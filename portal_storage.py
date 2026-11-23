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


def es_logo_en_storage(archivo):
    return isinstance(archivo, str) and archivo.startswith("logos/") and ".." not in archivo


def es_imagen_novedad_en_storage(archivo):
    return isinstance(archivo, str) and archivo.startswith("novedades/") and ".." not in archivo


def _subir_imagen_storage(archivo, nombre_original, carpeta):
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Configure SUPABASE_SERVICE_ROLE_KEY para subir imágenes institucionales.")

    extension = nombre_original.rsplit(".", 1)[1].lower()
    ruta_storage = f"{carpeta}/{uuid4().hex}.{extension}"
    content_type = archivo.mimetype or mimetypes.guess_type(nombre_original)[0] or "application/octet-stream"
    archivo.stream.seek(0)
    contenido = archivo.stream.read()
    supabase_admin.storage.from_(SUPABASE_PORTAL_BUCKET).upload(
        ruta_storage,
        contenido,
        {"content-type": content_type, "upsert": "false"},
    )
    return ruta_storage


def subir_foto_portal(archivo, nombre_original):
    return _subir_imagen_storage(archivo, nombre_original, "fotos")


def subir_logo_institucional(archivo, nombre_original):
    return _subir_imagen_storage(archivo, nombre_original, "logos")


def subir_imagen_novedad(archivo, nombre_original):
    return _subir_imagen_storage(archivo, nombre_original, "novedades")


def url_publica_imagen_novedad(ruta_storage):
    if not es_imagen_novedad_en_storage(ruta_storage):
        raise ValueError("La ruta no corresponde a una imagen de novedades.")
    return supabase.storage.from_(SUPABASE_PORTAL_BUCKET).get_public_url(ruta_storage)


def eliminar_imagen_novedad(ruta_storage):
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Configure SUPABASE_SERVICE_ROLE_KEY para eliminar imágenes de novedades.")
    if es_imagen_novedad_en_storage(ruta_storage):
        supabase_admin.storage.from_(SUPABASE_PORTAL_BUCKET).remove([ruta_storage])


def url_publica_foto_portal(ruta_storage):
    if not es_foto_en_storage(ruta_storage):
        raise ValueError("La ruta no corresponde a una foto de Supabase Storage.")
    return supabase.storage.from_(SUPABASE_PORTAL_BUCKET).get_public_url(ruta_storage)


def url_publica_logo_institucional(ruta_storage):
    if not es_logo_en_storage(ruta_storage):
        raise ValueError("La ruta no corresponde a un logo institucional de Supabase Storage.")
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


def eliminar_logo_institucional(ruta_storage):
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Configure SUPABASE_SERVICE_ROLE_KEY para eliminar el logo institucional.")
    if es_logo_en_storage(ruta_storage):
        supabase_admin.storage.from_(SUPABASE_PORTAL_BUCKET).remove([ruta_storage])
