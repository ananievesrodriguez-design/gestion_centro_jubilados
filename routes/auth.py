import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
from supabase_client import supabase, supabase_admin
from auth_manager import admin_required, verificar_o_refrescar_token
from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_GRAPH_API_VERSION,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TEMPLATE_LANGUAGE,
    WHATSAPP_TEMPLATE_NAME,
)
from models import db

auth_bp = Blueprint("auth", __name__)


def _whatsapp_configurado():
    return all((
        WHATSAPP_ACCESS_TOKEN,
        WHATSAPP_PHONE_NUMBER_ID,
        WHATSAPP_TEMPLATE_NAME,
    ))


def _normalizar_usuario(usuario):
    usuario = usuario.strip().casefold()
    if not 3 <= len(usuario) <= 40 or not all(
        caracter.isalnum() or caracter in "._-" for caracter in usuario
    ):
        raise ValueError("El nombre de usuario debe tener entre 3 y 40 caracteres, sin espacios.")
    return usuario


def _digitos_telefono(telefono):
    return re.sub(r"\D", "", telefono or "")


def _buscar_cobrador_por_telefono(telefono):
    digitos_ingresados = _digitos_telefono(telefono)
    if not 8 <= len(digitos_ingresados) <= 15:
        return None

    cobradores = db.session.execute(text("""
        SELECT c.id, c.username, c.habilitado, c.password,
               s.telefono AS telefono_registrado
        FROM cobradores c
        JOIN socios s ON s.id = c.socio_id
        WHERE c.habilitado IS TRUE
          AND c.rol = 'cobrador'
          AND LOWER(COALESCE(s.estado, 'Activo')) = 'activo'
          AND s.telefono IS NOT NULL;
    """)).mappings().all()
    coincidencias = [
        cobrador for cobrador in cobradores
        if _digitos_telefono(cobrador["telefono_registrado"])[-10:]
        == digitos_ingresados[-10:]
    ]
    return coincidencias[0] if len(coincidencias) == 1 else None


def _hash_codigo(cobrador_id, codigo):
    clave = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    mensaje = f"{cobrador_id}:{codigo}".encode("utf-8")
    return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()


