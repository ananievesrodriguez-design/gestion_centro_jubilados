from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import text
from werkzeug.security import generate_password_hash
import os
from datetime import datetime
from auth_manager import admin_required, login_required
from config import (
    UPLOAD_FOLDER, NOVEDADES_UPLOAD_FOLDER, DOCUMENTOS_UPLOAD_FOLDER, FOTOS_PORTAL_UPLOAD_FOLDER,
    EXTENSIONES_PERMITIDAS, EXTENSIONES_DOCUMENTOS, cargar_config, guardar_config,
    archivo_permitido, documento_permitido, WHATSAPP_NEWS_TEMPLATE,
)
from models import db
from whatsapp_service import whatsapp_template_configured

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/cobradores", methods=["POST"])
@admin_required
def cobradores():
    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    username = request.form.get("username", "").strip().casefold()
    socio_id = request.form.get("socio_id", "").strip()
    rol = request.form.get("rol", "cobrador")
    if rol not in {"cobrador", "admin", "superadmin"}:
        flash("Seleccione un rol válido.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    if not nombre or not 3 <= len(username) <= 40 or not all(
        caracter.isalnum() or caracter in "._-" for caracter in username
    ):
        flash("Ingresá el nombre y un usuario de 3 a 40 caracteres, sin espacios.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    if len(password) < 8:
        flash("La clave debe tener al menos 8 caracteres.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    if rol == "cobrador" and not socio_id.isdigit():
        flash("Seleccioná un socio activo para el cobrador.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    socio_id = int(socio_id) if socio_id.isdigit() else None

    if socio_id is not None:
        socio = db.session.execute(text("""
        SELECT id FROM socios
        WHERE id = :id AND LOWER(COALESCE(estado, 'Activo')) = 'activo';
        """), {"id": socio_id}).first()
        if not socio:
            flash("El socio vinculado debe estar activo.", "warning")
            return redirect(url_for("admin.cobradores_list"))

    existing = db.session.execute(text("""
        SELECT id FROM cobradores
        WHERE socio_id = :socio_id;
    """), {"socio_id": socio_id}).first() if socio_id is not None else None
    if existing:
        flash("Ese socio ya está vinculado a un cobrador.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    username_existente = db.session.execute(
        text("SELECT id FROM cobradores WHERE LOWER(username) = :username"),
        {"username": username},
    ).first()
    if username_existente:
        flash("Ese nombre de usuario ya está en uso.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    email_existente = db.session.execute(
        text("SELECT id FROM cobradores WHERE LOWER(email) = :email"),
        {"email": email},
    ).first() if email else None
    if email_existente:
        flash("Ya existe un cobrador con ese correo electrónico.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    db.session.execute(text("""
        INSERT INTO cobradores (
            nombre, apellido, email, username, password, socio_id, habilitado, rol
        )
        VALUES (
            :nombre, :apellido, :email, :username, :password, :socio_id, TRUE, :rol
        )
    """), {
        "nombre": nombre,
        "apellido": apellido,
        "email": email or None,
        "username": username,
        "password": generate_password_hash(password),
        "socio_id": socio_id,
        "rol": rol,
    })
    db.session.commit()
    flash("Usuario creado. Ya puede ingresar con su nombre de usuario y clave.", "success")
    return redirect(url_for("admin.cobradores_list"))


@admin_bp.route("/cobradores")
@admin_required
def cobradores_list():
    """Lista los cobradores registrados."""
    cobradores = db.session.execute(text("""
        SELECT c.id, c.nombre, c.apellido, c.email, c.username, c.socio_id, c.rol,
               s.nro_socio, s.estado AS estado_socio, c.habilitado AS activo
        FROM cobradores c
        LEFT JOIN socios s ON s.id = c.socio_id
        ORDER BY c.nombre, c.apellido;
    """)).mappings().all()
    socios_activos = db.session.execute(text("""
        SELECT id, nro_socio, apellido, nombre
        FROM socios
        WHERE LOWER(COALESCE(estado, 'Activo')) = 'activo'
        ORDER BY apellido, nombre;
    """)).mappings().all()
    return render_template(
        "cobradores.html",
        cobradores=cobradores,
        socios_activos=socios_activos,
    )


@admin_bp.route("/cobradores/<int:cid>/editar", methods=["POST"])
@admin_required
def editar_cobrador(cid):
    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    username = request.form.get("username", "").strip().casefold()
    socio_id = request.form.get("socio_id", "").strip()

    cobrador = db.session.execute(text("""
        SELECT id, rol, username FROM cobradores WHERE id = :id;
    """),
        {"id": cid},
    ).mappings().first()
    if not cobrador:
        flash("No se encontró el cobrador que desea modificar.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    username = username or cobrador["username"]
    rol = request.form.get("rol", cobrador["rol"])
    if rol not in {"cobrador", "admin", "superadmin"}:
        flash("Seleccione un rol válido.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    if not nombre:
        flash("El nombre es obligatorio.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    if username and (
        not 3 <= len(username) <= 40
        or not all(caracter.isalnum() or caracter in "._-" for caracter in username)
    ):
        flash("El usuario debe tener entre 3 y 40 caracteres, sin espacios.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    if password and len(password) < 8:
        flash("La clave debe tener al menos 8 caracteres.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    if rol == "cobrador" and not socio_id.isdigit():
        flash("Seleccioná un socio activo para el cobrador.", "warning")
        return redirect(url_for("admin.cobradores_list"))
    socio_id = int(socio_id) if socio_id.isdigit() else None

    if username:
        username_repetido = db.session.execute(text("""
            SELECT id FROM cobradores
            WHERE LOWER(username) = :username AND id <> :id;
        """), {"username": username, "id": cid}).first()
        if username_repetido:
            flash("Otro usuario ya utiliza ese nombre de usuario.", "warning")
            return redirect(url_for("admin.cobradores_list"))

    if socio_id is not None:
        socio = db.session.execute(text("""
        SELECT id FROM socios
        WHERE id = :id AND LOWER(COALESCE(estado, 'Activo')) = 'activo';
        """), {"id": socio_id}).first()
        if not socio:
            flash("El socio vinculado debe estar activo.", "warning")
            return redirect(url_for("admin.cobradores_list"))

    socio_repetido = db.session.execute(text("""
        SELECT id FROM cobradores
        WHERE socio_id = :socio_id AND id <> :id;
    """), {"socio_id": socio_id, "id": cid}).first() if socio_id is not None else None
    if socio_repetido:
        flash("Ese socio ya está vinculado a otro cobrador.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    email_repetido = db.session.execute(text("""
        SELECT id FROM cobradores
        WHERE LOWER(email) = :email AND id <> :id;
    """), {"email": email, "id": cid}).first() if email else None
    if email_repetido:
        flash("Otro cobrador ya utiliza ese correo electrónico.", "warning")
        return redirect(url_for("admin.cobradores_list"))

    if password:
        db.session.execute(text("""
            UPDATE cobradores
            SET nombre = :nombre, apellido = :apellido, email = :email,
                username = :username, password = :password, socio_id = :socio_id,
                habilitado = TRUE, rol = :rol
            WHERE id = :id;
        """), {
            "nombre": nombre,
            "apellido": apellido,
            "email": email or None,
            "username": username,
            "password": generate_password_hash(password),
            "socio_id": socio_id,
            "rol": rol,
            "id": cid,
        })
    else:
        db.session.execute(text("""
            UPDATE cobradores
            SET nombre = :nombre, apellido = :apellido, email = :email,
                username = :username, socio_id = :socio_id, rol = :rol
            WHERE id = :id;
        """), {
            "nombre": nombre,
            "apellido": apellido,
            "email": email or None,
            "username": username,
            "socio_id": socio_id,
            "rol": rol,
            "id": cid,
        })
    db.session.commit()
    flash("Datos del cobrador actualizados correctamente.", "success")
    return redirect(url_for("admin.cobradores_list"))


@admin_bp.route("/cobradores/<int:cid>/baja", methods=["POST"])
@admin_required
def baja_cobrador(cid):
    """Da de baja (desactiva) un cobrador."""
    result = db.session.execute(
        text("""
            UPDATE cobradores
            SET password = NULL, habilitado = FALSE
            WHERE id = :id AND habilitado IS TRUE;
        """),
        {"id": cid},
    )
    db.session.commit()
    flash(
        "Cobrador dado de baja correctamente." if result.rowcount else "El cobrador ya estaba dado de baja.",
        "info",
    )
    return redirect(url_for("admin.cobradores_list"))


@admin_bp.route("/configuracion", methods=["GET", "POST"])
@admin_required
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
@admin_required
def listar_novedades():
    sql = """
        SELECT n.id, n.titulo, n.contenido, n.imagen, n.fecha_publicacion, n.activa, n.orden,
               (SELECT COUNT(*) FROM whatsapp_envios w
                WHERE w.tipo = 'novedad' AND w.referencia = n.id::text
                  AND w.estado = 'pendiente') AS whatsapp_pendientes,
               (SELECT COUNT(*) FROM whatsapp_envios w
                WHERE w.tipo = 'novedad' AND w.referencia = n.id::text
                  AND w.estado = 'enviado') AS whatsapp_enviados,
               (SELECT COUNT(*) FROM whatsapp_envios w
                WHERE w.tipo = 'novedad' AND w.referencia = n.id::text
                  AND w.estado = 'fallido') AS whatsapp_fallidos
        FROM novedades n
        ORDER BY orden DESC, fecha_publicacion DESC;
    """
    novedades = db.session.execute(text(sql)).mappings().all()
    return render_template(
        "novedades_listar.html",
        novedades=novedades,
        whatsapp_configurado=whatsapp_template_configured(WHATSAPP_NEWS_TEMPLATE),
    )


@admin_bp.route("/novedades/enviar", methods=["GET", "POST"])
@login_required
def enviar_novedad_cobrador():
    if session.get("user", {}).get("role") != "cobrador":
        return redirect(url_for("admin.listar_novedades"))
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        contenido = request.form.get("contenido", "").strip()
        if not titulo or len(titulo) > 200 or len(contenido) > 10000:
            flash("El título es obligatorio (máximo 200 caracteres) y el texto no puede superar 10.000 caracteres.", "warning")
            return render_template("novedad_cobrador.html")

        db.session.execute(text("""
            INSERT INTO novedades (titulo, contenido, activa, orden, fecha_publicacion)
            VALUES (:titulo, :contenido, FALSE, 0, NOW());
        """), {"titulo": titulo, "contenido": contenido})
        db.session.commit()
        flash("La novedad fue enviada a la administración para su revisión.", "success")
        return redirect(url_for("socios.inicio_cobrador"))
    return render_template("novedad_cobrador.html")


@admin_bp.route("/novedades/nueva", methods=["POST"])
@admin_required
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


@admin_bp.route("/novedades/<int:id>/enviar-whatsapp", methods=["POST"])
@admin_required
def enviar_novedad_whatsapp(id):
    novedad = db.session.execute(text("""
        SELECT id, titulo, contenido
        FROM novedades
        WHERE id = :id AND activa IS TRUE;
    """), {"id": id}).mappings().first()
    if not novedad:
        flash("Solo se pueden enviar novedades activas.", "warning")
        return redirect(url_for("admin.listar_novedades"))
    if not whatsapp_template_configured(WHATSAPP_NEWS_TEMPLATE):
        flash("Configure WhatsApp y la plantilla aprobada para novedades.", "warning")
        return redirect(url_for("admin.listar_novedades"))
    if len(novedad["titulo"]) > 200 or len(novedad["contenido"] or "") > 1000:
        flash("Para WhatsApp, el título debe tener hasta 200 caracteres y el texto hasta 1.000.", "warning")
        return redirect(url_for("admin.listar_novedades"))

    destinatarios = db.session.execute(text("""
        SELECT COUNT(*)
        FROM socios
        WHERE whatsapp_autorizado IS TRUE
          AND telefono IS NOT NULL
          AND LENGTH(regexp_replace(telefono, '[^0-9]', '', 'g')) BETWEEN 11 AND 15
          AND regexp_replace(telefono, '[^0-9]', '', 'g') LIKE '54%'
          AND LOWER(COALESCE(estado, 'activo')) IN ('activo', 'vitalicio');
    """)).scalar_one()
    if not destinatarios:
        flash("No hay socios activos con teléfono internacional y autorización de WhatsApp.", "warning")
        return redirect(url_for("admin.listar_novedades"))

    result = db.session.execute(text("""
        INSERT INTO whatsapp_envios (
            socio_id, tipo, referencia, telefono, parametro_1, parametro_2
        )
        SELECT id, 'novedad', :referencia,
               regexp_replace(telefono, '[^0-9]', '', 'g'), :titulo, :contenido
        FROM socios
        WHERE whatsapp_autorizado IS TRUE
          AND telefono IS NOT NULL
          AND LENGTH(regexp_replace(telefono, '[^0-9]', '', 'g')) BETWEEN 11 AND 15
          AND regexp_replace(telefono, '[^0-9]', '', 'g') LIKE '54%'
          AND LOWER(COALESCE(estado, 'activo')) IN ('activo', 'vitalicio')
        ON CONFLICT (socio_id, tipo, referencia) DO UPDATE
        SET estado = 'pendiente', error = NULL, actualizado_en = NOW()
        WHERE whatsapp_envios.estado = 'fallido';
    """), {
        "referencia": str(novedad["id"]),
        "titulo": novedad["titulo"],
        "contenido": novedad["contenido"] or "",
    })
    db.session.commit()
    if result.rowcount:
        flash(
            f"Novedad puesta en cola para {result.rowcount} socio(s). "
            "El hosting la enviará en el próximo proceso programado.",
            "success",
        )
    else:
        flash("Esta novedad ya fue enviada o está en cola para todos los socios autorizados.", "info")
    return redirect(url_for("admin.listar_novedades"))


@admin_bp.route("/novedades/editar/<int:id>", methods=["POST"])
@admin_required
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
@admin_required
def novedades_eliminar(id):
    activar = request.form.get("activar") == "1"
    db.session.execute(text("UPDATE novedades SET activa = :activa WHERE id = :id;"), {"activa": activar, "id": id})
    db.session.commit()
    flash("Estado de novedad actualizado.", "success")
    return redirect(url_for("admin.listar_novedades"))


@admin_bp.route("/archivos-portal", methods=["GET"])
@admin_required
def listar_archivos_portal():
    sql = """
        SELECT id, titulo, descripcion, tipo, archivo, fecha_subida, activa, orden
        FROM archivos_portal
        ORDER BY tipo, orden DESC, fecha_subida DESC;
    """
    archivos = db.session.execute(text(sql)).mappings().all()
    return render_template("archivos_portal.html", archivos=archivos)


@admin_bp.route("/archivos-portal/nueva", methods=["POST"])
@admin_required
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
    except Exception:
        db.session.rollback()
        if os.path.exists(ruta_destino):
            os.remove(ruta_destino)
        current_app.logger.exception("No se pudo guardar el archivo del portal")
        flash("No se pudo guardar el archivo. Verifique el archivo e inténtelo nuevamente.", "danger")

    return redirect(url_for("admin.listar_archivos_portal"))


@admin_bp.route("/archivos-portal/eliminar/<int:id>", methods=["POST"])
@admin_required
def archivos_portal_eliminar(id):
    activar = request.form.get("activar") == "1"
    db.session.execute(text("UPDATE archivos_portal SET activa = :activa WHERE id = :id;"), {"activa": activar, "id": id})
    db.session.commit()
    flash("Estado del archivo actualizado correctamente.", "success")
    return redirect(url_for("admin.listar_archivos_portal"))


@admin_bp.route("/archivos-portal/editar/<int:id>", methods=["GET", "POST"])
@admin_required
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
