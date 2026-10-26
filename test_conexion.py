import os
import sys
from dotenv import load_dotenv

print("--- INICIO DEL TEST ---", flush=True)

# 1. Cargar .env
load_dotenv()
db_url = os.getenv("DATABASE_URL")

print(f"Versión de Python en uso: {sys.executable}", flush=True)

if not db_url:
    print("ERROR CRÍTICO: No se encontró la variable DATABASE_URL en el archivo .env", flush=True)
    print("Verifica que el archivo se llame exactamente .env y esté en la carpeta del proyecto.", flush=True)
    sys.exit(1)

# Mostramos parte de la URL sin exponer toda la contraseña
url_segura = db_url.split("@")[-1] if "@" in db_url else db_url[:15]
print(f"DATABASE_URL encontrada. Conectando al servidor: @{url_segura}", flush=True)

# 2. Intentar conexión
try:
    from sqlalchemy import create_engine, text
    print("Módulo SQLAlchemy cargado correctamente.", flush=True)
    
    engine = create_engine(db_url, connect_args={"connect_timeout": 10})
    print("Conectando con Supabase (esperando respuesta)...", flush=True)
    
    with engine.connect() as conexion:
        resultado = conexion.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;")
        )
        tablas = [fila[0] for fila in resultado]
        print("\n>>> ¡CONEXIÓN EXITOSA A SUPABASE! <<<", flush=True)
        print(f"Tablas encontradas: {tablas}", flush=True)

except Exception as e:
    print(f"\nERROR AL CONECTAR CON SUPABASE:\n{e}", flush=True)

print("--- FIN DEL TEST ---", flush=True)