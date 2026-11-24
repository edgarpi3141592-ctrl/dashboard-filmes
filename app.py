import json
import os
import re

import pandas as pd
import psycopg2
import streamlit as st
from google.cloud import firestore

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

st.set_page_config(page_title="Películas · Dashboard",
                   page_icon="🎬",
                   layout="wide",
                   initial_sidebar_state="expanded")

ROJO = "#E50914"
COLECCION = "movies"
RAIZ = os.path.dirname(os.path.abspath(__file__))
CARTELES = os.path.join(RAIZ, "assets", "posters")

st.markdown("""
<style>
  .stApp { background: #141414; }

  
  .cintillo { display:flex; align-items:baseline; gap:.65rem; margin:.2rem 0 .1rem; }
  .cintillo .marca {
      font-family: "Arial Black", Impact, sans-serif;
      font-size: 2.6rem; font-weight: 900; letter-spacing: -.045em;
      color: #E50914; line-height: 1;
  }
  .cintillo .resto {
      font-size: 1.45rem; font-weight: 600; color: #f5f5f5; letter-spacing: .01em;
  }
  .bajada { color:#9a9a9a; font-size:.9rem; margin:0 0 1.1rem; }

  
  .fichas { display:flex; gap:.6rem; flex-wrap:wrap; margin:.1rem 0 1.3rem; }
  .ficha {
      background:#1c1c1c; border:1px solid #2b2b2b; border-radius:9px;
      padding:.5rem .95rem; min-width:106px;
  }
  .ficha .n { font-size:1.5rem; font-weight:800; color:#fff; line-height:1.1; }
  .ficha .t { font-size:.68rem; color:#8d8d8d; text-transform:uppercase;
              letter-spacing:.09em; }
  .ficha.viva { border-color:#E50914; }
  .ficha.viva .n { color:#E50914; }

  
  .tarjeta { margin-bottom:1.1rem; }
  
  div[data-testid="stImage"] img {
      width:100%; aspect-ratio:2/3; object-fit:cover; border-radius:7px;
      background:#232323; display:block;
  }
  
  div[data-testid="stButton"] button[kind="tertiary"] {
      color:#f2f2f2; font-size:.82rem; font-weight:600; line-height:1.25;
      text-align:left; justify-content:flex-start; height:2.5rem;
      padding:.38rem 0 0; margin:0; background:transparent; border:0;
      white-space:normal; overflow:hidden;
  }
  div[data-testid="stButton"] button[kind="tertiary"]:hover,
  div[data-testid="stButton"] button[kind="tertiary"]:focus {
      color:#E50914; background:transparent; border:0;
  }

  
  .tarjeta .dir {
      color:#8d8d8d; font-size:.72rem; line-height:1.2; height:1.75rem;
      display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
      overflow:hidden;
  }
  .tarjeta .gen {
      display:inline-block; margin-top:.3rem; padding:.06rem .42rem;
      border:1px solid #3a3a3a; border-radius:3px;
      color:#b6b6b6; font-size:.64rem; letter-spacing:.05em;
      text-transform:uppercase;
  }
  .sinimg {
      width:100%; aspect-ratio:2/3; border-radius:7px; background:#232323;
      display:flex; align-items:center; justify-content:center;
      color:#4a4a4a; font-size:1.9rem;
  }

  
  .ficha-tit { font-size:1.65rem; font-weight:800; color:#fff; line-height:1.15; }
  .ficha-sub { color:#8d8d8d; font-size:.9rem; margin:.15rem 0 1.1rem; }
  .ficha-dato {
      display:flex; gap:.9rem; padding:.5rem 0; border-bottom:1px solid #262626;
  }
  .ficha-dato .e {
      color:#8d8d8d; font-size:.7rem; text-transform:uppercase;
      letter-spacing:.09em; min-width:92px; padding-top:.2rem;
  }
  .ficha-dato .v { color:#f2f2f2; font-size:1rem; font-weight:500; }
  .ficha-pie { color:#6a6a6a; font-size:.72rem; margin-top:1.1rem; }

  
  section[data-testid="stSidebar"] { background:#0d0d0d; border-right:1px solid #262626; }
  section[data-testid="stSidebar"] .cintillo { margin-bottom:1.1rem; }
  section[data-testid="stSidebar"] .marca { font-size:2rem; }
  section[data-testid="stSidebar"] h3 {
      color:#E50914; font-size:.76rem; text-transform:uppercase;
      letter-spacing:.11em; margin:1.1rem 0 .3rem;
  }
  .stButton > button {
      background:#E50914; color:#fff; border:0; border-radius:4px;
      font-weight:600; font-size:.83rem;
  }
  .stButton > button:hover { background:#f6121d; color:#fff; }

  div[data-testid="stDataFrame"] { border:1px solid #2b2b2b; border-radius:7px; }
</style>
""", unsafe_allow_html=True)


