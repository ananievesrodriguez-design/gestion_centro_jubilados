import os
import json
from dotenv import load_dotenv
from flask import session
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Faltan configurar SUPABASE_URL o SUPABASE_ANON_KEY en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else supabase

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Falta configurar SECRET_KEY en las variables de entorno.")
DATABASE_URL = os.getenv("DATABASE_URL")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_institucion.json")
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img")
NOVEDADES_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "novedades")
DOCUMENTOS_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "documentos")
FOTOS_PORTAL_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fotos_portal")
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "svg"}
EXTENSIONES_DOCUMENTOS = {"pdf", "doc", "docx"}


def cargar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_config(datos):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)


def archivo_permitido(nombre):
    return "." in nombre and nombre.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS


def documento_permitido(nombre):
    return "." in nombre and nombre.rsplit(".", 1)[1].lower() in EXTENSIONES_DOCUMENTOS


def inject_global_context():
    config = cargar_config()
    return {
        "INSTITUCION": config.get("institucion", {}),
        "CONFIG": config,
        "current_user": session.get("user", None),
        "is_authenticated": bool(session.get("access_token")),
    }
