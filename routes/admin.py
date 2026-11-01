from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import text
from werkzeug.security import generate_password_hash
import os
from datetime import datetime
from supabase_client import supabase, supabase_admin
from auth_manager import login_required, verificar_o_refrescar_token
from config import (
    UPLOAD_FOLDER, NOVEDADES_UPLOAD_FOLDER, DOCUMENTOS_UPLOAD_FOLDER, FOTOS_PORTAL_UPLOAD_FOLDER,
    EXTENSIONES_PERMITIDAS, EXTENSIONES_DOCUMENTOS, cargar_config, guardar_config,
    archivo_permitido, documento_permitido,
)
from models import db

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/cobradores", methods=["POST"])
@login_required
def cobradores():
    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not nombre or not email or not password:
        flash("Nombre, correo y contraseña son obligatorios para dar de alta.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    existing = db.session.execute(
        text("SELECT id FROM cobradores WHERE LOWER(email) = :email"),
        {"email": email},
    ).first()
    if existing:
        flash("Ya existe un cobrador con ese correo electrónico.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    db.session.execute(text("""
        INSERT INTO cobradores (nombre, apellido, email, password)
        VALUES (:nombre, :apellido, :email, :password)
    """), {
        "nombre": nombre,
        "apellido": apellido,
        "email": email,
        "password": generate_password_hash(password),
    })
    db.session.commit()
    flash("Cobrador dado de alta correctamente.", "success")
    return redirect(url_for("admin.cobradores_list"))


@admin_bp.route("/cobradores")
@login_required
def cobradores_list():
    """Lista los cobradores registrados."""
    cobradores = db.session.execute(text("""
        SELECT id, nombre, apellido, email, (password IS NOT NULL) AS activo
        FROM cobradores
        ORDER BY nombre, apellido;
    """)).mappings().all()
    return render_template("cobradores.html", cobradores=cobradores)


@admin_bp.route("/cobradores/<int:cid>/editar", methods=["POST"])
@login_required
def editar_cobrador(cid):
    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not nombre or not email:
        flash("El nombre y el correo electrónico son obligatorios.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    cobrador = db.session.execute(
        text("SELECT id FROM cobradores WHERE id = :id"),
        {"id": cid},
    ).first()
    if not cobrador:
        flash("No se encontró el cobrador que desea modificar.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    email_repetido = db.session.execute(text("""
        SELECT id FROM cobradores
        WHERE LOWER(email) = :email AND id <> :id;
    """), {"email": email, "id": cid}).first()
    if email_repetido:
        flash("Otro cobrador ya utiliza ese correo electrónico.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    if password:
        db.session.execute(text("""
            UPDATE cobradores
            SET nombre = :nombre, apellido = :apellido, email = :email, password = :password
            WHERE id = :id;
        """), {
            "nombre": nombre,
            "apellido": apellido,
            "email": email,
            "password": generate_password_hash(password),
            "id": cid,
        })
    else:
        db.session.execute(text("""
            UPDATE cobradores
            SET nombre = :nombre, apellido = :apellido, email = :email
            WHERE id = :id;
        """), {"nombre": nombre, "apellido": apellido, "email": email, "id": cid})
    db.session.commit()
    flash("Datos del cobrador actualizados correctamente.", "success")
    return redirect(url_for("admin.cobradores_list"))


@admin_bp.route("/cobradores/<int:cid>/baja", methods=["POST"])
@login_required
def baja_cobrador(cid):
    """Da de baja (desactiva) un cobrador."""
    result = db.session.execute(
        text("UPDATE cobradores SET password = NULL WHERE id = :id AND password IS NOT NULL"),
        {"id": cid},
    )
    db.session.commit()
    flash(
        "Cobrador dado de baja correctamente." if result.rowcount else "El cobrador ya estaba dado de baja.",
        "info",
    )
    return redirect(url_for("admin.cobradores_list"))


@admin_bp.route("/configuracion", methods=["GET", "POST"])
@login_required
def configuracion():
    config = cargar_config()
    config.setdefault("institucion", {})
    config.setdefault("autoridades", {})
    config.setdefault("reglas_negocio", {})
    config.setdefault("actividades", {})

    if request.method == "POST":
        if "logo" in request.files:
            archivo = request.files["logo"]
            if archivo and archivo.filename != "" and archivo_permitido(archivo.filename):
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                ext = archivo.filename.rsplit(".", 1)[1].lower()
                nombre_archivo = f"logo_institucional.{ext}"
                archivo.save(os.path.join(UPLOAD_FOLDER, nombre_archivo))
                config["institucion"]["logo"] = nombre_archivo

        config["institucion"]["nombre"] = request.form.get("nombre", "").strip()
        config["institucion"]["subtitulo"] = request.form.get("subtitulo", "").strip()
        config["institucion"]["cuit"] = request.form.get("cuit", "").strip()
        config["institucion"]["direccion"] = request.form.get("direccion", "").strip()
        config["institucion"]["ciudad_provincia"] = request.form.get("ciudad_provincia", "").strip()
        config["institucion"]["telefono"] = request.form.get("telefono", "").strip()
        config["institucion"]["email"] = request.form.get("email", "").strip()

        config["autoridades"]["presidente"] = request.form.get("presidente", "").strip()
        config["autoridades"]["secretario"] = request.form.get("secretario", "").strip()
        config["autoridades"]["tesorero"] = request.form.get("tesorero", "").strip()

        config["reglas_negocio"]["descripcion_general"] = request.form.get("descripcion_general", "").strip()
        config["reglas_negocio"]["politica_anticipada"] = request.form.get("politica_anticipada", "").strip()
        config["reglas_negocio"]["valor_cuota_mensual"] = float(request.form.get("valor_cuota_mensual", 0) or 0)
        config["reglas_negocio"]["valor_anual_promocional"] = float(request.form.get("valor_anual_promocional", 0) or 0)
        config["reglas_negocio"]["valor_anual_estandar"] = float(request.form.get("valor_anual_estandar", 0) or 0)
        config["reglas_negocio"]["valor_inscripcion"] = float(request.form.get("valor_inscripcion", 0) or 0)

        config["actividades"]["gimnasia"] = request.form.get("gimnasia", "").strip()
        config["actividades"]["bingo"] = request.form.get("bingo", "").strip()
        config["actividades"]["festejos"] = request.form.get("festejos", "").strip()

        guardar_config(config)
        flash("Parámetros actualizados correctamente.", "success")
        return redirect(url_for("admin.configuracion"))

    return render_template("configuracion.html", cfg=config)


@admin_bp.route("/novedades", methods=["GET"])
@login_required
def listar_novedades():
    sql = """
        SELECT id, titulo, contenido, imagen, fecha_publicacion, activa, orden
        FROM novedades
        ORDER BY orden DESC, fecha_publicacion DESC;
    """
    novedades = db.session.execute(text(sql)).mappings().all()
    return render_template("novedades_listar.html", novedades=novedades)


@admin_bp.route("/novedades/nueva", methods=["POST"])
@login_required
def novedades_nueva():
    titulo = request.form.get("titulo", "").strip()
    contenido = request.form.get("contenido", "").strip()
    activa = request.form.get("activa") == "on"
    orden = int(request.form.get("orden", "0") or 0)
    imagen_nombre = None

    if "imagen" in request.files:
        archivo = request.files["imagen"]
        if archivo and archivo.filename != "" and archivo_permitido(archivo.filename):
            os.makedirs(NOVEDADES_UPLOAD_FOLDER, exist_ok=True)
            ext = archivo.filename.rsplit(".", 1)[1].lower()
            nombre_archivo = f"novedad_{int(datetime.now().timestamp())}.{ext}"
            archivo.save(os.path.join(NOVEDADES_UPLOAD_FOLDER, nombre_archivo))
            imagen_nombre = nombre_archivo

    if not titulo:
        flash("El título es obligatorio.", "warning")
        return redirect(url_for("admin.listar_novedades"))

    db.session.execute(text("""
        INSERT INTO novedades (titulo, contenido, activa, orden, imagen, fecha_publicacion)
        VALUES (:titulo, :contenido, :activa, :orden, :imagen, NOW());
    """), {"titulo": titulo, "contenido": contenido, "activa": activa, "orden": orden, "imagen": imagen_nombre})
    db.session.commit()
    flash("Novedad creada correctamente.", "success")
    return redirect(url_for("admin.listar_novedades"))


@admin_bp.route("/novedades/editar/<int:id>", methods=["POST"])
@login_required
def novedades_editar(id):
    titulo = request.form.get("titulo", "").strip()
    contenido = request.form.get("contenido", "").strip()
    activa = request.form.get("activa") == "on"
    orden = int(request.form.get("orden", "0") or 0)

    if not titulo:
        flash("El título es obligatorio.", "warning")
        return redirect(url_for("admin.listar_novedades"))

    imagen_nombre = None
    if "imagen" in request.files:
        archivo = request.files["imagen"]
        if archivo and archivo.filename != "" and archivo_permitido(archivo.filename):
            os.makedirs(NOVEDADES_UPLOAD_FOLDER, exist_ok=True)
            ext = archivo.filename.rsplit(".", 1)[1].lower()
            nombre_archivo = f"novedad_{int(datetime.now().timestamp())}.{ext}"
            archivo.save(os.path.join(NOVEDADES_UPLOAD_FOLDER, nombre_archivo))
            imagen_nombre = nombre_archivo

    if imagen_nombre:
        db.session.execute(text("""
            UPDATE novedades
            SET titulo = :titulo, contenido = :contenido, activa = :activa, orden = :orden, imagen = :imagen
            WHERE id = :id;
        """), {"titulo": titulo, "contenido": contenido, "activa": activa, "orden": orden, "imagen": imagen_nombre, "id": id})
    else:
        db.session.execute(text("""
            UPDATE novedades
            SET titulo = :titulo, contenido = :contenido, activa = :activa, orden = :orden
            WHERE id = :id;
        """), {"titulo": titulo, "contenido": contenido, "activa": activa, "orden": orden, "id": id})
    db.session.commit()
    flash("Novedad actualizada correctamente.", "success")
    return redirect(url_for("admin.listar_novedades"))


@admin_bp.route("/novedades/eliminar/<int:id>", methods=["POST"])
@login_required
def novedades_eliminar(id):
    activar = request.form.get("activar") == "1"
    db.session.execute(text("UPDATE novedades SET activa = :activa WHERE id = :id;"), {"activa": activar, "id": id})
    db.session.commit()
    flash("Estado de novedad actualizado.", "success")
    return redirect(url_for("admin.listar_novedades"))


@admin_bp.route("/archivos-portal", methods=["GET"])
@login_required
def listar_archivos_portal():
    sql = """
        SELECT id, titulo, descripcion, tipo, archivo, fecha_subida, activa, orden
        FROM archivos_portal
        ORDER BY tipo, orden DESC, fecha_subida DESC;
    """
    archivos = db.session.execute(text(sql)).mappings().all()
    return render_template("archivos_portal.html", archivos=archivos)


@admin_bp.route("/archivos-portal/nueva", methods=["POST"])
@login_required
def archivos_portal_nueva():
    MAX_FILE_SIZE = 10 * 1024 * 1024
    titulo = request.form.get("titulo", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    tipo = request.form.get("tipo", "").strip()
    activa = request.form.get("activa") == "on"
    orden = int(request.form.get("orden", "0") or 0)

    if not titulo or not tipo or "archivo" not in request.files:
        flash("Datos incompletos o archivo no seleccionado.", "warning")
        return redirect(url_for("admin.listar_archivos_portal"))

    archivo = request.files["archivo"]
    if not archivo or archivo.filename == "":
        flash("No se recibió ningún archivo válido.", "warning")
        return redirect(url_for("admin.listar_archivos_portal"))

    ext = archivo.filename.rsplit(".", 1)[1].lower() if "." in archivo.filename else ""
    if tipo == "foto" and ext not in EXTENSIONES_PERMITIDAS:
        flash("Para fotos use formatos: JPG, PNG, WEBP, SVG.", "warning")
        return redirect(url_for("admin.listar_archivos_portal"))
    elif tipo in ("estatuto", "memoria_balance") and ext not in EXTENSIONES_DOCUMENTOS:
        flash("Para documentos use formato PDF o Word.", "warning")
        return redirect(url_for("admin.listar_archivos_portal"))

    archivo.seek(0, 2)
    file_size = archivo.tell()
    archivo.seek(0)
    if file_size > MAX_FILE_SIZE:
        flash("El archivo supera el límite de 10 MB.", "warning")
        return redirect(url_for("admin.listar_archivos_portal"))

    carpeta = DOCUMENTOS_UPLOAD_FOLDER if tipo in ("estatuto", "memoria_balance") else FOTOS_PORTAL_UPLOAD_FOLDER
    os.makedirs(carpeta, exist_ok=True)
    nombre_archivo = f"portal_{tipo}_{int(datetime.now().timestamp())}.{ext}"
    ruta_destino = os.path.join(carpeta, nombre_archivo)

    try:
        archivo.save(ruta_destino)
        db.session.execute(text("""
            INSERT INTO archivos_portal (titulo, descripcion, tipo, archivo, activa, orden, fecha_subida)
            VALUES (:titulo, :descripcion, :tipo, :archivo, :activa, :orden, NOW());
        """), {"titulo": titulo, "descripcion": descripcion, "tipo": tipo, "archivo": nombre_archivo, "activa": activa, "orden": orden})
        db.session.commit()
        flash("Archivo subido correctamente al portal.", "success")
    except Exception as e:
        db.session.rollback()
        if os.path.exists(ruta_destino):
            os.remove(ruta_destino)
        flash(f"Error al guardar el archivo: {str(e)}", "danger")

    return redirect(url_for("admin.listar_archivos_portal"))


@admin_bp.route("/archivos-portal/eliminar/<int:id>", methods=["POST"])
@login_required
def archivos_portal_eliminar(id):
    activar = request.form.get("activar") == "1"
    db.session.execute(text("UPDATE archivos_portal SET activa = :activa WHERE id = :id;"), {"activa": activar, "id": id})
    db.session.commit()
    flash("Estado del archivo actualizado correctamente.", "success")
    return redirect(url_for("admin.listar_archivos_portal"))


@admin_bp.route("/archivos-portal/editar/<int:id>", methods=["GET", "POST"])
@login_required
def archivos_portal_editar(id):
    archivo = db.session.execute(text("SELECT * FROM archivos_portal WHERE id = :id;"), {"id": id}).mappings().first()
    if not archivo:
        flash("Archivo no encontrado.", "warning")
        return redirect(url_for("admin.listar_archivos_portal"))

    if request.method == "POST":
        titulo = request.form.get("titulo", archivo.get("titulo") or "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        tipo = request.form.get("tipo", archivo.get("tipo") or "").strip()
        activa = str(request.form.get("activa")) == "on"
        imagen_nombre = archivo.get("archivo")
        f = request.files.get("archivo")
        if f and f.filename:
            ext = f.filename.rsplit(".", 1)[1].lower() if "." in f.filename else ""
            if tipo == "foto" and ext not in EXTENSIONES_PERMITIDAS:
                flash("Para fotos use formatos: JPG, PNG, WEBP, SVG.", "warning")
                return redirect(url_for("admin.listar_archivos_portal"))
            if tipo in ("estatuto", "memoria_balance") and ext not in EXTENSIONES_DOCUMENTOS:
                flash("Para documentos use formato PDF o Word.", "warning")
                return redirect(url_for("admin.listar_archivos_portal"))
            carpeta = DOCUMENTOS_UPLOAD_FOLDER if tipo in ("estatuto", "memoria_balance") else FOTOS_PORTAL_UPLOAD_FOLDER
            os.makedirs(carpeta, exist_ok=True)
            imagen_nombre = f"portal_{tipo}_{int(datetime.now().timestamp())}.{ext}"
            f.save(os.path.join(carpeta, imagen_nombre))
        db.session.execute(text("""
            UPDATE archivos_portal
            SET titulo = :titulo, descripcion = :descripcion, tipo = :tipo, archivo = :archivo, activa = :activa
            WHERE id = :id;
        """), {"titulo": titulo, "descripcion": descripcion, "tipo": tipo, "archivo": imagen_nombre, "activa": activa, "id": id})
        db.session.commit()
        flash("Archivo actualizado correctamente.", "success")
        return redirect(url_for("admin.listar_archivos_portal"))

    return render_template("editar_archivo_portal.html", archivo=archivo)
