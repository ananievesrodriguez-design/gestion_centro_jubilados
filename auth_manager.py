from functools import wraps
from flask import abort, session, redirect, url_for, flash, request
from sqlalchemy import text
from supabase_client import supabase
from models import db


def _admin_activo():
    usuario = session.get("user", {})
    if session.get("auth_provider") in {"cobradores", "local"}:
        cuenta = db.session.execute(text("""
            SELECT rol
            FROM cobradores
            WHERE id = :id
              AND habilitado IS TRUE
              AND password IS NOT NULL
              AND rol IN ('admin', 'superadmin');
        """), {"id": session.get("cobrador_id")}).mappings().first()
        if cuenta:
            session["user"] = {**usuario, "role": cuenta["rol"]}
            return True
        return False

    if usuario.get("role") == "superadmin":
        return True
    if usuario.get("role") != "admin" or not usuario.get("email"):
        return False
    return db.session.execute(text("""
        SELECT id FROM cobradores
        WHERE LOWER(email) = :email
          AND rol IN ('admin', 'superadmin')
          AND habilitado IS TRUE;
    """), {"email": usuario["email"].lower()}).first() is not None


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
    """Permite el acceso a sesiones válidas de administración o cobradores."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("auth_provider") in {"cobradores", "local"}:
            cobrador_id = session.get("cobrador_id")
            cobrador = db.session.execute(text("""
                SELECT c.id, c.nombre, c.apellido, c.rol
                FROM cobradores c
                LEFT JOIN socios s ON s.id = c.socio_id
                WHERE c.id = :id
                  AND c.habilitado IS TRUE
                  AND c.password IS NOT NULL
                  AND (
                    c.rol IN ('admin', 'superadmin')
                    OR (
                        c.rol = 'cobrador'
                        AND s.id IS NOT NULL
                        AND LOWER(COALESCE(s.estado, 'Activo')) = 'activo'
                    )
                  );
            """), {"id": cobrador_id}).mappings().first()
            if cobrador:
                session["user"] = {
                    **session.get("user", {}),
                    "role": cobrador["rol"],
                    "nombre": f"{cobrador['nombre']} {cobrador['apellido'] or ''}".strip(),
                }
                return f(*args, **kwargs)
            session.clear()
            flash("La cuenta de cobrador no está habilitada.", "warning")
            return redirect(url_for("auth.login"))

        if not session.get("access_token") or not verificar_o_refrescar_token():
            flash("Por favor inicia sesión para acceder al panel de administración.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if not _admin_activo():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Restringe una vista a usuarios autenticados de administración."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("auth_provider") in {"cobradores", "local"}:
            if not _admin_activo():
                abort(403)
            return f(*args, **kwargs)
        if not session.get("access_token") or not verificar_o_refrescar_token():
            flash("Por favor inicia sesión para acceder al panel de administración.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if not _admin_activo():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function