def secreto(seccion):
    try:
        if seccion in st.secrets:
            return dict(st.secrets[seccion])
    except Exception:
        pass
    return None


@st.cache_resource
def conecta_firestore():
    credenciales = secreto("firestore")
    if credenciales:
        if "private_key" in credenciales:
            credenciales["private_key"] = credenciales["private_key"].replace(
                "\\n", "\n")
        return firestore.Client.from_service_account_info(credenciales)

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")
    if os.path.isfile(ruta):
        return firestore.Client.from_service_account_json(ruta)

    st.error(
        "**Falta la llave de Firestore.**\n\n"
        "En la computadora: el archivo `keys.json` en esta carpeta.\n\n"
        "En Streamlit Cloud: el contenido de ese JSON pegado en "
        "*Settings → Secrets*, bajo `[firestore]`."
    )
    st.stop()


@st.cache_data(ttl=300, show_spinner="Leyendo las películas de Firestore…")
def lee_todas_las_peliculas():
    documentos = conecta_firestore().collection(COLECCION).stream()
    registros = []
    for doc in documentos:
        d = doc.to_dict()
        d["id"] = doc.id
        registros.append(d)

    df = pd.DataFrame(registros)
    if df.empty:
        return df

    for columna in ("name", "genre", "director", "company", "year",
                    "poster_file", "poster_url"):
        if columna not in df.columns:
            df[columna] = ""
    df = df.fillna("")
    orden = ["name", "genre", "director", "company", "year",
             "poster_file", "poster_url", "id"]
    df = df[orden + [c for c in df.columns if c not in orden]]
    return df.sort_values("name", ignore_index=True)


def guarda_pelicula(nombre, genero, director, compania, anio="", poster=""):
    identificador = re.sub(r"[^\w\s-]", "", nombre, flags=re.UNICODE).strip()
    identificador = re.sub(r"[\s_-]+", "-", identificador).lower()[:1400]
    if not identificador:
        return False, "El nombre no puede quedar vacío."

    referencia = conecta_firestore().collection(COLECCION).document(identificador)
    if referencia.get().exists:
        return False, f"«{nombre}» ya está en la colección."

    referencia.set({"name": nombre.strip(), "genre": genero,
                    "director": director, "company": compania,
                    "year": str(anio),
                    "poster_url": poster.strip(), "poster_file": ""})
    return True, f"«{nombre}» se insertó en Firestore."


def datos_postgres():
    credenciales = secreto("postgres")
    if credenciales:
        return credenciales
    return {
        "host": os.getenv("PGHOST", ""),
        "port": os.getenv("PGPORT", "5432"),
        "user": os.getenv("PGUSER", ""),
        "password": os.getenv("PGPASSWORD", ""),
        "dbname": os.getenv("PGDATABASE", "guests"),
        "sslmode": os.getenv("PGSSLMODE", "require"),
    }


def conecta_postgres():
    return psycopg2.connect(**datos_postgres())


def registra_visita(correo, comentario):
    with conecta_postgres() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO people (email, comment) VALUES (%s, %s)",
                (correo.strip(), comentario.strip()))
        conexion.commit()


