import json
import os
import re
import sys

from dotenv import load_dotenv
from google.cloud import firestore

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(os.path.join(RAIZ, ".env"))

LLAVES = os.path.join(RAIZ, os.getenv("GOOGLE_APPLICATION_CREDENTIALS",
                                      "keys.json"))
COLECCION = os.getenv("FIRESTORE_COLECCION", "movies")
DATOS = os.path.join(RAIZ, "datos", "peliculas.json")

if not os.path.isfile(LLAVES):
    sys.exit(
        f"No encuentro {LLAVES}.\n\n"
        "Firestore no se conecta con correo y contraseña: necesita la llave de\n"
        "CUENTA DE SERVICIO. En console.firebase.google.com:\n"
        "  Configuración del proyecto → Cuentas de servicio → Python\n"
        "  → Generar nueva clave privada\n"
        f"y el archivo descargado se guarda aquí como {LLAVES}"
    )

with open(DATOS, encoding="utf-8") as f:
    peliculas = json.load(f)

db = firestore.Client.from_service_account_json(LLAVES)
coleccion = db.collection(COLECCION)


def identificador(nombre):
    limpio = re.sub(r"[^\w\s-]", "", nombre, flags=re.UNICODE).strip()
    limpio = re.sub(r"[\s_-]+", "-", limpio).lower()
    return limpio[:1400] or "sin-nombre"


if "--borra" in sys.argv:
    n = 0
    for doc in coleccion.stream():
        doc.reference.delete()
        n += 1
    print(f"Borrados {n} documentos previos de '{COLECCION}'")

lote = db.batch()
for p in peliculas:
    lote.set(coleccion.document(identificador(p["name"])), p)
lote.commit()
print(f"Subidas {len(peliculas)} películas a la colección '{COLECCION}'")

traidas = [d.to_dict() for d in coleccion.stream()]
print(f"Leídas de vuelta: {len(traidas)}")
directores = sorted({t.get("director", "") for t in traidas})
print(f"Directores distintos: {len(directores)}")
print("Ejemplo:", json.dumps(traidas[0], ensure_ascii=False)[:160])
