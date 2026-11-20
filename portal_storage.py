import mimetypes
from uuid import uuid4

from config import (
    SUPABASE_PORTAL_BUCKET,
    SUPABASE_SERVICE_ROLE_KEY,
    supabase,
    supabase_admin,
)


def es_foto_en_storage(archivo):
    return isinstance(archivo, str) and archivo.startswith("fotos/") and ".." not in archivo


def subir_foto_portal(archivo, nombre_original):
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Configure SUPABASE_SERVICE_ROLE_KEY para subir fotos del portal.")

    extension = nombre_original.rsplit(".", 1)[1].lower()
    ruta_storage = f"fotos/{uuid4().hex}.{extension}"
    content_type = archivo.mimetype or mimetypes.guess_type(nombre_original)[0] or "application/octet-stream"
    archivo.stream.seek(0)
    supabase_admin.storage.from_(SUPABASE_PORTAL_BUCKET).upload(
        ruta_storage,
        archivo.stream,
        {"content-type": content_type, "upsert": "false"},
    )
    return ruta_storage


def url_publica_foto_portal(ruta_storage):
    if not es_foto_en_storage(ruta_storage):
        raise ValueError("La ruta no corresponde a una foto de Supabase Storage.")
    return supabase.storage.from_(SUPABASE_PORTAL_BUCKET).get_public_url(ruta_storage)


def descargar_foto_portal(ruta_storage):
    if not es_foto_en_storage(ruta_storage):
        raise ValueError("La ruta no corresponde a una foto de Supabase Storage.")
    return supabase.storage.from_(SUPABASE_PORTAL_BUCKET).download(ruta_storage)


def eliminar_foto_portal(ruta_storage):
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Configure SUPABASE_SERVICE_ROLE_KEY para eliminar fotos del portal.")
    if es_foto_en_storage(ruta_storage):
        supabase_admin.storage.from_(SUPABASE_PORTAL_BUCKET).remove([ruta_storage])