def lee_visitas():
    with conecta_postgres() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT id, email, comment, fecha
                  FROM people
                 ORDER BY id DESC
            """)
            filas = cursor.fetchall()
    return pd.DataFrame(filas, columns=["id", "email", "comment", "fecha"])


def busca_por_titulo(df, texto):
    if not texto.strip():
        return df
    return df[df["name"].str.contains(texto.strip(), case=False, na=False,
                                      regex=False)]


def filtra_por_director(df, director):
    return df[df["director"].str.strip().str.casefold()
              == director.strip().casefold()]


def contadores(df, total, etiqueta_viva):
    piezas = [
        ('<div class="ficha viva"><div class="n">%d</div>'
         '<div class="t">%s</div></div>' % (len(df), etiqueta_viva)),
        ('<div class="ficha"><div class="n">%d</div>'
         '<div class="t">en la colección</div></div>' % total),
        ('<div class="ficha"><div class="n">%d</div>'
         '<div class="t">directores</div></div>'
         % (df["director"].nunique() if not df.empty else 0)),
        ('<div class="ficha"><div class="n">%d</div>'
         '<div class="t">géneros</div></div>'
         % (df["genre"].nunique() if not df.empty else 0)),
    ]
    st.markdown('<div class="fichas">%s</div>' % "".join(piezas),
                unsafe_allow_html=True)


def escapa(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def ruta_cartel(pelicula):
    archivo = str(pelicula.get("poster_file", "")).strip()
    if archivo:
        ruta = os.path.join(CARTELES, archivo)
        if os.path.isfile(ruta):
            return ruta
    enlace = str(pelicula.get("poster_url", "")).strip()
    return enlace if enlace.startswith("http") else ""


@st.dialog("Ficha de la película", width="large")
def ficha(pelicula):
    izquierda, derecha = st.columns([1, 2.1], gap="medium")

    with izquierda:
        cartel = ruta_cartel(pelicula)
        if cartel:
            st.image(cartel, width=230)
        else:
            st.markdown('<div class="sinimg">🎬</div>', unsafe_allow_html=True)

    with derecha:
        st.markdown(
            '<div class="ficha-tit">%s</div>'
            '<div class="ficha-sub">%s</div>'
            % (escapa(pelicula.get("name", "")),
               escapa(pelicula.get("year", "") or "—")),
            unsafe_allow_html=True)

        for etiqueta, clave in (("Género", "genre"), ("Director", "director"),
                                ("Compañía", "company"), ("Año", "year")):
            st.markdown(
                '<div class="ficha-dato"><span class="e">%s</span>'
                '<span class="v">%s</span></div>'
                % (etiqueta, escapa(pelicula.get(clave, "") or "—")),
                unsafe_allow_html=True)

        st.markdown(
            '<div class="ficha-pie">Documento <code>%s</code> de la colección '
            '<code>%s</code> en Cloud Firestore</div>'
            % (escapa(pelicula.get("id", "")), COLECCION),
            unsafe_allow_html=True)


def galeria(df, por_fila=8):
    filas = df.to_dict("records")
    for principio in range(0, len(filas), por_fila):
        columnas = st.columns(por_fila, gap="small")
        for columna, pelicula in zip(columnas, filas[principio:principio + por_fila]):
            with columna:
                cartel = ruta_cartel(pelicula)
                if cartel:
                    st.image(cartel, width="stretch")
                else:
                    st.markdown('<div class="sinimg">🎬</div>',
                                unsafe_allow_html=True)

                if st.button(pelicula.get("name", "—"),
                             key="ficha-%s" % pelicula.get("id", principio),
                             type="tertiary", width="stretch"):
                    ficha(pelicula)

                anio = pelicula.get("year", "")
                st.markdown(
                    '<div class="tarjeta">'
                    '<div class="dir">%s%s</div>'
                    '<span class="gen">%s</span></div>'
                    % (escapa(pelicula.get("director", "")),
                       (" · %s" % escapa(anio)) if anio else "",
                       escapa(pelicula.get("genre", ""))),
                    unsafe_allow_html=True)


def muestra(df, encabezado, total, etiqueta_viva, nota=""):
    st.header(encabezado)
    if nota:
        st.caption(nota)
    contadores(df, total, etiqueta_viva)

    if df.empty:
        st.warning("No hay películas que coincidan con esa búsqueda.")
        return

    galeria(df)
    st.markdown("##### Datos")
    st.dataframe(df[["name", "genre", "director", "company", "year"]],
                 width="stretch", height=min(420, 56 + 35 * len(df)))


peliculas = lee_todas_las_peliculas()

if peliculas.empty:
    st.markdown('<div class="cintillo"><span class="marca">FILMES</span></div>',
                unsafe_allow_html=True)
    st.warning(
        f"La colección **{COLECCION}** de Firestore está vacía. "
        "Corre `scripts/03_carga_firestore.py` para llenarla."
    )
    st.stop()

directores = sorted(d for d in peliculas["director"].unique() if d)
companias = sorted(c for c in peliculas["company"].unique() if c)
generos = sorted(g for g in peliculas["genre"].unique() if g)

with st.sidebar:
    st.markdown('<div class="cintillo"><span class="marca">FILMES</span></div>',
                unsafe_allow_html=True)

    todas = st.checkbox("Mostrar todas las películas", value=True)

    st.markdown("### Buscar por título")
    titulo = st.text_input("Título de la película", key="titulo",
                           placeholder="avatar, the lord…",
                           label_visibility="collapsed")
    busca = st.button("Buscar", width="stretch")

    st.markdown("### Buscar por director")
    director = st.selectbox("Director", directores, index=0,
                            label_visibility="collapsed")
    busca_dir = st.button("Buscar por director", width="stretch")

    st.markdown("### Nuevo filme")
    with st.form("alta", clear_on_submit=True):
        nuevo_nombre = st.text_input("Name")
        nueva_compania = st.selectbox("Company", companias)
        otra_compania = st.text_input("…o escribe otra compañía")
        nuevo_director = st.selectbox("Director ", directores)
        otro_director = st.text_input("…o escribe otro director")
        nuevo_genero = st.selectbox("Genre", generos)
        nuevo_cartel = st.text_input("Carátula (URL, opcional)")
        guarda = st.form_submit_button("Crear nuevo filme", width="stretch")

    if guarda:
        if not nuevo_nombre.strip():
            st.error("El nombre es obligatorio.")
        else:
            bien, aviso = guarda_pelicula(
                nuevo_nombre,
                nuevo_genero,
                (otro_director.strip() or nuevo_director),
                (otra_compania.strip() or nueva_compania),
                poster=nuevo_cartel)
            if bien:
                st.success(aviso)
                lee_todas_las_peliculas.clear()
                st.rerun()
            else:
                st.warning(aviso)

    st.markdown("### Libro de visitas")
    with st.form("visitas", clear_on_submit=True):
        correo = st.text_input("email")
        comentario = st.text_area("Comentario", height=80)
        firma = st.form_submit_button("Registrar visita", width="stretch")

    if firma:
        if not correo.strip() or not comentario.strip():
            st.warning("Hacen falta el correo y el comentario.")
        else:
            try:
                registra_visita(correo, comentario)
                st.success("¡Gracias! Tu comentario quedó guardado.")
            except Exception as error:
                st.error(f"No se pudo guardar en PostgreSQL: {error}")

    ver_visitas = st.button("Ver visitas", width="stretch")

st.markdown(
    '<div class="cintillo"><span class="marca">FILMES</span>'
    '<span class="resto">catálogo interactivo</span></div>'
    '<p class="bajada">Las películas se leen de la colección '
    '<code>movies</code> de Cloud Firestore; el libro de visitas se guarda en '
    'PostgreSQL. <b>Haz clic en el título de una película para ver su '
    'ficha.</b></p>', unsafe_allow_html=True)

total = len(peliculas)

if busca_dir:
    resultado = filtra_por_director(peliculas, director)
    muestra(resultado, f"Películas de {director}", total, "de este director")

elif busca:
    resultado = busca_por_titulo(peliculas, titulo)
    muestra(resultado, f"Resultados para «{titulo}»" if titulo.strip()
            else "Todas las películas", total, "encontradas",
            nota="La coincidencia es «que contenga» y no distingue "
                 "mayúsculas de minúsculas.")

elif todas:
    muestra(peliculas, "Todas las películas", total, "en pantalla")

else:
    st.info(
        "Marca **Mostrar todas las películas** en la barra lateral, o busca "
        "por título o por director."
    )

if ver_visitas:
    st.markdown("---")
    st.header("Libro de visitas")
    try:
        visitas = lee_visitas()
        if visitas.empty:
            st.info("Todavía no hay comentarios registrados.")
        else:
            st.caption(f"{len(visitas)} comentarios en la tabla "
                       "`people` de PostgreSQL")
            for _, v in visitas.iterrows():
                st.markdown(
                    f"**{v['id']}.** {v['comment']}  \n"
                    f"<span style='color:#8d8d8d;font-size:.8rem'>"
                    f"{v['email']} · {v['fecha']:%d/%m/%Y %H:%M}</span>",
                    unsafe_allow_html=True)
            st.dataframe(visitas, width="stretch")
    except Exception as error:
        st.error(f"No se pudo leer de PostgreSQL: {error}")
