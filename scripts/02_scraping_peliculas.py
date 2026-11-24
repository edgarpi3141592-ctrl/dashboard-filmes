import csv
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DESTINO = os.path.join(RAIZ, "datos")
sys.stdout.reconfigure(encoding="utf-8")

CABECERAS = {"User-Agent": "RetoFilmesDashboard/1.0 (proyecto escolar)"}
PAUSA = 0.4
TOPE_TAQUILLERAS = 40
SESION = requests.Session()
SESION.headers.update(CABECERAS)


def baja(url):
    r = SESION.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def limpia(texto):
    texto = re.sub(r"\[[^\]]{1,4}\]", "", texto)
    return re.sub(r"\s+", " ", texto).strip(" ,;·")


def titulos_taquilleras():
    sopa = baja("https://en.wikipedia.org/wiki/List_of_highest-grossing_films")
    tabla = sopa.select_one("table.wikitable")
    salida = []
    for fila in tabla.select("tr"):
        enl = fila.select_one("th[scope='row'] i a, td i a")
        if enl and "/wiki/" in enl.get("href", ""):
            salida.append((enl.get_text(strip=True), enl["href"]))
    return salida[:TOPE_TAQUILLERAS]


def titulos_oscar():
    sopa = baja("https://en.wikipedia.org/wiki/Academy_Award_for_Best_Picture")
    salida = []
    for tabla in sopa.select("table.wikitable"):
        encabezado = tabla.find_previous(["h2", "h3"])
        decada = encabezado.get_text(" ", strip=True) if encabezado else ""
        if decada not in ("1990s", "2000s", "2010s", "2020s"):
            continue
        for enl in tabla.select("tr a"):
            padres = {p.name for p in enl.parents}
            if {"b", "i"} <= padres and "/wiki/" in enl.get("href", ""):
                salida.append((enl.get_text(strip=True), enl["href"]))
    return salida


GENEROS = [
    (r"animated|animation", "Animation"),
    (r"science[- ]fiction|sci-fi|space opera", "Sci-Fi"),
    (r"superhero", "Action"),
    (r"fantasy", "Fantasy"),
    (r"horror", "Horror"),
    (r"musical", "Musical"),
    (r"western", "Western"),
    (r"war|anti-war", "War"),
    (r"biographical|biopic", "Biography"),
    (r"crime|heist|gangster", "Crime"),
    (r"mystery|noir", "Mystery"),
    (r"thriller|spy", "Thriller"),
    (r"romantic|romance", "Romance"),
    (r"comedy|comedic", "Comedy"),
    (r"historical|period", "Historical"),
    (r"sports?", "Sport"),
    (r"adventure", "Adventure"),
    (r"action", "Action"),
    (r"drama", "Drama"),
]

RUIDO_CATEGORIA = re.compile(r"award|winner|nominat|registry|bafta|golden globe",
                             re.I)


def adivina_genero(primera_oracion, categorias):
    corte = re.split(r"\bfilms?\b", primera_oracion, maxsplit=1)[0].lower()

    limpias = [c for c in categorias if not RUIDO_CATEGORIA.search(c)]
    for fuente in (corte, " ".join(limpias).lower()):
        for patron, etiqueta in GENEROS:
            if re.search(rf"\b(?:{patron})\b", fuente):
                return etiqueta
    return "Drama"


def valor_infobox(caja, *etiquetas):
    for fila in caja.select("tr"):
        th, td = fila.select_one("th"), fila.select_one("td")
        if not (th and td):
            continue
        nombre = re.sub(r"\s+", " ", th.get_text(" ", strip=True)).lower()
        if any(e in nombre for e in etiquetas):
            for sup in td.select("sup"):
                sup.decompose()
            for br in td.select("br"):
                br.replace_with("|")
            puntos = td.select("li")
            if puntos:
                return [limpia(p.get_text(" ", strip=True)) for p in puntos]
            bruto = limpia(td.get_text("|", strip=True))
            return [t for t in (x.strip() for x in bruto.split("|")) if t]
    return []


