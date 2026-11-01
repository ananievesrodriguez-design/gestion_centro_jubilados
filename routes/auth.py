from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from supabase_client import supabase, supabase_admin
from auth_manager import login_required, verificar_o_refrescar_token
from models import db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("access_token") and verificar_o_refrescar_token():
        return redirect(url_for("socios.listar_socios"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Por favor ingresa tu correo y contraseña.", "warning")
            return render_template("login.html")

        try:
            # Login seguro contra Supabase Auth
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            # Guardar tokens y claims en la sesión segura del servidor
            session["access_token"] = response.session.access_token
            session["refresh_token"] = response.session.refresh_token
            session["user"] = {
                "id": response.user.id,
                "email": response.user.email,
                "nombre": response.user.user_metadata.get("nombre", email),
                "role": response.user.app_metadata.get("role", "admin")
            }

            flash(f"¡Bienvenido/a, {session['user']['nombre']}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("socios.listar_socios"))

        except Exception as e:
            flash("Credenciales incorrectas o usuario no autorizado.", "danger")
            return render_template("login.html")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    session.clear()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/registro", methods=["POST"])
def registro():
    """Registra un nuevo usuario administrador en Supabase Auth y lo vincula en la tabla cobradores."""
    try:
        data = request.get_json(silent=True) or request.form
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        nombre = (data.get("nombre") or "").strip()
        apellido = (data.get("apellido") or "").strip()

        if not email or not password or not nombre:
            return jsonify({"ok": False, "error": "Email, contraseña y nombre son obligatorios."}), 400

        # 1. Crear el usuario en Supabase Auth (la contraseña queda hasheada por Supabase)
        user = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })

        # 2. Guardar hash de la contraseña en la tabla cobradores
        password_hash = generate_password_hash(password)

        # 3. Vincular el registro en la tabla cobradores
        db.session.execute(text("""
            INSERT INTO cobradores (nombre, apellido, email, password)
            VALUES (:nombre, :apellido, :email, :password)
        """), {
            "nombre": nombre,
            "apellido": apellido,
            "email": email,
            "password": password_hash,
        })
        db.session.commit()

        return jsonify({"ok": True, "user": {"id": user.user.id, "email": email}}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400


@auth_bp.route("/reset-password", methods=["POST"])
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

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
