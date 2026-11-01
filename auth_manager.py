import os
import jwt
from functools import wraps
from flask import session, redirect, url_for, flash, request
from supabase_client import supabase
from dotenv import load_dotenv

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

def verificar_o_refrescar_token():
    token = session.get("access_token")
    refresh_token = session.get("refresh_token")

    if not token:
        return False

    try:
        # Validación del token de acceso contra el servidor de Supabase Auth
        # (el servidor soporta las firmas HS256 y ES256, y valida expiracion/aud)
        res = supabase.auth.get_user(token)
        if res and res.user:
            return True
        raise ValueError("Token de acceso invalido")
    except Exception:
        # Si el access_token expiro o esta invalido, lo renovamos con el refresh_token
        if refresh_token:
            try:
                res = supabase.auth.refresh_session(refresh_token)
                session["access_token"] = res.session.access_token
                session["refresh_token"] = res.session.refresh_token
                return True
            except Exception:
                session.clear()
                return False
        session.clear()
        return False

def login_required(f):
    """Protege cualquier vista interna de administración"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("access_token") or not verificar_o_refrescar_token():
            flash("Por favor inicia sesión para acceder al panel de administración.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function