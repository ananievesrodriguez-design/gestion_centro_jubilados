import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Faltan configurar SUPABASE_URL o SUPABASE_ANON_KEY en el archivo .env")

# Cliente público que respeta las políticas RLS en PostgreSQL
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Cliente admin que usa la service_role_key (requerido para crear/editar usuarios en Supabase Auth)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else supabase