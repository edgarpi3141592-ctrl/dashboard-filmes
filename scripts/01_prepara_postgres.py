import os
import sys

import psycopg2
from dotenv import load_dotenv

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(os.path.join(RAIZ, ".env"))

HOST = os.environ["PGHOST"]
PUERTO = os.environ["PGPORT"]
USUARIO = os.environ["PGUSER"]
CLAVE = os.environ["PGPASSWORD"]
SSL = os.environ.get("PGSSLMODE", "require")
BASE = os.environ.get("PGDATABASE", "guests")
BASE_ADMIN = os.environ.get("PGDATABASE_ADMIN", "defaultdb")


def conecta(nombre_base):
    return psycopg2.connect(host=HOST, port=PUERTO, user=USUARIO,
                            password=CLAVE, dbname=nombre_base, sslmode=SSL)


print(f"Servidor : {HOST}:{PUERTO}")
print(f"Usuario  : {USUARIO}")

cn = conecta(BASE_ADMIN)
cn.autocommit = True
try:
    with cn.cursor() as cur:
        cur.execute("SELECT version()")
        print("Version  :", cur.fetchone()[0].split(",")[0])

        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (BASE,))
        if cur.fetchone():
            print(f"Base     : '{BASE}' ya existía")
        else:
            cur.execute(f'CREATE DATABASE "{BASE}"')
            print(f"Base     : '{BASE}' CREADA")
finally:
    cn.close()

with conecta(BASE) as cn:
    with cn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS people (
                id      SERIAL PRIMARY KEY,
                email   TEXT NOT NULL,
                comment TEXT NOT NULL,
                fecha   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    cn.commit()

    with cn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'people'
            ORDER BY ordinal_position
        """)
        print(f"\nTabla 'people' en la base '{BASE}':")
        for columna, tipo in cur.fetchall():
            print(f"   {columna:10s} {tipo}")

        cur.execute("SELECT COUNT(*) FROM people")
        print(f"\nRenglones actuales: {cur.fetchone()[0]}")

print("\nLISTO")
