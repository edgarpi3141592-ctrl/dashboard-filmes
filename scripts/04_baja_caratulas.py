import io
import json
import os
import sys
import time

import requests
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DESTINO = os.path.join(RAIZ, "assets", "posters")
DATOS = os.path.join(RAIZ, "datos", "peliculas.json")
sys.stdout.reconfigure(encoding="utf-8")

CABECERAS = {"User-Agent": "RetoFilmesDashboard/1.0 (proyecto escolar)"}
ANCHO = 200
PAUSA = 1.0
REINTENTOS = 4

os.makedirs(DESTINO, exist_ok=True)
with open(DATOS, encoding="utf-8") as f:
    peliculas = json.load(f)


def nombre_archivo(pelicula):
    base = "".join(c if c.isalnum() else "-" for c in pelicula["name"].lower())
    base = "-".join(p for p in base.split("-") if p)
    return f"{base[:60]}.jpg"


def baja(url):
    for intento in range(REINTENTOS):
        r = requests.get(url, headers=CABECERAS, timeout=40)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return r.content
        if r.status_code == 429:
            espera = int(r.headers.get("retry-after", 60)) + 5
            print(f"        429; el servidor pide {espera - 5} s de espera…")
            time.sleep(espera)
            continue
        raise RuntimeError(f"{r.status_code} {r.headers.get('content-type','')}")
    raise RuntimeError("429 tras varios intentos")


bien, mal = 0, []
for i, p in enumerate(peliculas, 1):
    archivo = nombre_archivo(p)
    ruta = os.path.join(DESTINO, archivo)
    p["poster_file"] = archivo
    p["poster_url"] = p.get("poster", "")

    if os.path.isfile(ruta) and os.path.getsize(ruta) > 2000:
        bien += 1
        continue

    try:
        crudo = baja(p["poster_url"])
        imagen = Image.open(io.BytesIO(crudo)).convert("RGB")
        alto = round(imagen.height * ANCHO / imagen.width)
        imagen = imagen.resize((ANCHO, alto), Image.LANCZOS)
        imagen.save(ruta, "JPEG", quality=82, optimize=True)
        bien += 1
        print(f"  [{i:3d}/{len(peliculas)}] {p['name'][:40]:42s} "
              f"{imagen.width}x{imagen.height}  {os.path.getsize(ruta)//1024} KB")
    except Exception as e:
        mal.append((p["name"], str(e)[:50]))
        p["poster_file"] = ""
        print(f"  [{i:3d}/{len(peliculas)}] {p['name'][:40]:42s} FALLÓ {e}")
    time.sleep(PAUSA)

with open(DATOS, "w", encoding="utf-8") as f:
    json.dump(peliculas, f, ensure_ascii=False, indent=2)

total = sum(os.path.getsize(os.path.join(DESTINO, a))
            for a in os.listdir(DESTINO))
print(f"\n{bien} carátulas en {DESTINO}  ({total/1024/1024:.2f} MB en total)")
if mal:
    print("fallaron:")
    for n, m in mal:
        print("  ", n, m)