def caratula(caja):
    img = caja.select_one("img")
    if not img:
        return ""

    def arregla(u):
        u = u.split("?")[0].strip()
        if u.startswith("//"):
            u = "https:" + u
        if "/thumb/" in u:
            u = u.replace("/thumb/", "/").rsplit("/", 1)[0]
        return u.replace("://thumb.wikimedia.org", "://upload.wikimedia.org")

    conjunto = img.get("srcset", "")
    if conjunto:
        return arregla(conjunto.split(",")[0].strip().split(" ")[0])
    return arregla(img.get("src", ""))


def ficha(titulo, url):
    sopa = baja(url)
    caja = sopa.select_one("table.infobox")
    if caja is None:
        return None

    directores = valor_infobox(caja, "directed by")
    companias = (valor_infobox(caja, "production compan")
                 or valor_infobox(caja, "distributed by")
                 or valor_infobox(caja, "studio"))
    fechas = valor_infobox(caja, "release date")

    anio = ""
    for t in fechas:
        m = re.search(r"(19|20)\d{2}", t)
        if m:
            anio = m.group(0)
            break

    primera = ""
    for p in sopa.select("div.mw-parser-output > p, p"):
        t = limpia(p.get_text(" ", strip=True))
        if len(t) > 60 and re.search(r"\bis (?:a|an)\b.*\bfilms?\b", t, re.I):
            primera = t.split(". ")[0]
            break

    cats = [a.get_text(strip=True) for a in sopa.select("#mw-normal-catlinks li a")]

    if not directores:
        return None

    return {
        "name": limpia(titulo),
        "genre": adivina_genero(primera, cats),
        "director": directores[0],
        "company": companias[0] if companias else "Independiente",
        "year": anio,
        "poster": caratula(caja),
    }


print("Recogiendo los títulos…")
pares = titulos_taquilleras()
print(f"  taquilleras : {len(pares)}")
osc = titulos_oscar()
print(f"  Óscar       : {len(osc)}")

vistos, lista = set(), []
for titulo, url in pares + osc:
    if url in vistos:
        continue
    vistos.add(url)
    lista.append((titulo, url))
print(f"  únicos      : {len(lista)}\n")

peliculas, fallos = [], []
for i, (titulo, url) in enumerate(lista, 1):
    try:
        d = ficha(titulo, url)
    except Exception as e:
        d = None
        print(f"  [{i:3d}/{len(lista)}] {titulo[:38]:40s} ERROR {e}")
    if d is None:
        fallos.append(titulo)
        continue
    peliculas.append(d)
    print(f"  [{i:3d}/{len(lista)}] {d['name'][:36]:38s} "
          f"{d['genre']:10s} {d['director'][:22]:24s} {d['company'][:26]}")
    time.sleep(PAUSA)

os.makedirs(DESTINO, exist_ok=True)
with open(os.path.join(DESTINO, "peliculas.json"), "w", encoding="utf-8") as f:
    json.dump(peliculas, f, ensure_ascii=False, indent=2)

campos = ["name", "genre", "director", "company", "year", "poster"]
with open(os.path.join(DESTINO, "peliculas.csv"), "w", encoding="utf-8",
          newline="") as f:
    w = csv.DictWriter(f, fieldnames=campos)
    w.writeheader()
    w.writerows(peliculas)

print(f"\n{len(peliculas)} películas guardadas en {DESTINO}")
if fallos:
    print("sin infobox utilizable:", ", ".join(fallos))

generos = {}
directores = {}
for p in peliculas:
    generos[p["genre"]] = generos.get(p["genre"], 0) + 1
    directores[p["director"]] = directores.get(p["director"], 0) + 1
print("\nGéneros :", ", ".join(f"{g} {n}" for g, n in
                               sorted(generos.items(), key=lambda x: -x[1])))
repetidos = {d: n for d, n in directores.items() if n > 1}
print(f"Directores: {len(directores)} distintos; con más de una película:",
      ", ".join(f"{d} ({n})" for d, n in
                sorted(repetidos.items(), key=lambda x: -x[1])))
print("Con carátula:", sum(1 for p in peliculas if p["poster"]))