def _enviar_codigo_whatsapp(telefono, codigo):
    datos = {
        "messaging_product": "whatsapp",
        "to": _digitos_telefono(telefono),
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE_NAME,
            "language": {"code": WHATSAPP_TEMPLATE_LANGUAGE},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": codigo}],
            }],
        },
    }
    url = (
        f"https://graph.facebook.com/{WHATSAPP_GRAPH_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    req = Request(
        url,
        data=json.dumps(datos).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as respuesta:
            if respuesta.status < 200 or respuesta.status >= 300:
                raise ValueError("WhatsApp no aceptó el envío del código.")
    except HTTPError as error:
        current_app.logger.error("WhatsApp rechazó el envío del código (HTTP %s).", error.code)
        raise ValueError("No se pudo enviar el código por WhatsApp. Inténtelo nuevamente.") from error
    except URLError as error:
        current_app.logger.error("No se pudo conectar con WhatsApp: %s", error.reason)
        raise ValueError("No se pudo conectar con WhatsApp. Inténtelo nuevamente.") from error
    except TimeoutError as error:
        current_app.logger.error("Venció el tiempo de espera al conectar con WhatsApp.")
        raise ValueError("WhatsApp tardó demasiado en responder. Inténtelo nuevamente.") from error


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user", {}).get("role") == "cobrador":
        return redirect(url_for("socios.inicio_cobrador"))
    if session.get("access_token") and verificar_o_refrescar_token():
        return redirect(url_for("socios.listar_socios"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("Por favor ingresá tu correo o nombre de usuario y contraseña.", "warning")
            return render_template("login.html")

        es_correo = "@" in identifier
        cuenta_local = db.session.execute(text("""
                SELECT c.id, c.nombre, c.apellido, c.password, c.habilitado, c.rol,
                       c.email, s.id AS socio_id, s.estado AS estado_socio
                FROM cobradores c
                LEFT JOIN socios s ON s.id = c.socio_id
                WHERE LOWER(c.email) = :identifier
            """ if es_correo else """
                SELECT c.id, c.nombre, c.apellido, c.password, c.habilitado, c.rol,
                       c.email, s.id AS socio_id, s.estado AS estado_socio
                FROM cobradores c
                LEFT JOIN socios s ON s.id = c.socio_id
                WHERE LOWER(c.username) = :identifier
            """), {"identifier": identifier.casefold()}).mappings().first()
        if cuenta_local and cuenta_local["password"]:
            cuenta_habilitada = cuenta_local["habilitado"] and (
                cuenta_local["rol"] != "cobrador"
                or (
                    cuenta_local["socio_id"] is not None
                    and (cuenta_local["estado_socio"] or "Activo").lower() == "activo"
                )
            )
            if not cuenta_habilitada or not check_password_hash(
                cuenta_local["password"], password
            ):
                flash("Usuario o clave incorrectos, o cuenta deshabilitada.", "danger")
                return render_template("login.html")

            session.clear()
            session["auth_provider"] = "local"
            session["cobrador_id"] = cuenta_local["id"]
            session["user"] = {
                "id": cuenta_local["id"],
                "nombre": f"{cuenta_local['nombre']} {cuenta_local['apellido'] or ''}".strip(),
                "email": cuenta_local["email"],
                "role": cuenta_local["rol"],
            }
            flash(f"¡Bienvenido/a, {session['user']['nombre']}!", "success")
            destino = (
                url_for("socios.inicio_cobrador")
                if cuenta_local["rol"] == "cobrador"
                else url_for("socios.listar_socios")
            )
            return redirect(destino)
        if not es_correo:
            flash("Credenciales incorrectas o usuario no habilitado.", "danger")
            return render_template("login.html")

        try:
            response = supabase.auth.sign_in_with_password({
                "email": identifier.lower(),
                "password": password
            })
        except Exception:
            flash("Credenciales incorrectas o usuario no autorizado.", "danger")
            return render_template("login.html")

        app_role = (response.user.app_metadata or {}).get("role", "").lower()
        if app_role == "superadmin":
            role = "superadmin"
        else:
            try:
                admin_account = db.session.execute(text("""
                    SELECT rol FROM cobradores
                    WHERE LOWER(email) = :email
                      AND rol IN ('admin', 'superadmin')
                      AND habilitado IS TRUE;
                """), {"email": identifier.lower()}).mappings().first()
            except Exception:
                db.session.rollback()
                current_app.logger.exception("No se pudo verificar el rol de una cuenta de administración")
                flash("No se pudo verificar el permiso de esta cuenta. Intentá nuevamente.", "danger")
                return render_template("login.html")
            if not admin_account:
                try:
                    supabase.auth.sign_out()
                except Exception:
                    current_app.logger.exception("No se pudo cerrar una sesión sin rol de administración")
                flash("Esta cuenta no está habilitada para administrar el sistema.", "danger")
                return render_template("login.html")
            role = admin_account["rol"]
        session.clear()
        session["access_token"] = response.session.access_token
        session["refresh_token"] = response.session.refresh_token
        session["auth_provider"] = "supabase"
        session["user"] = {
            "id": response.user.id,
            "email": response.user.email,
            "nombre": (response.user.user_metadata or {}).get("nombre", identifier),
            "role": role
        }
        flash(f"¡Bienvenido/a, {session['user']['nombre']}!", "success")
        next_url = request.args.get("next", "")
        parsed_next = urlsplit(next_url)
        if (
            parsed_next.scheme or parsed_next.netloc
            or not next_url.startswith("/") or next_url.startswith("//")
            or "\\" in next_url
        ):
            next_url = ""
        return redirect(next_url or url_for("socios.listar_socios"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    if session.get("auth_provider") == "supabase":
        try:
            supabase.auth.sign_out()
        except Exception:
            current_app.logger.exception("No se pudo cerrar la sesión de Supabase")
    session.clear()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    """Verifica por WhatsApp a un cobrador habilitado antes de que cree su clave."""
    if request.method == "GET":
        return render_template(
            "registro_cobrador.html",
            whatsapp_configurado=_whatsapp_configurado(),
        )

    if not _whatsapp_configurado():
        flash("El registro por WhatsApp todavía no está configurado.", "warning")
        return redirect(url_for("auth.registro"))

    try:
        username = _normalizar_usuario(request.form.get("username", ""))
        telefono = request.form.get("telefono", "").strip()
        if not re.fullmatch(r"\+[0-9\s()./-]+", telefono):
            raise ValueError("Ingresá un teléfono argentino con código de país, por ejemplo +54 9.")
        digitos_telefono = _digitos_telefono(telefono)
        if not digitos_telefono.startswith("54") or not 10 <= len(digitos_telefono) <= 13:
            raise ValueError("Ingresá un teléfono argentino con código de país, por ejemplo +54 9.")
        telefono = f"+{digitos_telefono}"

        cobrador = _buscar_cobrador_por_telefono(telefono)
        if not cobrador:
            raise ValueError(
                "No encontramos un cobrador habilitado con ese teléfono. "
                "Consultá a la comisión directiva."
            )
        if cobrador["username"]:
            raise ValueError("Este cobrador ya tiene un usuario. Ingresá con tu clave o consultá al Centro.")
        username_existente = db.session.execute(text("""
            SELECT id FROM cobradores
            WHERE LOWER(username) = :username;
        """), {"username": username}).first()
        if username_existente:
            raise ValueError("Ese nombre de usuario ya está elegido. Probá con otro.")

        ahora = datetime.now(timezone.utc)
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        result = db.session.execute(text("""
            INSERT INTO auth_cobrador_challenges (
                cobrador_id, username, codigo_hash, expira_en, reintentos, proximo_envio
            )
            VALUES (:cobrador_id, :username, :codigo_hash, :expira_en, 0, :proximo_envio)
            ON CONFLICT (cobrador_id) DO UPDATE
            SET username = EXCLUDED.username,
                codigo_hash = EXCLUDED.codigo_hash,
                expira_en = EXCLUDED.expira_en,
                reintentos = 0,
                proximo_envio = EXCLUDED.proximo_envio,
                actualizado_en = NOW()
            WHERE auth_cobrador_challenges.proximo_envio <= :ahora
            RETURNING cobrador_id;
        """), {
            "cobrador_id": cobrador["id"],
            "username": username,
            "codigo_hash": _hash_codigo(cobrador["id"], codigo),
            "expira_en": ahora + timedelta(minutes=10),
            "proximo_envio": ahora + timedelta(seconds=60),
            "ahora": ahora,
        }).first()
        if not result:
            db.session.rollback()
            raise ValueError("Esperá un minuto antes de solicitar otro código.")
        db.session.commit()

        try:
            _enviar_codigo_whatsapp(telefono, codigo)
        except ValueError:
            db.session.execute(
                text("DELETE FROM auth_cobrador_challenges WHERE cobrador_id = :id"),
                {"id": cobrador["id"]},
            )
            db.session.commit()
            raise

        flash("Enviamos un código a tu WhatsApp. Tenés 10 minutos para completar el registro.", "success")
        return render_template(
            "registro_cobrador_confirmar.html",
            username=username,
            telefono=telefono,
        )
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "warning")
        return redirect(url_for("auth.registro"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("No se pudo iniciar el registro de un cobrador")
        flash("No se pudo iniciar el registro. Inténtelo nuevamente.", "danger")
        return redirect(url_for("auth.registro"))


@auth_bp.route("/registro/confirmar", methods=["POST"])
def registro_confirmar():
    try:
        username = _normalizar_usuario(request.form.get("username", ""))
        telefono = request.form.get("telefono", "").strip()
        codigo = request.form.get("codigo", "").strip()
        password = request.form.get("password", "")
        confirmar_password = request.form.get("confirmar_password", "")

        if not re.fullmatch(r"\d{6}", codigo):
            raise ValueError("Ingresá el código de seis números recibido por WhatsApp.")
        if len(password) < 10:
            raise ValueError("La clave debe tener al menos 10 caracteres.")
        if password != confirmar_password:
            raise ValueError("Las claves no coinciden.")

        cobrador = _buscar_cobrador_por_telefono(telefono)
        if not cobrador or cobrador["username"]:
            raise ValueError("No se pudo validar el registro. Volvé a solicitar un código.")

        desafio = db.session.execute(text("""
            SELECT username, codigo_hash, expira_en, reintentos
            FROM auth_cobrador_challenges
            WHERE cobrador_id = :cobrador_id
            FOR UPDATE;
        """), {"cobrador_id": cobrador["id"]}).mappings().first()
        if not desafio or desafio["username"] != username:
            raise ValueError("El código no es válido. Volvé a solicitarlo.")
        if desafio["expira_en"] <= datetime.now(timezone.utc):
            db.session.execute(text("""
                DELETE FROM auth_cobrador_challenges WHERE cobrador_id = :id;
            """), {"id": cobrador["id"]})
            db.session.commit()
            raise ValueError("El código venció. Volvé a solicitar uno nuevo.")
        if desafio["reintentos"] >= 5:
            db.session.execute(text("""
                DELETE FROM auth_cobrador_challenges WHERE cobrador_id = :id;
            """), {"id": cobrador["id"]})
            db.session.commit()
            raise ValueError("Se superó la cantidad de intentos. Volvé a solicitar un código.")
        if not hmac.compare_digest(
            desafio["codigo_hash"], _hash_codigo(cobrador["id"], codigo)
        ):
            db.session.execute(text("""
                UPDATE auth_cobrador_challenges
                SET reintentos = reintentos + 1
                WHERE cobrador_id = :id;
            """), {"id": cobrador["id"]})
            db.session.commit()
            raise ValueError("El código ingresado no es correcto.")

        db.session.execute(text("""
            UPDATE cobradores
            SET username = :username, password = :password
            WHERE id = :id AND username IS NULL
              AND habilitado IS TRUE AND rol = 'cobrador';
        """), {
            "username": username,
            "password": generate_password_hash(password),
            "id": cobrador["id"],
        })
        db.session.execute(text("""
            DELETE FROM auth_cobrador_challenges WHERE cobrador_id = :id;
        """), {"id": cobrador["id"]})
        db.session.commit()
        flash("Tu clave quedó creada. Ya podés ingresar con tu nombre de usuario.", "success")
        return redirect(url_for("auth.login"))
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "warning")
        return render_template(
            "registro_cobrador_confirmar.html",
            username=request.form.get("username", ""),
            telefono=request.form.get("telefono", ""),
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("No se pudo confirmar el registro de un cobrador")
        flash("No se pudo completar el registro. Volvé a solicitar un código.", "danger")
        return redirect(url_for("auth.registro"))


@auth_bp.route("/reset-password", methods=["POST"])
@admin_required
def reset_password():
    """Resetea la contraseña de un usuario administrador en Supabase Auth."""
    try:
        data = request.get_json(silent=True) or request.form
        email = (data.get("email") or "").strip().lower()
        new_password = data.get("password") or ""

        if not email or not new_password:
            return jsonify({"ok": False, "error": "Email y nueva contraseña son obligatorios."}), 400

        # 1. Buscar el usuario por email
        users = supabase_admin.auth.admin.list_users()
        target = None
        for u in (users or []):
            if u.email and u.email.lower() == email:
                target = u
                break

        if not target:
            return jsonify({"ok": False, "error": "Usuario no encontrado."}), 404

        # 2. Actualizar la contraseña (Supabase la hashea automaticamente)
        supabase_admin.auth.admin.update_user_by_id(target.id, {
            "email": email,
            "password": new_password,
            "email_confirm": True,
        })

        # 3. Actualizar el hash en la tabla cobradores
        cobradores = db.session.execute(
            text("SELECT id, password FROM cobradores WHERE email = :email"),
            {"email": email},
        ).mappings().all()
        for c in cobradores:
            db.session.execute(
                text("UPDATE cobradores SET password = :p WHERE id = :id"),
                {"p": generate_password_hash(new_password), "id": c["id"]},
            )
        db.session.commit()

        return jsonify({"ok": True, "message": "Contraseña actualizada correctamente."}), 200

    except Exception:
        db.session.rollback()
        current_app.logger.exception("No se pudo restablecer la contraseña")
        return jsonify({"ok": False, "error": "No se pudo restablecer la contraseña. Inténtelo nuevamente."}), 400
