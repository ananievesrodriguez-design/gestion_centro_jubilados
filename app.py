import json
import os
from datetime import date
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "clave_secreta_centro_123")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["ADMIN_PASSWORD"] = os.getenv("ADMIN_PASSWORD", "centro2026")

db = SQLAlchemy(app)

# --- Inicializar tabla de novedades (se ejecuta una vez al arrancar) ---
with app.app_context():
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS novedades (
            id SERIAL PRIMARY KEY,
            titulo VARCHAR(200) NOT NULL,
            contenido TEXT,
            imagen VARCHAR(255),
            fecha_publicacion TIMESTAMP DEFAULT NOW(),
            activa BOOLEAN DEFAULT TRUE,
            orden INT DEFAULT 0
        );
    """))
    db.session.execute(text("""
        ALTER TABLE novedades ADD COLUMN IF NOT EXISTS imagen VARCHAR(255);
    """))
    # --- Tabla de archivos del portal (estatuto, memoria, fotos) ---
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS archivos_portal (
            id SERIAL PRIMARY KEY,
            titulo VARCHAR(200) NOT NULL,
            descripcion TEXT,
            tipo VARCHAR(50) NOT NULL,  -- 'estatuto', 'memoria_balance', 'foto'
            archivo VARCHAR(255) NOT NULL,
            fecha_subida TIMESTAMP DEFAULT NOW(),
            activa BOOLEAN DEFAULT TRUE,
            orden INT DEFAULT 0
        );
    """))
    db.session.commit()
###CONFIGURACION
import json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_institucion.json")

def cargar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_config(datos):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

# Inyector global: 'INSTITUCION' y 'CONFIG' quedan disponibles en todos los HTML
@app.context_processor
def inject_institucion():
    config = cargar_config()
    return {
        "INSTITUCION": config.get("institucion", {}),
        "CONFIG": config
    }

# Ruta para ver y actualizar la configuración
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "img")
NOVEDADES_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "novedades")
DOCUMENTOS_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "documentos")
FOTOS_PORTAL_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "fotos_portal")
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "svg"}
EXTENSIONES_DOCUMENTOS = {"pdf", "doc", "docx"}

def archivo_permitido(nombre):
    return "." in nombre and nombre.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS

def documento_permitido(nombre):
    return "." in nombre and nombre.rsplit(".", 1)[1].lower() in EXTENSIONES_DOCUMENTOS

@app.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    config = cargar_config()
    
    # Asegurar claves base por si el JSON no las tiene
    if "institucion" not in config:
        config["institucion"] = {}
    if "autoridades" not in config:
        config["autoridades"] = {}
    if "reglas_negocio" not in config:
        config["reglas_negocio"] = {}
    if "actividades" not in config:
        config["actividades"] = {}

    if request.method == "POST":
        # 1. Procesar subida del logo
        if "logo" in request.files:
            archivo = request.files["logo"]
            if archivo and archivo.filename != "" and archivo_permitido(archivo.filename):
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                extension = archivo.filename.rsplit(".", 1)[1].lower()
                nombre_archivo = f"logo_institucional.{extension}"
                ruta_destino = os.path.join(UPLOAD_FOLDER, nombre_archivo)
                archivo.save(ruta_destino)
                config["institucion"]["logo"] = nombre_archivo

        # 2. Datos institucionales
        config["institucion"]["nombre"] = request.form.get("nombre", "").strip()
        config["institucion"]["subtitulo"] = request.form.get("subtitulo", "").strip()
        config["institucion"]["cuit"] = request.form.get("cuit", "").strip()
        config["institucion"]["direccion"] = request.form.get("direccion", "").strip()
        config["institucion"]["ciudad_provincia"] = request.form.get("ciudad_provincia", "").strip()
        config["institucion"]["telefono"] = request.form.get("telefono", "").strip()
        config["institucion"]["email"] = request.form.get("email", "").strip()

        # 3. Autoridades
        config["autoridades"]["presidente"] = request.form.get("presidente", "").strip()
        config["autoridades"]["secretario"] = request.form.get("secretario", "").strip()
        config["autoridades"]["tesorero"] = request.form.get("tesorero", "").strip()

        # 4. Reglas de negocio
        config["reglas_negocio"]["descripcion_general"] = request.form.get("descripcion_general", "").strip()
        config["reglas_negocio"]["politica_anticipada"] = request.form.get("politica_anticipada", "").strip()
        config["reglas_negocio"]["valor_cuota_mensual"] = float(request.form.get("valor_cuota_mensual", 0) or 0)
        config["reglas_negocio"]["valor_anual_promocional"] = float(request.form.get("valor_anual_promocional", 0) or 0)
        config["reglas_negocio"]["valor_anual_estandar"] = float(request.form.get("valor_anual_estandar", 0) or 0)
        config["reglas_negocio"]["valor_inscripcion"] = float(request.form.get("valor_inscripcion", 0) or 0)

        # 5. Actividades
        config["actividades"]["gimnasia"] = request.form.get("gimnasia", "").strip()
        config["actividades"]["bingo"] = request.form.get("bingo", "").strip()
        config["actividades"]["festejos"] = request.form.get("festejos", "").strip()

        guardar_config(config)
        flash("Parámetros del Centro de Jubilados y logo actualizados correctamente.", "success")
        return redirect(url_for("configuracion"))

    return render_template("configuracion.html", cfg=config)

###FIN CONFIGURACION
# --- Modelos ---
class Socio(db.Model):
    __tablename__ = "socios"
    id = db.Column(db.Integer, primary_key=True)
    nro_socio = db.Column(db.Integer)
    dni = db.Column(db.String(15), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(30), default="Activo")

class Cobrador(db.Model):
    __tablename__ = "cobradores"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100))
    activo = db.Column(db.Boolean, default=True)

# --- Rutas ---
#RUTA PORTAL SOCIOS
from datetime import date, datetime
from sqlalchemy import text

@app.route("/", methods=["GET", "POST"])
def portal_socios():
    socio_encontrado = None
    cuotas_socio = []
    ultimo_pago = None
    busqueda_realizada = False
    termino_busqueda = ""
    es_cumpleanos_hoy = False
    es_mes_cumpleanos = False

    # 1. Cargar configuración institucional
    config = cargar_config()
    comision = config.get("comision_directiva", [])

    hoy = date.today()

    # 2. Novedades activas (para mostrar en el portal)
    sql_novedades = """
        SELECT id, titulo, contenido, imagen, fecha_publicacion
        FROM novedades
        WHERE activa = TRUE
        ORDER BY orden DESC, fecha_publicacion DESC
        LIMIT 6;
    """
    novedades = db.session.execute(text(sql_novedades)).mappings().all()

    # 3. Cumpleaños del día (todos los socios activos)
    sql_cumple_hoy = """
        SELECT id, nro_socio, apellido, nombre, dni, telefono, fecha_nacimiento
        FROM socios
        WHERE estado ILIKE 'activo'
          AND fecha_nacimiento IS NOT NULL
          AND EXTRACT(DAY FROM fecha_nacimiento) = :dia
          AND EXTRACT(MONTH FROM fecha_nacimiento) = :mes
        ORDER BY apellido, nombre;
    """
    cumple_hoy = db.session.execute(text(sql_cumple_hoy), {"dia": hoy.day, "mes": hoy.month}).mappings().all()

    # 4. Cumpleaños del mes (todos los socios activos)
    sql_cumple_mes = """
        SELECT id, nro_socio, apellido, nombre, dni, telefono, fecha_nacimiento,
               EXTRACT(DAY FROM fecha_nacimiento)::int AS dia_cumple
        FROM socios
        WHERE estado ILIKE 'activo'
          AND fecha_nacimiento IS NOT NULL
          AND EXTRACT(MONTH FROM fecha_nacimiento) = :mes
        ORDER BY dia_cumple, apellido, nombre;
    """
    cumple_mes = db.session.execute(text(sql_cumple_mes), {"mes": hoy.month}).mappings().all()

    # Calcular edad para los cumpleañeros
    def _calcular_edad(fn):
        if not fn:
            return None
        try:
            if isinstance(fn, str):
                fn_date = datetime.strptime(fn[:10], "%Y-%m-%d").date()
            else:
                fn_date = fn
            return hoy.year - fn_date.year - ((hoy.month, hoy.day) < (fn_date.month, fn_date.day))
        except Exception:
            return None

    cumple_hoy_con_edad = []
    for c in cumple_hoy:
        d = dict(c)
        d["edad"] = _calcular_edad(c.get("fecha_nacimiento"))
        cumple_hoy_con_edad.append(d)

    cumple_mes_con_edad = []
    for m in cumple_mes:
        d = dict(m)
        d["edad"] = _calcular_edad(m.get("fecha_nacimiento"))
        cumple_mes_con_edad.append(d)

    # 5. Archivos del portal para socios (estatuto, memoria y balance, fotos)
    sql_archivos_portal = """
        SELECT id, titulo, descripcion, tipo, archivo, fecha_subida
        FROM archivos_portal
        WHERE activa = TRUE
        ORDER BY tipo, orden DESC, fecha_subida DESC;
    """
    archivos_portal = db.session.execute(text(sql_archivos_portal)).mappings().all()

    # Agrupar por tipo para el template
    estatuto = [a for a in archivos_portal if a["tipo"] == "estatuto"]
    memoria_balance = [a for a in archivos_portal if a["tipo"] == "memoria_balance"]
    fotos_portal = [a for a in archivos_portal if a["tipo"] == "foto"]

    if request.method == "POST":
        busqueda_realizada = True
        termino_busqueda = request.form.get("criterio", "").strip()

        if termino_busqueda:
            sql_buscar = """
                SELECT id, nro_socio, apellido, nombre, dni, estado, fecha_ingreso, fecha_nacimiento
                FROM socios
                WHERE dni = :val OR CAST(nro_socio AS TEXT) = :val OR CAST(id AS TEXT) = :val
                LIMIT 1;
            """
            socio_encontrado = db.session.execute(text(sql_buscar), {"val": termino_busqueda}).mappings().first()

            if socio_encontrado:
                # Comprobar cumpleaños del socio encontrado
                fn = socio_encontrado.get("fecha_nacimiento")
                if fn:
                    try:
                        if isinstance(fn, str):
                            fn_date = datetime.strptime(fn[:10], "%Y-%m-%d").date()
                        else:
                            fn_date = fn

                        if fn_date.day == hoy.day and fn_date.month == hoy.month:
                            es_cumpleanos_hoy = True
                        elif fn_date.month == hoy.month:
                            es_mes_cumpleanos = True
                    except Exception:
                        pass

                # Definición de la consulta con nro_recibo
                sql_pagos = """
                    SELECT id, fecha_cobro, periodo, anio, monto, nro_recibo AS comprobante, metodo_pago
                    FROM cobro_cuotas
                    WHERE socio_id = :socio_id
                    ORDER BY fecha_cobro DESC, id DESC
                    LIMIT 5;
                """
                cuotas_socio = db.session.execute(text(sql_pagos), {"socio_id": socio_encontrado["id"]}).mappings().all()
                if cuotas_socio:
                    ultimo_pago = cuotas_socio[0]

    return render_template(
        "portal_socios.html",
        socio=socio_encontrado,
        cuotas=cuotas_socio,
        ultimo_pago=ultimo_pago,
        busqueda_realizada=busqueda_realizada,
        termino=termino_busqueda,
        es_cumpleanos_hoy=es_cumpleanos_hoy,
        es_mes_cumpleanos=es_mes_cumpleanos,
        comision=comision,
        novedades=novedades,
        cumple_hoy=cumple_hoy_con_edad,
        cumple_mes=cumple_mes_con_edad,
        hoy=hoy,
        estatuto=estatuto,
        memoria_balance=memoria_balance,
        fotos_portal=fotos_portal
    )
###FIN RUTA PARA SOCIOS

# --- RUTAS DE NOVEDADES (ADMINISTRACIÓN) ---

@app.route("/novedades", methods=["GET"])
def listar_novedades():
    """Lista todas las novedades (activas e inactivas) para administración."""
    sql = """
        SELECT id, titulo, contenido, imagen, fecha_publicacion, activa, orden
        FROM novedades
        ORDER BY orden DESC, fecha_publicacion DESC;
    """
    novedades = db.session.execute(text(sql)).mappings().all()
    return render_template("novedades_listar.html", novedades=novedades)


@app.route("/novedades/nueva", methods=["POST"])
def nueva_novedad():
    """Crea una nueva novedad con imagen opcional."""
    titulo = request.form.get("titulo", "").strip()
    contenido = request.form.get("contenido", "").strip()
    activa = request.form.get("activa") == "on"  # True solo si el checkbox está marcado
    orden = int(request.form.get("orden", "0") or 0)
    imagen_nombre = None

    # Subida de imagen
    if "imagen" in request.files:
        archivo = request.files["imagen"]
        if archivo and archivo.filename != "" and archivo_permitido(archivo.filename):
            os.makedirs(NOVEDADES_UPLOAD_FOLDER, exist_ok=True)
            extension = archivo.filename.rsplit(".", 1)[1].lower()
            nombre_archivo = f"novedad_{int(datetime.now().timestamp())}.{extension}"
            ruta_destino = os.path.join(NOVEDADES_UPLOAD_FOLDER, nombre_archivo)
            archivo.save(ruta_destino)
            imagen_nombre = nombre_archivo
            print(f"[DEBUG] Imagen guardada: {ruta_destino}")

    if not titulo:
        flash("El título es obligatorio.", "warning")
        return redirect(url_for("listar_novedades"))

    print(f"[DEBUG] Guardando novedad: activa={activa}, imagen={imagen_nombre}")
    db.session.execute(text("""
        INSERT INTO novedades (titulo, contenido, activa, orden, imagen, fecha_publicacion)
        VALUES (:titulo, :contenido, :activa, :orden, :imagen, NOW());
    """), {"titulo": titulo, "contenido": contenido, "activa": activa, "orden": orden, "imagen": imagen_nombre})
    db.session.commit()
    flash("Novedad creada correctamente.", "success")
    return redirect(url_for("listar_novedades"))


@app.route("/novedades/editar/<int:id>", methods=["POST"])
def editar_novedad(id):
    """Edita una novedad existente, opcionalmente actualizando la imagen."""
    titulo = request.form.get("titulo", "").strip()
    contenido = request.form.get("contenido", "").strip()
    activa = request.form.get("activa") == "on"
    orden = int(request.form.get("orden", "0") or 0)

    if not titulo:
        flash("El título es obligatorio.", "warning")
        return redirect(url_for("listar_novedades"))

    # Manejo de imagen: si se sube una nueva, la guardamos; si no, se mantiene la existente
    imagen_nombre = None
    if "imagen" in request.files:
        archivo = request.files["imagen"]
        if archivo and archivo.filename != "" and archivo_permitido(archivo.filename):
            os.makedirs(NOVEDADES_UPLOAD_FOLDER, exist_ok=True)
            extension = archivo.filename.rsplit(".", 1)[1].lower()
            nombre_archivo = f"novedad_{int(datetime.now().timestamp())}.{extension}"
            ruta_destino = os.path.join(NOVEDADES_UPLOAD_FOLDER, nombre_archivo)
            archivo.save(ruta_destino)
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
    return redirect(url_for("listar_novedades"))


@app.route("/novedades/eliminar/<int:id>", methods=["POST"])
def eliminar_novedad(id):
    """Desactiva o activa una novedad (borrado lógico)."""
    activar = request.form.get("activar") == "1"
    nuevo_estado = True if activar else False
    accion = "activada" if activar else "desactivada"
    flash_color = "success" if activar else "warning"

    db.session.execute(text("UPDATE novedades SET activa = :activa WHERE id = :id;"), {"activa": nuevo_estado, "id": id})
    db.session.commit()
    flash(f"Novedad {accion} correctamente.", flash_color)
    return redirect(url_for("listar_novedades"))


# --- RUTAS DE ARCHIVOS DEL PORTAL (ADMINISTRACIÓN) ---

@app.route("/archivos-portal", methods=["GET"])
def listar_archivos_portal():
    """Lista todos los archivos del portal para administración."""
    sql = """
        SELECT id, titulo, descripcion, tipo, archivo, fecha_subida, activa, orden
        FROM archivos_portal
        ORDER BY tipo, orden DESC, fecha_subida DESC;
    """
    archivos = db.session.execute(text(sql)).mappings().all()
    return render_template("archivos_portal.html", archivos=archivos)


@app.route("/archivos-portal/nueva", methods=["POST"])
def nueva_archivo_portal():
    """Sube un nuevo archivo al portal (estatuto, memoria, foto)."""
    from flask import current_app
    import os as _os

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB máximo

    titulo = request.form.get("titulo", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    tipo = request.form.get("tipo", "").strip()
    activa = request.form.get("activa") == "on"
    orden = int(request.form.get("orden", "0") or 0)

    if not titulo or not tipo:
        flash("El título y el tipo son obligatorios.", "warning")
        return redirect(url_for("listar_archivos_portal"))

    if "archivo" not in request.files:
        flash("Debe seleccionar un archivo.", "warning")
        return redirect(url_for("listar_archivos_portal"))

    archivo = request.files["archivo"]
    if not archivo or archivo.filename == "":
        flash("No se recibió el archivo.", "warning")
        return redirect(url_for("listar_archivos_portal"))

    ext = archivo.filename.rsplit(".", 1)[1].lower() if "." in archivo.filename else ""

    # Validar extensión según tipo
    if tipo == "foto":
        if ext not in EXTENSIONES_PERMITIDAS:
            flash("Para fotos use formatos: JPG, PNG, WEBP, SVG.", "warning")
            return redirect(url_for("listar_archivos_portal"))
    elif tipo in ("estatuto", "memoria_balance"):
        if ext not in EXTENSIONES_DOCUMENTOS:
            flash("Para documentos use formato PDF.", "warning")
            return redirect(url_for("listar_archivos_portal"))
    else:
        flash("Tipo de archivo no válido.", "warning")
        return redirect(url_for("listar_archivos_portal"))

    # Verificar tamaño del archivo (leer en chunks para no cargar todo en memoria)
    archivo.seek(0, 2)  # Ir al final
    file_size = archivo.tell()
    archivo.seek(0)  # Volver al inicio
    if file_size > MAX_FILE_SIZE:
        flash(f"El archivo es demasiado grande (máx. 10 MB). Tamaño actual: {file_size / (1024*1024):.1f} MB.", "warning")
        return redirect(url_for("listar_archivos_portal"))

    carpeta = DOCUMENTOS_UPLOAD_FOLDER if tipo in ("estatuto", "memoria_balance") else FOTOS_PORTAL_UPLOAD_FOLDER
    _os.makedirs(carpeta, exist_ok=True)
    nombre_archivo = f"portal_{tipo}_{int(datetime.now().timestamp())}.{ext}"
    ruta_destino = _os.path.join(carpeta, nombre_archivo)

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
        # Si falló la DB, borrar el archivo subido
        if _os.path.exists(ruta_destino):
            _os.remove(ruta_destino)
        flash(f"Error al guardar el archivo: {str(e)}", "danger")
        current_app.logger.error(f"Error subiendo archivo portal: {e}")

    return redirect(url_for("listar_archivos_portal"))


@app.route("/archivos-portal/editar/<int:id>", methods=["POST"])
def editar_archivo_portal(id):
    """Edita un archivo del portal existente."""
    from flask import current_app
    import os as _os

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB máximo

    titulo = request.form.get("titulo", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    tipo = request.form.get("tipo", "").strip()
    activa = request.form.get("activa") == "on"
    orden = int(request.form.get("orden", "0") or 0)

    if not titulo or not tipo:
        flash("El título y el tipo son obligatorios.", "warning")
        return redirect(url_for("listar_archivos_portal"))

    if tipo not in ("estatuto", "memoria_balance", "foto"):
        flash("Tipo de archivo no válido.", "warning")
        return redirect(url_for("listar_archivos_portal"))

    archivo_nombre = None

    if "archivo" in request.files:
        archivo = request.files["archivo"]
        if archivo and archivo.filename != "":
            ext = archivo.filename.rsplit(".", 1)[1].lower() if "." in archivo.filename else ""

            # Validar extensión según tipo
            if tipo == "foto":
                if ext not in EXTENSIONES_PERMITIDAS:
                    flash("Para fotos use formatos: JPG, PNG, WEBP, SVG.", "warning")
                    return redirect(url_for("listar_archivos_portal"))
            elif tipo in ("estatuto", "memoria_balance"):
                if ext not in EXTENSIONES_DOCUMENTOS:
                    flash("Para documentos use formato PDF.", "warning")
                    return redirect(url_for("listar_archivos_portal"))

            # Verificar tamaño del archivo
            archivo.seek(0, 2)
            file_size = archivo.tell()
            archivo.seek(0)
            if file_size > MAX_FILE_SIZE:
                flash(f"El archivo es demasiado grande (máx. 10 MB). Tamaño actual: {file_size / (1024*1024):.1f} MB.", "warning")
                return redirect(url_for("listar_archivos_portal"))

            carpeta = DOCUMENTOS_UPLOAD_FOLDER if tipo in ("estatuto", "memoria_balance") else FOTOS_PORTAL_UPLOAD_FOLDER
            _os.makedirs(carpeta, exist_ok=True)
            nombre_archivo = f"portal_{tipo}_{int(datetime.now().timestamp())}.{ext}"
            ruta_destino = _os.path.join(carpeta, nombre_archivo)
            archivo_nombre = nombre_archivo

    try:
        if archivo_nombre:
            archivo.save(ruta_destino)
            db.session.execute(text("""
                UPDATE archivos_portal
                SET titulo = :titulo, descripcion = :descripcion, tipo = :tipo, archivo = :archivo, activa = :activa, orden = :orden
                WHERE id = :id;
            """), {"titulo": titulo, "descripcion": descripcion, "tipo": tipo, "archivo": archivo_nombre, "activa": activa, "orden": orden, "id": id})
        else:
            db.session.execute(text("""
                UPDATE archivos_portal
                SET titulo = :titulo, descripcion = :descripcion, tipo = :tipo, activa = :activa, orden = :orden
                WHERE id = :id;
            """), {"titulo": titulo, "descripcion": descripcion, "tipo": tipo, "activa": activa, "orden": orden, "id": id})
        db.session.commit()
        flash("Archivo actualizado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        # Si falló la DB y se subió un archivo nuevo, borrarlo
        if archivo_nombre:
            carpeta = DOCUMENTOS_UPLOAD_FOLDER if tipo in ("estatuto", "memoria_balance") else FOTOS_PORTAL_UPLOAD_FOLDER
            ruta_temp = _os.path.join(carpeta, archivo_nombre)
            if _os.path.exists(ruta_temp):
                _os.remove(ruta_temp)
        flash(f"Error al guardar el archivo: {str(e)}", "danger")
        current_app.logger.error(f"Error editando archivo portal: {e}")

    return redirect(url_for("listar_archivos_portal"))


@app.route("/archivos-portal/eliminar/<int:id>", methods=["POST"])
def eliminar_archivo_portal(id):
    """Desactiva o activa un archivo del portal."""
    activar = request.form.get("activar") == "1"
    nuevo_estado = True if activar else False
    accion = "activada" if activar else "desactivada"
    flash_color = "success" if activar else "warning"

    db.session.execute(text("UPDATE archivos_portal SET activa = :activa WHERE id = :id;"), {"activa": nuevo_estado, "id": id})
    db.session.commit()
    flash(f"Archivo {accion} correctamente.", flash_color)
    return redirect(url_for("listar_archivos_portal"))


@app.route("/archivos-portal/descargar/<int:id>")
def descargar_archivo_portal(id):
    """Descarga un archivo del portal."""
    sql = "SELECT archivo, tipo, titulo FROM archivos_portal WHERE id = :id AND activa = TRUE;"
    archivo = db.session.execute(text(sql), {"id": id}).mappings().first()
    if not archivo:
        flash("Archivo no encontrado o no disponible.", "warning")
        return redirect(url_for("portal_socios"))

    carpeta = DOCUMENTOS_UPLOAD_FOLDER if archivo["tipo"] in ("estatuto", "memoria_balance") else FOTOS_PORTAL_UPLOAD_FOLDER
    ruta = os.path.join(carpeta, archivo["archivo"])
    if not os.path.exists(ruta):
        flash("El archivo físico no existe en el servidor.", "warning")
        return redirect(url_for("portal_socios"))

    from flask import send_file
    return send_file(ruta, as_attachment=True, download_name=f"{archivo['titulo']}.{archivo['archivo'].rsplit('.', 1)[1].lower()}")


##MOROSIDAD
from datetime import date
from sqlalchemy import text

@app.route("/socios/morosidad")
def control_morosidad():
    config = cargar_config()
    reglas = config.get("reglas_negocio", {})
    valor_cuota = float(reglas.get("valor_cuota_mensual", 200.0) or 200.0)

    hoy = date.today()
    mes_actual = hoy.month
    anio_actual = hoy.year

    # 1. Obtener socios activos o vitalicios con su último pago registrado
    sql_morosos = """
        SELECT 
            s.id,
            COALESCE(s.nro_socio, s.id) AS nro_socio,
            s.apellido,
            s.nombre,
            s.dni,
            s.telefono,
            s.direccion,
            s.estado,
            s.fecha_ingreso,
            MAX(c.anio) AS ultimo_anio_pago,
            MAX(c.fecha_cobro) AS ultima_fecha_cobro
        FROM socios s
        LEFT JOIN cobro_cuotas c ON s.id = c.socio_id
        WHERE LOWER(COALESCE(s.estado, 'Activo')) != 'baja'
        GROUP BY s.id, s.nro_socio, s.apellido, s.nombre, s.dni, s.telefono, s.direccion, s.estado, s.fecha_ingreso
        ORDER BY s.apellido ASC, s.nombre ASC;
    """
    socios = db.session.execute(text(sql_morosos)).mappings().all()

    listado_deudores = []
    total_deuda_acumulada = 0.0

    for s in socios:
        ultimo_anio = s["ultimo_anio_pago"]
        
        # Socios sin ningún pago registrado
        if not ultimo_anio:
            meses_deuda = 12  # Estimación base anual para nuevos o sin historial
            estado_mora = "Sin Pagos Registrados"
            badge_class = "danger"
        else:
            # Si el último año es anterior al año en curso
            anios_dif = anio_actual - ultimo_anio
            if anios_dif > 0:
                meses_deuda = (anios_dif * 12) + mes_actual
                estado_mora = f"Debe años anteriores ({ultimo_anio})"
                badge_class = "danger"
            else:
                # Mismo año: verificamos qué períodos tiene pagos en este año
                sql_pagos_anio = """
                    SELECT periodo, count(*) 
                    FROM cobro_cuotas 
                    WHERE socio_id = :socio_id AND anio = :anio
                    GROUP BY periodo;
                """
                pagos = db.session.execute(text(sql_pagos_anio), {"socio_id": s["id"], "anio": anio_actual}).mappings().all()
                cant_pagos = len(pagos)
                
                # Si pagó el año completo o tiene más/igual cuotas que el mes corriente
                if cant_pagos >= mes_actual:
                    meses_deuda = 0
                    estado_mora = "Al Día"
                    badge_class = "success"
                else:
                    meses_deuda = mes_actual - cant_pagos
                    if meses_deuda <= 2:
                        estado_mora = f"Mora Leve ({meses_deuda} m.)"
                        badge_class = "warning"
                    else:
                        estado_mora = f"Mora Crítica ({meses_deuda} m.)"
                        badge_class = "danger"

        # Solo listamos a los que adeudan al menos 1 cuota
        if meses_deuda > 0:
            monto_estimado = meses_deuda * valor_cuota
            total_deuda_acumulada += monto_estimado
            listado_deudores.append({
                "id": s["id"],
                "nro_socio": s["nro_socio"],
                "nombre_completo": f"{s['apellido']}, {s['nombre']}",
                "dni": s["dni"],
                "telefono": s["telefono"],
                "direccion": s["direccion"],
                "estado_socio": s["estado"],
                "ultima_fecha": s["ultima_fecha_cobro"],
                "meses_deuda": meses_deuda,
                "monto_estimado": monto_estimado,
                "estado_mora": estado_mora,
                "badge_class": badge_class
            })

    # Ordenar por mayor cantidad de meses de deuda
    listado_deudores.sort(key=lambda x: x["meses_deuda"], reverse=True)

    return render_template(
        "morosidad.html",
        deudores=listado_deudores,
        total_deudores=len(listado_deudores),
        total_deuda=total_deuda_acumulada,
        valor_cuota=valor_cuota,
        hoy=hoy.strftime("%d/%m/%Y")
    )
#FIN MOROSIDAD


#####RUTA AGREGADA
@app.route("/cuotas")
def listar_cuotas():
    # Consulta uniendo cobro_cuotas con socios y cobradores
    sql = text("""
        SELECT 
            c.id,
            c.nro_recibo,
            c.fecha_cobro,
            c.periodo,
            c.anio,
            c.monto,
            c.metodo_pago,
            c.estado,
            c.observaciones,
            s.nro_socio,
            s.apellido AS socio_apellido,
            s.nombre AS socio_nombre,
            s.dni AS socio_dni,
            cob.nombre AS cobrador_nombre,
            cob.apellido AS cobrador_apellido
        FROM cobro_cuotas c
        INNER JOIN socios s ON c.socio_id = s.id
        LEFT JOIN cobradores cob ON c.cobrador_id = cob.id
        ORDER BY c.fecha_cobro DESC, c.id DESC;
    """)
    
    resultados = db.session.execute(sql).fetchall()
    return render_template("listar_cuotas.html", cuotas=resultados)
##RUTA DE IMPRESION
@app.route("/cuotas/recibo/<int:cuota_id>")
def imprimir_recibo(cuota_id):
    # Consulta detallada del cobro cruzando socio y cobrador
    sql_recibo = """
        SELECT 
            c.id AS cuota_id,
            c.nro_recibo,
            c.fecha_cobro,
            c.periodo,
            c.anio,
            c.monto,
            c.metodo_pago,
            c.observaciones,
            COALESCE(c.estado, 'PAGADO') AS estado,
            s.id AS socio_id,
            COALESCE(s.nro_socio, s.id) AS nro_socio,
            s.apellido,
            s.nombre,
            s.dni,
            s.direccion,
            cob.nombre AS nombre_cobrador,
            cob.apellido AS apellido_cobrador
        FROM cobro_cuotas c
        INNER JOIN socios s ON c.socio_id = s.id
        LEFT JOIN cobradores cob ON c.cobrador_id = cob.id
        WHERE c.id = :id;
    """
    cobro = db.session.execute(text(sql_recibo), {"id": cuota_id}).mappings().first()

    if not cobro:
        flash("El recibo solicitado no existe.", "warning")
        return redirect(url_for("matriz_cuotas"))

    return render_template("recibo_imprimir.html", c=cobro)
##FIN RUTA IMPRESION

# --- RUTA EDITAR CUOTA ---
@app.route("/cuotas/editar/<int:cuota_id>", methods=["GET", "POST"])
def editar_cuota(cuota_id):
    """Edita una cuota existente (tipo, monto, periodo, etc.)."""
    # Obtener la cuota con datos del socio
    sql_cuota = """
        SELECT 
            c.id, c.nro_recibo, c.fecha_cobro, c.socio_id, c.periodo, c.anio, c.monto,
            c.metodo_pago, c.cobrador_id, c.estado, c.observaciones,
            c.tipo_concepto,
            s.apellido, s.nombre, s.nro_socio
        FROM cobro_cuotas c
        INNER JOIN socios s ON c.socio_id = s.id
        WHERE c.id = :id;
    """
    cuota = db.session.execute(text(sql_cuota), {"id": cuota_id}).mappings().first()

    if not cuota:
        flash("La cuota solicitada no existe.", "warning")
        return redirect(url_for("matriz_cuotas"))

    # Obtener lista de cobradores para el select
    cobradores = db.session.execute(text("SELECT id, nombre, apellido FROM cobradores WHERE activo = TRUE ORDER BY nombre")).mappings().all()

    if request.method == "POST":
        nro_recibo = request.form.get("nro_recibo", "").strip()
        fecha_cobro = request.form.get("fecha_cobro") or ""
        periodo = request.form.get("periodo", "").strip()
        anio = int(request.form.get("anio", "2026") or 2026)
        monto = float(request.form.get("monto", "0") or 0)
        metodo_pago = request.form.get("metodo_pago", "Efectivo").strip()
        cobrador_id = int(request.form.get("cobrador_id")) if request.form.get("cobrador_id") else None
        estado = request.form.get("estado", "PAGADO").strip()
        observaciones = request.form.get("observaciones", "").strip()
        tipo_concepto = request.form.get("tipo_concepto", "cuota_mensual").strip()

        if not nro_recibo or not periodo or monto <= 0:
            flash("Recibo, período y monto son obligatorios.", "warning")
            return redirect(url_for("editar_cuota", cuota_id=cuota_id))

        try:
            db.session.execute(text("""
                UPDATE cobro_cuotas
                SET nro_recibo = :nro_recibo,
                    fecha_cobro = :fecha_cobro,
                    periodo = :periodo,
                    anio = :anio,
                    monto = :monto,
                    metodo_pago = :metodo_pago,
                    cobrador_id = :cobrador_id,
                    estado = :estado,
                    observaciones = :observaciones,
                    tipo_concepto = :tipo_concepto
                WHERE id = :id;
            """), {
                "id": cuota_id,
                "nro_recibo": nro_recibo,
                "fecha_cobro": fecha_cobro,
                "periodo": periodo,
                "anio": anio,
                "monto": monto,
                "metodo_pago": metodo_pago,
                "cobrador_id": cobrador_id,
                "estado": estado,
                "observaciones": observaciones,
                "tipo_concepto": tipo_concepto
            })
            db.session.commit()
            flash("Cuota actualizada correctamente.", "success")
            return redirect(url_for("ficha_socio", id=cuota["socio_id"]))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar la cuota: {str(e)}", "danger")
            return redirect(url_for("editar_cuota", cuota_id=cuota_id))

    return render_template("editar_cuota.html", cuota=cuota, cobradores=cobradores)

#### FIN RUTA EDITAR CUOTA
#### RUTA PARA MOVIMIENTOS DE CAJA
from datetime import date
###listar caja
@app.route("/caja")
def listar_caja():
    anio_param = request.args.get("anio", "")
    mes_param = request.args.get("mes", "")
    
    # 1. Filtros según el período seleccionado
    if anio_param.isdigit() and mes_param.isdigit():
        # Filtro por mes y año específicos
        filtro_cuotas = "AND anio = :anio AND mes = :mes"
        filtro_caja = "AND EXTRACT(YEAR FROM fecha) = :anio AND EXTRACT(MONTH FROM fecha) = :mes"
        params = {"anio": int(anio_param), "mes": int(mes_param)}
        meses_nombre = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        etiqueta_periodo = f"{meses_nombre[int(mes_param)]} {anio_param}"
    elif anio_param.isdigit():
        # Filtro solo por año
        filtro_cuotas = "AND (anio = :anio OR EXTRACT(YEAR FROM fecha_cobro) = :anio)"
        filtro_caja = "AND EXTRACT(YEAR FROM fecha) = :anio"
        params = {"anio": int(anio_param)}
        etiqueta_periodo = f"Año {anio_param}"
    else:
        filtro_cuotas = ""
        filtro_caja = ""
        params = {}
        etiqueta_periodo = "Histórico Acumulado"

    # 2. Total Ingresos de Socios (Cuotas + Inscripciones)
    sql_socios = f"""
        SELECT COALESCE(SUM(monto), 0)
        FROM cobro_cuotas
        WHERE (LOWER(estado) = 'pagado' OR estado IS NULL)
        {filtro_cuotas};
    """
    total_socios = float(db.session.execute(text(sql_socios), params).scalar() or 0.0)

    # 3. Otros Ingresos asentados en caja (excluyendo pagos de cuotas para no duplicar)
    sql_otros_ingresos = f"""
        SELECT 
            id,
            fecha,
            categoria,
            concepto,
            comprobante,
            interviene,
            metodo,
            monto AS total_concepto
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'ingreso' AND cuota_id IS NULL
        {filtro_caja}
        ORDER BY fecha DESC, id DESC;
    """
    otros_ingresos_items = db.session.execute(text(sql_otros_ingresos), params).fetchall()
    total_otros_ingresos = sum(float(item.total_concepto) for item in otros_ingresos_items) if otros_ingresos_items else 0.0

    # 4. Egresos / Gastos
    sql_egresos = f"""
        SELECT 
            id,
            fecha,
            categoria,
            concepto,
            comprobante,
            interviene,
            metodo,
            monto AS total_concepto
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'egreso'
        {filtro_caja}
        ORDER BY fecha DESC, id DESC;
    """
    egresos_items = db.session.execute(text(sql_egresos), params).fetchall()
    total_egresos = sum(float(item.total_concepto) for item in egresos_items) if egresos_items else 0.0

    # 5. Consolidación de Totales
    total_ingresos = total_socios + total_otros_ingresos
    saldo_actual = total_ingresos - total_egresos

    return render_template(
        "listar_caja.html",
        etiqueta_periodo=etiqueta_periodo,
        anio_param=anio_param,
        mes_param=mes_param,
        total_socios=total_socios,
        otros_ingresos_items=otros_ingresos_items,
        total_otros_ingresos=total_otros_ingresos,
        total_ingresos=total_ingresos,
        egresos_items=egresos_items,
        total_egresos=total_egresos,
        saldo_actual=saldo_actual
    )

#### fin listar caja

@app.route("/caja/exportar_excel_balance", methods=["GET"])
def caja_exportar_excel_balance():
    """Exporta el Balance de Ingresos y Egresos a Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from flask import send_file
    import io
    from datetime import datetime

    config = cargar_config()
    nombre_inst = config.get("institucion", {}).get("nombre", "Centro de Jubilados y Pensionados")

    anio_param = request.args.get("anio", "")
    mes_param = request.args.get("mes", "")

    if anio_param.isdigit() and mes_param.isdigit():
        filtro_cuotas = "AND anio = :anio AND mes = :mes"
        filtro_caja = "AND EXTRACT(YEAR FROM fecha) = :anio AND EXTRACT(MONTH FROM fecha) = :mes"
        params = {"anio": int(anio_param), "mes": int(mes_param)}
        meses_nombre = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        etiqueta_periodo = f"{meses_nombre[int(mes_param)]} {anio_param}"
    elif anio_param.isdigit():
        filtro_cuotas = "AND (anio = :anio OR EXTRACT(YEAR FROM fecha_cobro) = :anio)"
        filtro_caja = "AND EXTRACT(YEAR FROM fecha) = :anio"
        params = {"anio": int(anio_param)}
        etiqueta_periodo = f"Año {anio_param}"
    else:
        filtro_cuotas = ""
        filtro_caja = ""
        params = {}
        etiqueta_periodo = "Histórico Acumulado"

    # 1. Ingresos de socios (cuotas) - CONSOLIDADO en una sola línea
    sql_total_socios = f"""
        SELECT COALESCE(SUM(monto), 0) AS total
        FROM cobro_cuotas
        WHERE (LOWER(estado) = 'pagado' OR estado IS NULL)
        {filtro_cuotas};
    """
    total_socios_result = db.session.execute(text(sql_total_socios), params).fetchone()
    total_socios = float(total_socios_result[0] if total_socios_result else 0)

    # 2. Otros ingresos de caja (sin cuota_id para no duplicar)
    sql_otros_ingresos = f"""
        SELECT 
            fecha,
            'Ingreso - Caja' AS tipo,
            COALESCE(categoria, 'General') AS categoria,
            concepto,
            comprobante,
            metodo,
            monto,
            interviene,
            observaciones
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'ingreso' AND cuota_id IS NULL
        {filtro_caja};
    """
    otros_ingresos = db.session.execute(text(sql_otros_ingresos), params).mappings().all()

    # 3. Egresos
    sql_egresos = f"""
        SELECT 
            fecha,
            'Egreso' AS tipo,
            COALESCE(categoria, 'General') AS categoria,
            concepto,
            comprobante,
            metodo,
            monto,
            interviene,
            observaciones
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'egreso'
        {filtro_caja};
    """
    egresos = db.session.execute(text(sql_egresos), params).mappings().all()

    # Combinar: primero la línea consolidada de socios, luego otros ingresos, luego egresos
    todos_movimientos = []

    # Línea consolidada de socios
    if total_socios > 0:
        todos_movimientos.append({
            "fecha": "",
            "tipo": "Ingreso - Cuota Socio",
            "categoria": "Cuota Social",
            "concepto": "Recaudación Masa Societaria (Cuotas e Inscripciones)",
            "comprobante": "",
            "metodo": "",
            "monto": total_socios,
            "interviene": "Cobradores y Sede",
            "observaciones": "Total general de cobranzas a socios registrados",
            "es_socio_consolidado": True
        })

    # Otros ingresos individuales
    for item in otros_ingresos:
        item_dict = dict(item)
        item_dict["es_socio_consolidado"] = False
        todos_movimientos.append(item_dict)

    # Egresos individuales
    for item in egresos:
        item_dict = dict(item)
        item_dict["es_socio_consolidado"] = False
        todos_movimientos.append(item_dict)

    # Crear el libro Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Balance Caja"
    ws.views.sheetView[0].showGridLines = True

    fuente_titulo = Font(name="Calibri", size=14, bold=True, color="1B365D")
    fuente_subtitulo = Font(name="Calibri", size=11, bold=True, color="495057")
    fuente_info = Font(name="Calibri", size=10, bold=True, color="0D6EFD")
    fuente_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    fuente_fila = Font(name="Calibri", size=10)
    fuente_negrita = Font(name="Calibri", size=10, bold=True)

    fill_header = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    fill_ingreso = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    fill_egreso = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
    fill_resumen = PatternFill(start_color="F1F3F5", end_color="F1F3F5", fill_type="solid")

    borde_fino = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC")
    )
    borde_doble_bottom = Border(bottom=Side(style="double", color="000000"), top=Side(style="thin", color="000000"))

    # Encabezado
    ws["A1"] = nombre_inst.upper()
    ws["A1"].font = fuente_titulo

    ws["A2"] = f"BALANCE DE INGRESOS Y EGRESOS - {etiqueta_periodo}"
    ws["A2"].font = fuente_subtitulo

    ws["A3"] = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A3"].font = Font(name="Calibri", size=9, italic=True, color="6C757D")

    # Encabezados de tabla
    headers = ["Fecha", "Tipo", "Categoría", "Concepto", "Comprobante", "Medio", "Importe ($)", "Interviene", "Observaciones"]
    fila_actual = 5

    for col_idx, header in enumerate(headers, 1):
        celda = ws.cell(row=fila_actual, column=col_idx, value=header)
        celda.font = fuente_header
        celda.fill = fill_header
        celda.alignment = Alignment(horizontal="center", vertical="center")
        celda.border = borde_fino

    fila_inicio_datos = fila_actual + 1
    total_ingresos = 0.0
    total_egresos = 0.0

    for mov in todos_movimientos:
        fila_actual += 1
        monto = float(mov["monto"] or 0)
        tipo = str(mov["tipo"] or "-")
        es_ingreso = "ingreso" in tipo.lower()
        es_consolidado = mov.get("es_socio_consolidado", False)

        # Para la línea consolidada de socios, no hay fecha específica
        if es_consolidado:
            fecha_txt = "Acumulado"
        else:
            fecha_txt = ""
            if mov["fecha"]:
                if hasattr(mov["fecha"], "strftime"):
                    fecha_txt = mov["fecha"].strftime("%d/%m/%Y")
                else:
                    fecha_txt = str(mov["fecha"])

        valores = [
            fecha_txt,
            tipo,
            mov["categoria"] or "-",
            mov["concepto"] or "-",
            mov["comprobante"] or "-",
            mov["metodo"] or "-",
            monto if es_ingreso else None,
            None if es_ingreso else monto,
            mov["interviene"] or "-",
            mov["observaciones"] or "-"
        ]

        for col_idx, val in enumerate(valores, 1):
            celda = ws.cell(row=fila_actual, column=col_idx, value=val)
            celda.border = borde_fino
            # Estilo especial para la línea consolidada de socios
            if es_consolidado:
                celda.font = fuente_negrita
                celda.fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
                if col_idx in [1, 2, 3, 5, 6, 9]:
                    celda.alignment = Alignment(horizontal="center")
                elif col_idx == 4:
                    celda.alignment = Alignment(horizontal="left")
                elif col_idx in [7, 8]:
                    celda.alignment = Alignment(horizontal="right")
                    celda.number_format = "$#,##0.00"
            else:
                celda.font = fuente_fila
                if col_idx in [1, 2, 3, 5, 6, 9]:
                    celda.alignment = Alignment(horizontal="center")
                elif col_idx == 4:
                    celda.alignment = Alignment(horizontal="left")
                elif col_idx in [7, 8]:
                    celda.alignment = Alignment(horizontal="right")
                    celda.number_format = "$#,##0.00"
                    if val is not None:
                        celda.fill = fill_ingreso if col_idx == 7 else fill_egreso

        if es_ingreso:
            total_ingresos += monto
        else:
            total_egresos += monto

    # Totales
    fila_actual += 1
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=6)
    c_tot = ws.cell(row=fila_actual, column=1, value="TOTALES:")
    c_tot.font = fuente_negrita
    c_tot.alignment = Alignment(horizontal="right")

    c_ing_tot = ws.cell(row=fila_actual, column=7, value=total_ingresos)
    c_ing_tot.font = fuente_negrita
    c_ing_tot.number_format = "$#,##0.00"
    c_ing_tot.alignment = Alignment(horizontal="right")
    c_ing_tot.border = borde_doble_bottom
    c_ing_tot.fill = fill_ingreso

    c_egr_tot = ws.cell(row=fila_actual, column=8, value=total_egresos)
    c_egr_tot.font = fuente_negrita
    c_egr_tot.number_format = "$#,##0.00"
    c_egr_tot.alignment = Alignment(horizontal="right")
    c_egr_tot.border = borde_doble_bottom
    c_egr_tot.fill = fill_egreso

    fila_actual += 1
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=6)
    c_saldo_txt = ws.cell(row=fila_actual, column=1, value="SALDO EN CAJA:")
    c_saldo_txt.font = fuente_negrita
    c_saldo_txt.alignment = Alignment(horizontal="right")

    c_saldo_val = ws.cell(row=fila_actual, column=7, value=total_ingresos - total_egresos)
    c_saldo_val.font = Font(name="Calibri", size=11, bold=True, color="004D40")
    c_saldo_val.number_format = "$#,##0.00"
    c_saldo_val.alignment = Alignment(horizontal="right")
    c_saldo_val.fill = fill_resumen
    c_saldo_val.border = borde_doble_bottom

    # Anchos de columnas
    anchos = {"A": 12, "B": 20, "C": 18, "D": 40, "E": 16, "F": 12, "G": 14, "H": 14, "I": 18, "J": 40}
    for col, w in anchos.items():
        ws.column_dimensions[col].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    nombre_archivo = f"Balance_Caja_{etiqueta_periodo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nombre_archivo
    )


@app.route("/caja/nuevo", methods=["GET", "POST"])
def nuevo_movimiento_caja():
    if request.method == "POST":
        tipo = request.form.get("tipo")               # Ingreso / Egreso
        categoria = request.form.get("categoria")     # Servicios, Donación, Mantenimiento, etc.
        concepto = request.form.get("concepto", "").strip()
        monto = float(request.form.get("monto", "0"))
        comprobante = request.form.get("comprobante", "").strip()
        interviene = request.form.get("interviene", "").strip()
        metodo = request.form.get("metodo", "Efectivo")
        fecha = request.form.get("fecha") or str(date.today())
        observaciones = request.form.get("observaciones", "").strip()

        try:
            query = text("""
                INSERT INTO movimientos_caja (
                    fecha, tipo, categoria, concepto, monto, comprobante, interviene, metodo, observaciones
                )
                VALUES (
                    :fecha, :tipo, :categoria, :concepto, :monto, :comprobante, :interviene, :metodo, :observaciones
                );
            """)
            db.session.execute(query, {
                "fecha": fecha,
                "tipo": tipo,
                "categoria": categoria,
                "concepto": concepto,
                "monto": monto,
                "comprobante": comprobante,
                "interviene": interviene,
                "metodo": metodo,
                "observaciones": observaciones
            })
            db.session.commit()
            flash("Movimiento asentado en caja correctamente.", "success")
            return redirect(url_for("listar_caja"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar movimiento: {str(e)}", "danger")

    hoy = str(date.today())
    return render_template("nuevo_movimiento.html", hoy=hoy)

#### FIN RUTA MOVIMIENTOS DE CAJA

####RUTA EDITAR MOVIMIENTO DE CAJA
@app.route("/caja/editar/<int:id>", methods=["GET", "POST"])
def editar_movimiento_caja(id):
    # Verificar que el movimiento exista y no sea de un cobro de cuota
    query_verif = text("SELECT * FROM movimientos_caja WHERE id = :id;")
    movimiento = db.session.execute(query_verif, {"id": id}).fetchone()

    if not movimiento:
        flash("El movimiento no existe.", "warning")
        return redirect(url_for("listar_caja"))

    if movimiento.cuota_id is not None:
        flash("Los movimientos vinculados a cuotas de socios deben modificarse desde el módulo de cuotas.", "danger")
        return redirect(url_for("listar_caja"))

    if request.method == "POST":
        tipo = request.form.get("tipo")
        fecha = request.form.get("fecha")
        categoria = request.form.get("categoria")
        concepto = request.form.get("concepto", "").strip()
        monto = float(request.form.get("monto", "0"))
        comprobante = request.form.get("comprobante", "").strip()
        interviene = request.form.get("interviene", "").strip()
        metodo = request.form.get("metodo", "Efectivo")
        observaciones = request.form.get("observaciones", "").strip()

        try:
            update_sql = text("""
                UPDATE movimientos_caja
                SET tipo = :tipo,
                    fecha = :fecha,
                    categoria = :categoria,
                    concepto = :concepto,
                    monto = :monto,
                    comprobante = :comprobante,
                    interviene = :interviene,
                    metodo = :metodo,
                    observaciones = :observaciones
                WHERE id = :id AND cuota_id IS NULL;
            """)
            db.session.execute(update_sql, {
                "id": id,
                "tipo": tipo,
                "fecha": fecha,
                "categoria": categoria,
                "concepto": concepto,
                "monto": monto,
                "comprobante": comprobante,
                "interviene": interviene,
                "metodo": metodo,
                "observaciones": observaciones
            })
            db.session.commit()
            flash("Movimiento actualizado correctamente.", "success")
            return redirect(url_for("listar_caja"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar el movimiento: {str(e)}", "danger")

    return render_template("editar_movimiento.html", m=movimiento)
#####FIN EDITAR MOVIMIENTO DE CAJA
##Ruta matriz de datos (cobros)
from datetime import datetime

@app.route("/matriz-cuotas")
def matriz_cuotas():
    anio_param = request.args.get("anio", "")
    anio = int(anio_param) if anio_param.isdigit() else datetime.today().year
    busqueda = request.args.get("q", "").strip()

    # 1. Padrón de socios (con filtro de búsqueda si se especifica)
    if busqueda:
        sql_socios = """
            SELECT id, nro_socio, apellido, nombre, dni, telefono, COALESCE(estado, 'Activo') AS estado
            FROM socios
            WHERE apellido ILIKE :q OR nombre ILIKE :q OR CAST(nro_socio AS TEXT) ILIKE :q OR CAST(id AS TEXT) ILIKE :q
            ORDER BY apellido ASC, nombre ASC;
        """
        socios_raw = db.session.execute(text(sql_socios), {"q": f"%{busqueda}%"}).fetchall()
    else:
        sql_socios = """
            SELECT id, nro_socio, apellido, nombre, dni, telefono, COALESCE(estado, 'Activo') AS estado
            FROM socios
            ORDER BY apellido ASC, nombre ASC;
        """
        socios_raw = db.session.execute(text(sql_socios)).fetchall()

    # 2. Cobros del año
    sql_cobros = """
        SELECT 
            socio_id,
            mes,
            anio,
            periodo,
            LOWER(COALESCE(tipo_concepto, 'cuota')) AS concepto,
            monto
        FROM cobro_cuotas
        WHERE (anio = :anio OR EXTRACT(YEAR FROM fecha_cobro) = :anio)
          AND (LOWER(estado) = 'pagado' OR estado IS NULL);
    """
    cobros_raw = db.session.execute(text(sql_cobros), {"anio": anio}).fetchall()

    # Mapeo de abreviaturas de periodo a números de mes
    mapa_meses = {
        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
        'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dic': 12
    }

    # Indexar cobros tanto por id como por nro_socio
    pagos_por_socio = {}
    for c in cobros_raw:
        if c.socio_id is not None:
            pagos_por_socio.setdefault(c.socio_id, []).append(c)

    matriz = []
    total_socios_activos = 0

    for s in socios_raw:
        if s.estado.lower() == 'activo':
            total_socios_activos += 1

        meses_cubiertos = set()
        tiene_inscripcion = False
        total_abonado = 0.0

        # Buscar pagos vinculando por su nro_socio O por su id interno
        pagos = []
        if s.nro_socio in pagos_por_socio:
            pagos.extend(pagos_por_socio[s.nro_socio])
        if s.id in pagos_por_socio and s.id != s.nro_socio:
            pagos.extend(pagos_por_socio[s.id])

        for p in pagos:
            total_abonado += float(p.monto or 0)
            concepto_str = str(p.concepto or '')
            periodo_str = str(p.periodo or '').lower().strip()

            if 'inscrip' in concepto_str:
                tiene_inscripcion = True

            # Si mes viene numérico directo
            if p.mes and 1 <= p.mes <= 12:
                meses_cubiertos.add(p.mes)
            else:
                # Detectar mes por el prefijo de periodo (ej: "ene-26", "jul-26", "sept-26")
                encontrado = False
                for clave, num_mes in mapa_meses.items():
                    if periodo_str.startswith(clave):
                        meses_cubiertos.add(num_mes)
                        encontrado = True
                        break

                if not encontrado:
                    if 'anual' in periodo_str or 'año' in periodo_str or 'completo' in periodo_str:
                        meses_cubiertos.update(range(1, 13))
                    elif '1' in periodo_str and 'semestre' in periodo_str:
                        meses_cubiertos.update(range(1, 7))
                    elif '2' in periodo_str and 'semestre' in periodo_str:
                        meses_cubiertos.update(range(7, 13))

        matriz.append({
            "id": s.id,
            "nro_socio": s.nro_socio,
            "apellido": s.apellido,
            "nombre": s.nombre,
            "dni": s.dni,
            "telefono": s.telefono,
            "estado": s.estado,
            "inscripcion": tiene_inscripcion,
            "meses": [m in meses_cubiertos for m in range(1, 13)],
            "total_abonado": total_abonado
        })

    return render_template(
        "matriz_cuotas.html",
        matriz=matriz,
        anio=anio,
        busqueda=busqueda,
        total_socios_activos=total_socios_activos
    )
#Fin ruta matriz de datos 
# ==========================================
# RUTAS DE SOCIOS: PADRÓN Y FICHA
# ==========================================

@app.route("/socios")
def listar_socios():
    try:
        # Asegurar asignación de nro_socio a registros antiguos
        db.session.execute(text("UPDATE socios SET nro_socio = id WHERE nro_socio IS NULL;"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    # Consulta directa de socios - Ordenado alfabéticamente por apellido y nombre
    sql_socios = """
        SELECT 
            id,
            COALESCE(nro_socio, id) AS nro_socio,
            apellido,
            nombre,
            dni,
            telefono,
            direccion,
            fecha_ingreso,
            COALESCE(estado, 'Activo') AS estado
        FROM socios
        ORDER BY apellido ASC, nombre ASC;
    """
    socios = db.session.execute(text(sql_socios)).mappings().all()
    return render_template("listar_socios.html", socios=socios)


@app.route("/socios/<int:id>")
def ficha_socio(id):
    # 1. Obtener datos del socio mediante mappings
    sql_socio = "SELECT * FROM socios WHERE id = :id;"
    socio = db.session.execute(text(sql_socio), {"id": id}).mappings().first()

    if not socio:
        flash(f"El socio con ID {id} no fue encontrado.", "warning")
        return redirect(url_for("listar_socios"))

    # 2. Historial de cuotas pagadas vinculado por socio_id
    sql_cuotas = """
        SELECT 
            id,
            fecha_cobro,
            periodo,
            anio,
            monto,
            COALESCE(nro_recibo, '-') AS comprobante,
            COALESCE(metodo_pago, 'Efectivo') AS metodo,
            COALESCE(estado, 'PAGADO') AS estado,
            observaciones
        FROM cobro_cuotas
        WHERE socio_id = :socio_id
        ORDER BY fecha_cobro DESC, id DESC;
    """
    cuotas = db.session.execute(text(sql_cuotas), {"socio_id": id}).mappings().all()

    total_aportado = sum(float(c.get("monto") or 0) for c in cuotas if str(c.get("estado", "")).lower() == 'pagado')

    return render_template(
        "ficha_socio.html",
        socio=socio,
        cuotas=cuotas,
        total_aportado=total_aportado
    )
### ABM socios
from datetime import date, datetime

# ==========================================
# ABM DE SOCIOS
# ==========================================

@app.route("/socios/nuevo", methods=["GET", "POST"])
def nuevo_socio():
    if request.method == "POST":
        apellido = request.form.get("apellido", "").strip().upper()
        nombre = request.form.get("nombre", "").strip().title()
        dni = request.form.get("dni", "").strip()
        fecha_nacimiento = request.form.get("fecha_nacimiento") or None
        telefono = request.form.get("telefono", "").strip()
        email = request.form.get("email", "").strip()
        direccion = request.form.get("direccion", "").strip()
        fecha_ingreso = request.form.get("fecha_ingreso") or date.today()
        estado = request.form.get("estado", "Activo")
        observaciones = request.form.get("observaciones", "").strip()

        try:
            # 1. Insertamos dejando nro_socio temporalmente NULL y obtenemos el id autoincremental
            sql_insert = text("""
                INSERT INTO socios (
                    apellido, nombre, dni, fecha_nacimiento,
                    telefono, email, direccion, fecha_ingreso, estado, observaciones
                ) VALUES (
                    :apellido, :nombre, :dni, :fecha_nacimiento,
                    :telefono, :email, :direccion, :fecha_ingreso, :estado, :observaciones
                ) RETURNING id;
            """)
            res = db.session.execute(sql_insert, {
                "apellido": apellido,
                "nombre": nombre,
                "dni": dni,
                "fecha_nacimiento": fecha_nacimiento,
                "telefono": telefono,
                "email": email,
                "direccion": direccion,
                "fecha_ingreso": fecha_ingreso,
                "estado": estado,
                "observaciones": observaciones
            })
            nuevo_id = res.fetchone()[0]

            # 2. Igualamos nro_socio = id
            db.session.execute(
                text("UPDATE socios SET nro_socio = :id WHERE id = :id;"),
                {"id": nuevo_id}
            )
            db.session.commit()

            flash(f"Socio N° {nuevo_id} ({apellido}, {nombre}) registrado exitosamente.", "success")
            return redirect(url_for("listar_socios"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar socio: {e}", "danger")

    return render_template("socio_form.html", socio=None)
# ==========================================
# EDICIÓN DE SOCIO
# ==========================================

@app.route("/socios/editar/<int:id>", methods=["GET", "POST"])
def editar_socio(id):
    if request.method == "POST":
        nro_socio = request.form.get("nro_socio") or None
        apellido = request.form.get("apellido", "").strip()
        nombre = request.form.get("nombre", "").strip()
        dni = request.form.get("dni", "").strip()
        telefono = request.form.get("telefono", "").strip()
        email = request.form.get("email", "").strip()
        direccion = request.form.get("direccion", "").strip()
        estado = request.form.get("estado", "Activo")
        observaciones = request.form.get("observaciones", "").strip()

        sql_update = """
            UPDATE socios
            SET nro_socio = :nro_socio,
                apellido = :apellido,
                nombre = :nombre,
                dni = :dni,
                telefono = :telefono,
                email = :email,
                direccion = :direccion,
                estado = :estado,
                observaciones = :observaciones
            WHERE id = :id;
        """
        db.session.execute(text(sql_update), {
            "id": id,
            "nro_socio": nro_socio,
            "apellido": apellido,
            "nombre": nombre,
            "dni": dni,
            "telefono": telefono,
            "email": email,
            "direccion": direccion,
            "estado": estado,
            "observaciones": observaciones
        })
        db.session.commit()
        flash("Datos del socio actualizados exitosamente.", "success")
        return redirect(url_for("matriz_cuotas"))

    # Carga de datos para GET
    sql_socio = "SELECT * FROM socios WHERE id = :id;"
    socio = db.session.execute(text(sql_socio), {"id": id}).fetchone()
    if not socio:
        flash("Socio no encontrado.", "warning")
        return redirect(url_for("matriz_cuotas"))

    return render_template("editar_socio.html", socio=socio)

# ==========================================
# CUMPLEAÑOS Y RECORDATORIOS
# ==========================================

@app.route("/socios/cumpleanos")
def cumpleanos_socios():
    hoy = date.today()
    mes_actual = hoy.month
    dia_actual = hoy.day
    mes_filtro = int(request.args.get("mes", mes_actual))

    # 1. Cumpleaños del día de hoy
    sql_hoy = """
        SELECT id, nro_socio, apellido, nombre, telefono, fecha_nacimiento,
               EXTRACT(YEAR FROM AGE(:hoy, fecha_nacimiento)) AS edad
        FROM socios
        WHERE fecha_nacimiento IS NOT NULL
          AND EXTRACT(MONTH FROM fecha_nacimiento) = :mes_actual
          AND EXTRACT(DAY FROM fecha_nacimiento) = :dia_actual
          AND LOWER(COALESCE(estado, 'activo')) = 'activo'
        ORDER BY apellido;
    """
    cumple_hoy = db.session.execute(text(sql_hoy), {
        "hoy": hoy,
        "mes_actual": mes_actual,
        "dia_actual": dia_actual
    }).fetchall()

    # 2. Cumpleaños del mes seleccionado
    sql_mes = """
        SELECT id, nro_socio, apellido, nombre, telefono, fecha_nacimiento,
               EXTRACT(DAY FROM fecha_nacimiento) AS dia,
               EXTRACT(YEAR FROM AGE(:hoy, fecha_nacimiento)) AS edad
        FROM socios
        WHERE fecha_nacimiento IS NOT NULL
          AND EXTRACT(MONTH FROM fecha_nacimiento) = :mes_filtro
          AND LOWER(COALESCE(estado, 'activo')) = 'activo'
        ORDER BY EXTRACT(DAY FROM fecha_nacimiento) ASC, apellido ASC;
    """
    cumple_mes = db.session.execute(text(sql_mes), {
        "hoy": hoy,
        "mes_filtro": mes_filtro
    }).fetchall()

    meses_nombre = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }

    return render_template(
        "cumpleanos.html",
        cumple_hoy=cumple_hoy,
        cumple_mes=cumple_mes,
        mes_filtro=mes_filtro,
        meses_nombre=meses_nombre,
        hoy=hoy
    )
####FIN RUTA SOCIOS
###EDITAR UN SOCIO
@app.route("/registrar-cuota", methods=["GET", "POST"])
def registrar_cuota():
    if request.method == "POST":
        socio_id = request.form.get("socio_id")
        cobrador_id = request.form.get("cobrador_id")
        nro_recibo = request.form.get("nro_recibo", "").strip()
        fecha_cobro = request.form.get("fecha_cobro") or str(date.today())
        periodo = request.form.get("periodo", "").strip()
        monto = request.form.get("monto", "0")
        metodo_pago = request.form.get("metodo_pago", "Efectivo")
        observaciones = request.form.get("observaciones", "").strip()
        tipo_concepto = request.form.get("tipo_concepto", "cuota_anual")
        categoria_caja = "Inscripción" if tipo_concepto == "inscripcion" else "Cuota Social"

        try:
            # 1. Insertar cobro en cobro_cuotas
            query_cuota = text("""
                INSERT INTO cobro_cuotas (
                    nro_recibo, fecha_cobro, socio_id, periodo, anio, monto, metodo_pago, cobrador_id, estado, observaciones
                )
                VALUES (
                    :recibo, :fecha, :socio_id, :periodo, :anio, :monto, :metodo, :cobrador_id, 'PAGADO', :obs
                )
                RETURNING id;
            """)
            
            anio_actual = int(fecha_cobro.split("-")[0]) if fecha_cobro else 2026
            resultado = db.session.execute(query_cuota, {
                "recibo": nro_recibo,
                "fecha": fecha_cobro,
                "socio_id": socio_id,
                "periodo": periodo,
                "anio": anio_actual,
                "monto": float(monto),
                "metodo": metodo_pago,
                "cobrador_id": int(cobrador_id) if cobrador_id else None,
                "obs": observaciones
            })
            cuota_id = resultado.fetchone()[0]

            # 2. Buscar datos de referencia para el asiento contable
            socio = db.session.execute(text("SELECT apellido, nombre FROM socios WHERE id = :id"), {"id": socio_id}).fetchone()
            nombre_socio = f"{socio.apellido}, {socio.nombre}" if socio else f"Socio ID {socio_id}"

            nombre_cobrador = "Sede Central"
            if cobrador_id:
                cob = db.session.execute(text("SELECT nombre FROM cobradores WHERE id = :id"), {"id": cobrador_id}).fetchone()
                if cob:
                    nombre_cobrador = cob.nombre

            # 3. Asentar movimiento en movimientos_caja (un solo asiento ordenado)
            query_caja = text("""
                INSERT INTO movimientos_caja (
                    fecha, tipo, categoria, concepto, monto, comprobante, interviene, metodo, cuota_id, observaciones
                )
                VALUES (
                    :fecha, 'Ingreso', :categoria, :concepto, :monto, :comprobante, :interviene, :metodo, :cuota_id, :obs
                );
            """)

            db.session.execute(query_caja, {
                "fecha": fecha_cobro,
                "categoria": categoria_caja,
                "concepto": f"Cobro {periodo} - Socio: {nombre_socio}",
                "monto": float(monto),
                "comprobante": nro_recibo,
                "interviene": nombre_cobrador,
                "metodo": metodo_pago,
                "cuota_id": cuota_id,
                "obs": observaciones
            })

            db.session.commit()
            flash("¡Cobro e ingreso de caja registrados correctamente!", "success")
            return redirect(url_for("matriz_cuotas"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar cobro: {str(e)}", "danger")

    # CARGA PARA EL FORMULARIO (GET)
  # CARGA PARA EL FORMULARIO (GET)
    # 1. Traer socios sin importar si 'activo' está en minúscula, mayúscula o nulo
    sql_socios = """
        SELECT id, nro_socio, apellido, nombre, dni, COALESCE(estado, 'Activo') AS estado
        FROM socios 
        WHERE LOWER(COALESCE(estado, 'activo')) = 'activo'
        ORDER BY apellido ASC, nombre ASC;
    """
    socios = db.session.execute(text(sql_socios)).mappings().all()

    # Si por alguna razón no hubiese ninguno activo, traemos todos para que la lista nunca quede vacía
    if not socios:
        sql_todos = "SELECT id, nro_socio, apellido, nombre, dni FROM socios ORDER BY apellido ASC, nombre ASC;"
        socios = db.session.execute(text(sql_todos)).mappings().all()

    # 2. Traer cobradores para que el desplegable de cobrador no quede vacío
    try:
        sql_cobradores = "SELECT id, nombre, apellido FROM cobradores ORDER BY nombre ASC;"
        cobradores = db.session.execute(text(sql_cobradores)).mappings().all()
    except Exception:
        cobradores = []

    # 3. Fecha de hoy para el campo fecha_cobro
    hoy = str(date.today())

    return render_template(
        "registrar_cuota.html",
        socios=socios,
        cobradores=cobradores,
        hoy=hoy
    )

    # return render_template("registrar_cuota.html", socios=socios)
###FIN REGISTRO CUOTAS POR SOCIO
###CAMBIAR ESTADO DEL SOCIO
@app.route("/socios/<int:id>/cambiar-estado", methods=["POST"])
def cambiar_estado_socio(id):
    nuevo_estado = request.form.get("estado", "Activo")
    # Validamos únicamente los 3 estados institucionales
    if nuevo_estado not in ["Activo", "Baja", "Vitalicio"]:
        nuevo_estado = "Activo"

    try:
        db.session.execute(
            text("UPDATE socios SET estado = :estado WHERE id = :id;"),
            {"estado": nuevo_estado, "id": id}
        )
        db.session.commit()
        flash(f"Estado del socio actualizado a '{nuevo_estado}'.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al cambiar estado: {e}", "danger")

    return redirect(url_for("ficha_socio", id=id))
from datetime import datetime
#IMPRIMIR PADRON
@app.route("/socios/padron-imprimir")
def imprimir_padron():
    # Consulta de socios ordenada alfabéticamente por apellido y nombre
    sql_socios = """
        SELECT 
            id,
            COALESCE(nro_socio, id) AS nro_socio,
            apellido,
            nombre,
            dni,
            telefono,
            direccion,
            fecha_ingreso,
            COALESCE(estado, 'Activo') AS estado
        FROM socios
        ORDER BY apellido ASC, nombre ASC;
    """
    socios = db.session.execute(text(sql_socios)).mappings().all()

    # Conteos rápidos para el resumen del reporte
    total_socios = len(socios)
    total_activos = sum(1 for s in socios if (s.get("estado") or "").lower() == "activo")
    total_vitalicios = sum(1 for s in socios if (s.get("estado") or "").lower() == "vitalicio")
    total_bajas = sum(1 for s in socios if (s.get("estado") or "").lower() == "baja")

    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")

    return render_template(
        "padron_imprimir.html",
        socios=socios,
        total_socios=total_socios,
        total_activos=total_activos,
        total_vitalicios=total_vitalicios,
        total_bajas=total_bajas,
        fecha_emision=fecha_emision
    )
###Caja
from datetime import date

@app.route("/caja")
def caja_general():
    # 1. Obtener todos los movimientos ordenados por fecha descendente
    sql_movimientos = """
        SELECT 
            id,
            fecha,
            tipo,
            COALESCE(categoria, 'General') AS categoria,
            concepto,
            monto,
            COALESCE(comprobante, '-') AS comprobante,
            COALESCE(interviene, '-') AS interviene,
            COALESCE(metodo, 'Efectivo') AS metodo,
            observaciones
        FROM movimientos_caja
        ORDER BY fecha DESC, id DESC;
    """
    movimientos = db.session.execute(text(sql_movimientos)).mappings().all()

    # 2. Calcular totales
    total_ingresos = sum(float(m.get("monto") or 0) for m in movimientos if (m.get("tipo") or "").lower() == "ingreso")
    total_egresos = sum(float(m.get("monto") or 0) for m in movimientos if (m.get("tipo") or "").lower() == "egreso")
    saldo_actual = total_ingresos - total_egresos

    hoy = str(date.today())

    return render_template(
        "caja.html",
        movimientos=movimientos,
        total_ingresos=total_ingresos,
        total_egresos=total_egresos,
        saldo_actual=saldo_actual,
        hoy=hoy
    )


@app.route("/caja/exportar_excel", methods=["GET"])
def caja_exportar_excel():
    """Exporta los movimientos de caja a Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file
    import io
    from datetime import datetime

    # Obtener configuración
    config = cargar_config()
    nombre_inst = config.get("institucion", {}).get("nombre", "Centro de Jubilados y Pensionados")

    # Obtener todos los movimientos (sin filtro de fecha, todos los registrados)
    sql_movimientos = """
        SELECT 
            id,
            fecha,
            tipo,
            COALESCE(categoria, 'General') AS categoria,
            concepto,
            monto,
            COALESCE(comprobante, '-') AS comprobante,
            COALESCE(interviene, '-') AS interviene,
            COALESCE(metodo, 'Efectivo') AS metodo,
            observaciones
        FROM movimientos_caja
        ORDER BY fecha DESC, id DESC;
    """
    movimientos = db.session.execute(text(sql_movimientos)).mappings().all()

    # Crear el libro Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Libro de Caja"
    ws.views.sheetView[0].showGridLines = True

    # Estilos
    fuente_titulo = Font(name="Calibri", size=14, bold=True, color="1B365D")
    fuente_subtitulo = Font(name="Calibri", size=11, bold=True, color="495057")
    fuente_info = Font(name="Calibri", size=10, bold=True, color="0D6EFD")
    fuente_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    fuente_fila = Font(name="Calibri", size=10)
    fuente_negrita = Font(name="Calibri", size=10, bold=True)

    fill_header = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    fill_ingreso = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    fill_egreso = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
    fill_resumen = PatternFill(start_color="F1F3F5", end_color="F1F3F5", fill_type="solid")

    borde_fino = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC")
    )
    borde_doble_bottom = Border(bottom=Side(style="double", color="000000"), top=Side(style="thin", color="000000"))

    # Encabezado
    ws["A1"] = nombre_inst.upper()
    ws["A1"].font = fuente_titulo

    ws["A2"] = "LIBRO DIARIO DE CAJA - EXPORTACIÓN A EXCEL"
    ws["A2"].font = fuente_subtitulo

    ws["A3"] = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A3"].font = Font(name="Calibri", size=9, italic=True, color="6C757D")

    # Encabezados de la tabla (fila 5)
    headers = ["Fecha", "Tipo", "Categoría", "Concepto", "Comprobante", "Medio", "Importe ($)", "Interviene", "Observaciones"]
    fila_actual = 5

    for col_idx, header in enumerate(headers, 1):
        celda = ws.cell(row=fila_actual, column=col_idx, value=header)
        celda.font = fuente_header
        celda.fill = fill_header
        celda.alignment = Alignment(horizontal="center", vertical="center")
        celda.border = borde_fino

    fila_inicio_datos = fila_actual + 1

    for mov in movimientos:
        fila_actual += 1
        monto = float(mov["monto"] or 0)
        tipo = mov["tipo"] or "-"
        es_ingreso = str(tipo).strip().lower() == "ingreso"

        fecha_txt = ""
        if mov["fecha"]:
            if hasattr(mov["fecha"], "strftime"):
                fecha_txt = mov["fecha"].strftime("%d/%m/%Y")
            else:
                fecha_txt = str(mov["fecha"])

        valores = [
            fecha_txt,
            tipo,
            mov["categoria"] or "-",
            mov["concepto"] or "-",
            mov["comprobante"] or "-",
            mov["metodo"] or "-",
            monto if es_ingreso else None,
            None if es_ingreso else monto,
            mov["interviene"] or "-",
            mov["observaciones"] or "-"
        ]

        for col_idx, val in enumerate(valores, 1):
            celda = ws.cell(row=fila_actual, column=col_idx, value=val)
            celda.font = fuente_fila
            celda.border = borde_fino
            if col_idx in [1, 2, 3, 5, 6, 9]:
                celda.alignment = Alignment(horizontal="center")
            elif col_idx == 4:
                celda.alignment = Alignment(horizontal="left")
            elif col_idx in [7, 8]:
                celda.alignment = Alignment(horizontal="right")
                celda.number_format = "$#,##0.00"
                if val is not None:
                    celda.fill = fill_ingreso if col_idx == 7 else fill_egreso

    # Totales
    fila_actual += 1
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=6)
    c_tot = ws.cell(row=fila_actual, column=1, value="TOTALES:")
    c_tot.font = fuente_negrita
    c_tot.alignment = Alignment(horizontal="right")

    c_ing_tot = ws.cell(row=fila_actual, column=7, value=f"=SUM(G{fila_inicio_datos}:G{fila_actual-1})")
    c_ing_tot.font = fuente_negrita
    c_ing_tot.number_format = "$#,##0.00"
    c_ing_tot.alignment = Alignment(horizontal="right")
    c_ing_tot.border = borde_doble_bottom

    c_egr_tot = ws.cell(row=fila_actual, column=8, value=f"=SUM(H{fila_inicio_datos}:H{fila_actual-1})")
    c_egr_tot.font = fuente_negrita
    c_egr_tot.number_format = "$#,##0.00"
    c_egr_tot.alignment = Alignment(horizontal="right")
    c_egr_tot.border = borde_doble_bottom

    fila_actual += 1
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=6)
    c_saldo_txt = ws.cell(row=fila_actual, column=1, value="SALDO ACTUAL:")
    c_saldo_txt.font = fuente_negrita
    c_saldo_txt.alignment = Alignment(horizontal="right")

    c_saldo_val = ws.cell(row=fila_actual, column=7, value=f"=G{fila_actual-1}-H{fila_actual-1}")
    c_saldo_val.font = Font(name="Calibri", size=11, bold=True, color="004D40")
    c_saldo_val.number_format = "$#,##0.00"
    c_saldo_val.alignment = Alignment(horizontal="right")
    c_saldo_val.fill = fill_resumen
    c_saldo_val.border = borde_doble_bottom

    # Anchos de columnas
    anchos = {"A": 12, "B": 12, "C": 18, "D": 40, "E": 16, "F": 12, "G": 14, "H": 14, "I": 18, "J": 40}
    for col, w in anchos.items():
        ws.column_dimensions[col].width = w

    # Guardar en memoria y enviar
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    nombre_archivo = f"Libro_Caja_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nombre_archivo
    )


@app.route("/caja/nuevo-movimiento", methods=["POST"])
def registrar_movimiento_caja():
    tipo = request.form.get("tipo", "Egreso").strip()
    categoria = request.form.get("categoria", "Varios").strip()
    concepto = request.form.get("concepto", "").strip()
    monto = float(request.form.get("monto", 0) or 0)
    fecha = request.form.get("fecha") or str(date.today())
    comprobante = request.form.get("comprobante", "").strip()
    interviene = request.form.get("interviene", "").strip()
    metodo = request.form.get("metodo", "Efectivo").strip()
    observaciones = request.form.get("observaciones", "").strip()

    if monto <= 0 or not concepto:
        flash("Debe ingresar un concepto válido y un monto mayor a cero.", "warning")
        return redirect(url_for("caja_general"))

    try:
        sql_insert = """
            INSERT INTO movimientos_caja (
                fecha, tipo, categoria, concepto, monto, comprobante, interviene, metodo, observaciones
            )
            VALUES (
                :fecha, :tipo, :categoria, :concepto, :monto, :comprobante, :interviene, :metodo, :obs
            );
        """
        db.session.execute(text(sql_insert), {
            "fecha": fecha,
            "tipo": tipo,
            "categoria": categoria,
            "concepto": concepto,
            "monto": monto,
            "comprobante": comprobante,
            "interviene": interviene,
            "metodo": metodo,
            "obs": observaciones
        })
        db.session.commit()
        flash(f"{tipo} registrado correctamente en la Caja.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al registrar movimiento: {str(e)}", "danger")

    return redirect(url_for("caja_general"))
####
#RUTA BALANCE
import io
from datetime import date, datetime
from flask import send_file, request, render_template
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy import text

@app.route("/caja/balance", methods=["GET"])
def balance_periodico():
    hoy = date.today()
    primer_dia_mes = date(hoy.year, hoy.month, 1)

    fecha_desde = request.args.get("fecha_desde", primer_dia_mes.strftime("%Y-%m-%d"))
    fecha_hasta = request.args.get("fecha_hasta", hoy.strftime("%Y-%m-%d"))

    # 1. Total y cantidad específica de cuotas cobradas en el período
    sql_cuotas_periodo = """
        SELECT 
            COUNT(*) AS cantidad_cuotas,
            COALESCE(SUM(monto), 0) AS total_monto_cuotas
        FROM cobro_cuotas
        WHERE DATE(fecha_cobro) >= :desde 
          AND DATE(fecha_cobro) <= :hasta;
    """
    res_cuotas = db.session.execute(
        text(sql_cuotas_periodo), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().first()

    cantidad_cuotas = res_cuotas["cantidad_cuotas"] if res_cuotas else 0
    total_cuotas_monto = float(res_cuotas["total_monto_cuotas"] if res_cuotas else 0)

    # 2. Total Ingresos agrupados por concepto
    sql_ingresos = """
        SELECT 
            COALESCE(concepto, 'Cobro de Cuotas') AS concepto,
            COUNT(*) AS cantidad,
            SUM(monto) AS total
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'ingreso' 
          AND DATE(fecha) >= :desde 
          AND DATE(fecha) <= :hasta
        GROUP BY COALESCE(concepto, 'Cobro de Cuotas')
        ORDER BY total DESC;
    """
    ingresos_categoria = db.session.execute(
        text(sql_ingresos), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    # 3. Total Egresos agrupados por concepto
    sql_egresos = """
        SELECT 
            COALESCE(concepto, 'Gastos Operativos') AS concepto,
            COUNT(*) AS cantidad,
            SUM(monto) AS total
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'egreso' 
          AND DATE(fecha) >= :desde 
          AND DATE(fecha) <= :hasta
        GROUP BY COALESCE(concepto, 'Gastos Operativos')
        ORDER BY total DESC;
    """
    egresos_categoria = db.session.execute(
        text(sql_egresos), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    # 4. Cobranza consolidada por socio en el período
    sql_socios_cobros = """
        SELECT 
            s.id AS socio_id,
            COALESCE(s.nro_socio, s.id) AS nro_socio,
            s.apellido,
            s.nombre,
            s.dni,
            COUNT(c.id) AS cantidad_cuotas,
            STRING_AGG(DISTINCT c.periodo, ', ' ORDER BY c.periodo) AS periodos_pagados,
            MAX(c.fecha_cobro) AS ultima_fecha_pago,
            SUM(c.monto) AS total_pagado
        FROM cobro_cuotas c
        INNER JOIN socios s ON c.socio_id = s.id
        WHERE DATE(c.fecha_cobro) >= :desde 
          AND DATE(c.fecha_cobro) <= :hasta
        GROUP BY s.id, s.nro_socio, s.apellido, s.nombre, s.dni
        ORDER BY s.apellido ASC, s.nombre ASC;
    """
    socios_cobros = db.session.execute(
        text(sql_socios_cobros), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    # 5. Libro de movimientos: agrupa cuotas del mismo socio, fecha y comprobante base en 1 solo renglón
    sql_movimientos = """
        SELECT 
            MIN(m.id) AS id,
            DATE(m.fecha) AS fecha,
            'Ingreso' AS tipo,
            CASE 
                WHEN COUNT(m.id) > 1 THEN 
                    CONCAT(COUNT(m.id), ' cuotas - ', COALESCE(s.apellido || ', ' || s.nombre, 'Socio sin nombre'))
                ELSE MAX(m.concepto) 
            END AS concepto,
            CASE 
                WHEN COUNT(m.id) > 1 THEN SPLIT_PART(MAX(m.comprobante), '/', 1)
                ELSE MAX(m.comprobante) 
            END AS comprobante,
            SUM(m.monto) AS monto,
            CASE 
                WHEN COUNT(m.id) > 1 THEN 
                    CONCAT('Pago anual/múltiple: ', STRING_AGG(DISTINCT c.periodo, ', ' ORDER BY c.periodo))
                ELSE COALESCE(MAX(m.observaciones), '-')
            END AS observaciones
        FROM movimientos_caja m
        INNER JOIN cobro_cuotas c ON m.cuota_id = c.id
        INNER JOIN socios s ON c.socio_id = s.id
        WHERE LOWER(m.tipo) = 'ingreso'
          AND DATE(m.fecha) >= :desde 
          AND DATE(m.fecha) <= :hasta
        GROUP BY 
            DATE(m.fecha),
            s.id,
            s.apellido,
            s.nombre,
            SPLIT_PART(m.comprobante, '/', 1)

        UNION ALL

        SELECT 
            m.id,
            DATE(m.fecha) AS fecha,
            m.tipo,
            m.concepto,
            m.comprobante,
            m.monto,
            m.observaciones
        FROM movimientos_caja m
        WHERE NOT (LOWER(m.tipo) = 'ingreso' AND LOWER(m.concepto) LIKE 'cobro cuota%')
          AND DATE(m.fecha) >= :desde 
          AND DATE(fecha) <= :hasta

        ORDER BY fecha ASC, id ASC;
    """
    movimientos = db.session.execute(
        text(sql_movimientos), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    total_ingresos = sum(item["total"] for item in ingresos_categoria)
    total_egresos = sum(item["total"] for item in egresos_categoria)
    saldo_periodo = total_ingresos - total_egresos

    return render_template(
        "balance_periodico.html",
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        ingresos_cat=ingresos_categoria,
        egresos_cat=egresos_categoria,
        movimientos=movimientos,
        total_ingresos=total_ingresos,
        total_egresos=total_egresos,
        saldo_periodo=saldo_periodo,
        cantidad_cuotas=cantidad_cuotas,
        total_cuotas_monto=total_cuotas_monto,
        socios_cobros=socios_cobros
    )
    socios_cobros = db.session.execute(
        text(sql_socios_cobros), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()
    #fin cuotas consolidadas

    # 2. Total Egresos agrupados por concepto
    sql_egresos = """
        SELECT 
            COALESCE(concepto, 'Gastos Operativos') AS concepto,
            COUNT(*) AS cantidad,
            SUM(monto) AS total
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'egreso' 
          AND DATE(fecha) >= :desde 
          AND DATE(fecha) <= :hasta
        GROUP BY COALESCE(concepto, 'Gastos Operativos')
        ORDER BY total DESC;
    """
    egresos_categoria = db.session.execute(
        text(sql_egresos), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    # 3. Detalle cronológico de movimientos
    sql_movimientos = """
        SELECT id, fecha, tipo, concepto, comprobante, monto, observaciones
        FROM movimientos_caja
        WHERE DATE(fecha) >= :desde AND DATE(fecha) <= :hasta
        ORDER BY fecha ASC, id ASC;
    """
    movimientos = db.session.execute(
        text(sql_movimientos), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    total_ingresos = sum(item["total"] for item in ingresos_categoria)
    total_egresos = sum(item["total"] for item in egresos_categoria)
    saldo_periodo = total_ingresos - total_egresos

    return render_template(
        "balance_periodico.html",
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        ingresos_cat=ingresos_categoria,
        egresos_cat=egresos_categoria,
        movimientos=movimientos,
        total_ingresos=total_ingresos,
        total_egresos=total_egresos,
        saldo_periodo=saldo_periodo,
        cantidad_cuotas=cantidad_cuotas,
        total_cuotas_monto=total_cuotas_monto,
        socios_cobros=socios_cobros
    )


@app.route("/caja/balance/exportar_excel", methods=["GET"])
def exportar_balance_excel():
    hoy = date.today()
    primer_dia_mes = date(hoy.year, hoy.month, 1)

    fecha_desde = request.args.get("fecha_desde", primer_dia_mes.strftime("%Y-%m-%d"))
    fecha_hasta = request.args.get("fecha_hasta", hoy.strftime("%Y-%m-%d"))

    config = cargar_config()
    nombre_inst = config.get("institucion", {}).get("nombre", "Centro de Jubilados y Pensionados")

    # 1. Total y cantidad específica de cuotas cobradas
    sql_cuotas = """
        SELECT 
            COUNT(*) AS cantidad_cuotas,
            COALESCE(SUM(monto), 0) AS total_monto_cuotas
        FROM cobro_cuotas
        WHERE DATE(fecha_cobro) >= :desde 
          AND DATE(fecha_cobro) <= :hasta;
    """
    res_cuotas = db.session.execute(
        text(sql_cuotas), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().first()

    cant_cuotas = res_cuotas["cantidad_cuotas"] if res_cuotas else 0
    total_monto_cuotas = float(res_cuotas["total_monto_cuotas"] if res_cuotas else 0)

    # 2. Movimientos generales de caja
    # Las cuotas de un mismo socio cobradas en una misma fecha y comprobante base
    # (p. ej. un pago anual de 12 cuotas con un solo recibo) se consolidan en una
    # sola fila con el total acumulado, en lugar de generar una fila por cada mes.
    # Los movimientos no vinculados a cuotas se dejan como filas individuales.
    sql_movimientos = """
        SELECT 
            MIN(m.id) AS id,
            DATE(m.fecha) AS fecha,
            'Ingreso' AS tipo,
            CASE 
                WHEN COUNT(m.id) > 1 THEN 
                    CONCAT(COUNT(m.id), ' cuotas - ', COALESCE(s.apellido || ', ' || s.nombre, 'Socio sin nombre'))
                ELSE MAX(m.concepto) 
            END AS concepto,
            CASE 
                WHEN COUNT(m.id) > 1 THEN SPLIT_PART(MAX(m.comprobante), '/', 1)
                ELSE MAX(m.comprobante) 
            END AS comprobante,
            SUM(m.monto) AS monto,
            CASE 
                WHEN COUNT(m.id) > 1 THEN 
                    CONCAT('Pago anual/múltiple: ', STRING_AGG(DISTINCT c.periodo, ', ' ORDER BY c.periodo))
                ELSE COALESCE(MAX(m.observaciones), '-')
            END AS observaciones
        FROM movimientos_caja m
        INNER JOIN cobro_cuotas c ON m.cuota_id = c.id
        INNER JOIN socios s ON c.socio_id = s.id
        WHERE LOWER(m.tipo) = 'ingreso'
          AND DATE(m.fecha) >= :desde 
          AND DATE(m.fecha) <= :hasta
        GROUP BY 
            DATE(m.fecha),
            s.id,
            s.apellido,
            s.nombre,
            SPLIT_PART(m.comprobante, '/', 1)

        UNION ALL

        SELECT 
            m.id,
            DATE(m.fecha) AS fecha,
            m.tipo,
            m.concepto,
            m.comprobante,
            m.monto,
            m.observaciones
        FROM movimientos_caja m
        WHERE NOT (m.cuota_id IS NOT NULL AND LOWER(m.tipo) = 'ingreso')
          AND DATE(m.fecha) >= :desde 
          AND DATE(m.fecha) <= :hasta

        ORDER BY fecha ASC, id ASC;
    """
    movimientos = db.session.execute(
        text(sql_movimientos), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    # 3. Crear el libro Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance de Caja"
    ws.views.sheetView[0].showGridLines = True

    # Estilos compartidos
    fuente_titulo = Font(name="Calibri", size=14, bold=True, color="1B365D")
    fuente_subtitulo = Font(name="Calibri", size=11, bold=True, color="495057")
    fuente_info = Font(name="Calibri", size=10, bold=True, color="0D6EFD")
    fuente_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    fuente_fila = Font(name="Calibri", size=10)
    fuente_negrita = Font(name="Calibri", size=10, bold=True)
    
    fill_header = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    fill_ingreso = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    fill_egreso = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
    fill_resumen = PatternFill(start_color="F1F3F5", end_color="F1F3F5", fill_type="solid")

    borde_fino = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC")
    )
    borde_doble_bottom = Border(bottom=Side(style="double", color="000000"), top=Side(style="thin", color="000000"))

    # Encabezado Hoja 1: Balance de Caja
    ws["A1"] = nombre_inst.upper()
    ws["A1"].font = fuente_titulo

    ws["A2"] = f"BALANCE DE CAJA: {fecha_desde} al {fecha_hasta}"
    ws["A2"].font = fuente_subtitulo

    ws["A3"] = f"Cuotas sociales cobradas en el período: {cant_cuotas} comprobante(s) | Total recaudado: ${total_monto_cuotas:,.2f}"
    ws["A3"].font = fuente_info

    ws["A4"] = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A4"].font = Font(name="Calibri", size=9, italic=True, color="6C757D")

    # Encabezados de la tabla (fila 6)
    headers = ["Fecha", "Tipo", "Concepto", "Comprobante", "Ingreso ($)", "Egreso ($)", "Detalle / Observación"]
    fila_actual = 6

    for col_idx, header in enumerate(headers, 1):
        celda = ws.cell(row=fila_actual, column=col_idx, value=header)
        celda.font = fuente_header
        celda.fill = fill_header
        celda.alignment = Alignment(horizontal="center" if col_idx in [1, 2, 4] else ("right" if col_idx in [5, 6] else "left"), vertical="center")
        celda.border = borde_fino

    fila_inicio_datos = fila_actual + 1

    for mov in movimientos:
        fila_actual += 1
        monto = float(mov["monto"] or 0)
        es_ingreso = (str(mov["tipo"] or "").strip().lower() == "ingreso")
        
        val_ing = monto if es_ingreso else None
        val_egr = monto if not es_ingreso else None

        f_txt = mov["fecha"].strftime("%d/%m/%Y") if mov["fecha"] and hasattr(mov["fecha"], "strftime") else str(mov["fecha"] or "")

        valores = [
            f_txt,
            mov["tipo"],
            mov["concepto"] or "-",
            mov["comprobante"] or "-",
            val_ing,
            val_egr,
            mov["observaciones"] or "-"
        ]

        for col_idx, val in enumerate(valores, 1):
            celda = ws.cell(row=fila_actual, column=col_idx, value=val)
            celda.font = fuente_fila
            celda.border = borde_fino
            if col_idx in [1, 2, 4]:
                celda.alignment = Alignment(horizontal="center")
            elif col_idx in [5, 6]:
                celda.alignment = Alignment(horizontal="right")
                celda.number_format = "$#,##0.00"
                if col_idx == 5 and val is not None:
                    celda.fill = fill_ingreso
                elif col_idx == 6 and val is not None:
                    celda.fill = fill_egreso

    # Totales y Saldo final en Hoja 1
    fila_actual += 1
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=4)
    c_tot = ws.cell(row=fila_actual, column=1, value="TOTALES DEL PERÍODO:")
    c_tot.font = fuente_negrita
    c_tot.alignment = Alignment(horizontal="right")

    c_ing_tot = ws.cell(row=fila_actual, column=5, value=f"=SUM(E{fila_inicio_datos}:E{fila_actual-1})")
    c_ing_tot.font = fuente_negrita
    c_ing_tot.number_format = "$#,##0.00"
    c_ing_tot.alignment = Alignment(horizontal="right")
    c_ing_tot.border = borde_doble_bottom

    c_egr_tot = ws.cell(row=fila_actual, column=6, value=f"=SUM(F{fila_inicio_datos}:F{fila_actual-1})")
    c_egr_tot.font = fuente_negrita
    c_egr_tot.number_format = "$#,##0.00"
    c_egr_tot.alignment = Alignment(horizontal="right")
    c_egr_tot.border = borde_doble_bottom

    fila_actual += 1
    ws.merge_cells(start_row=fila_actual, start_column=1, end_row=fila_actual, end_column=5)
    c_saldo_txt = ws.cell(row=fila_actual, column=1, value="SALDO NETO SUPERÁVIT / (DÉFICIT):")
    c_saldo_txt.font = fuente_negrita
    c_saldo_txt.alignment = Alignment(horizontal="right")

    c_saldo_val = ws.cell(row=fila_actual, column=6, value=f"=E{fila_actual-1}-F{fila_actual-1}")
    c_saldo_val.font = Font(name="Calibri", size=11, bold=True, color="004D40")
    c_saldo_val.number_format = "$#,##0.00"
    c_saldo_val.alignment = Alignment(horizontal="right")
    c_saldo_val.fill = fill_resumen
    c_saldo_val.border = borde_doble_bottom

    # Ancho de columnas Hoja 1
    anchos = {"A": 13, "B": 12, "C": 28, "D": 16, "E": 16, "F": 16, "G": 32}
    for col, w in anchos.items():
        ws.column_dimensions[col].width = w

    # =========================================================================
    # NUEVO BLOQUE: PESTAÑA 2 - DETALLE DE CUOTAS POR SOCIO
    # =========================================================================
    sql_socios_cobros = """
        SELECT 
            COALESCE(s.nro_socio, s.id) AS nro_socio,
            s.apellido,
            s.nombre,
            s.dni,
            COUNT(c.id) AS cantidad_cuotas,
            STRING_AGG(DISTINCT c.periodo, ', ' ORDER BY c.periodo) AS periodos_pagados,
            MAX(c.fecha_cobro) AS ultima_fecha_pago,
            SUM(c.monto) AS total_pagado
        FROM cobro_cuotas c
        INNER JOIN socios s ON c.socio_id = s.id
        WHERE DATE(c.fecha_cobro) >= :desde 
          AND DATE(c.fecha_cobro) <= :hasta
        GROUP BY s.id, s.nro_socio, s.apellido, s.nombre, s.dni
        ORDER BY s.apellido ASC, s.nombre ASC;
    """
    socios_cobros = db.session.execute(
        text(sql_socios_cobros), {"desde": fecha_desde, "hasta": fecha_hasta}
    ).mappings().all()

    ws_socios = wb.create_sheet(title="Cuotas por Socio")
    ws_socios.views.sheetView[0].showGridLines = True

    ws_socios["A1"] = f"{nombre_inst.upper()} - DETALLE DE CUOTAS POR SOCIO"
    ws_socios["A1"].font = fuente_titulo
    ws_socios["A2"] = f"Período: {fecha_desde} al {fecha_hasta}"
    ws_socios["A2"].font = fuente_subtitulo

    headers_socios = ["N° Socio", "Apellido", "Nombre", "DNI", "Cant. Cuotas", "Períodos Abonados", "Último Pago", "Total Aportado ($)"]
    fila_s = 4

    for col_idx, h in enumerate(headers_socios, 1):
        c = ws_socios.cell(row=fila_s, column=col_idx, value=h)
        c.font = fuente_header
        c.fill = fill_header
        c.alignment = Alignment(horizontal="center" if col_idx in [1, 4, 5, 7] else ("right" if col_idx == 8 else "left"), vertical="center")
        c.border = borde_fino

    fila_s_inicio = fila_s + 1
    for sc in socios_cobros:
        fila_s += 1
        f_pago = sc["ultima_fecha_pago"].strftime("%d/%m/%Y") if sc["ultima_fecha_pago"] and hasattr(sc["ultima_fecha_pago"], "strftime") else str(sc["ultima_fecha_pago"] or "")
        
        datos_fila = [
            sc["nro_socio"],
            sc["apellido"],
            sc["nombre"],
            sc["dni"] or "-",
            sc["cantidad_cuotas"],
            sc["periodos_pagados"] or "Cuota Social",
            f_pago,
            float(sc["total_pagado"] or 0)
        ]
        for col_idx, val in enumerate(datos_fila, 1):
            c = ws_socios.cell(row=fila_s, column=col_idx, value=val)
            c.font = fuente_fila
            c.border = borde_fino
            if col_idx in [1, 4, 5, 7]:
                c.alignment = Alignment(horizontal="center")
            elif col_idx == 8:
                c.alignment = Alignment(horizontal="right")
                c.number_format = "$#,##0.00"
                c.fill = fill_ingreso

    if len(socios_cobros) > 0:
        fila_s += 1
        ws_socios.merge_cells(start_row=fila_s, start_column=1, end_row=fila_s, end_column=7)
        c_tot_s = ws_socios.cell(row=fila_s, column=1, value="TOTAL GENERAL RECAUDADO EN CUOTAS:")
        c_tot_s.font = fuente_negrita
        c_tot_s.alignment = Alignment(horizontal="right")

        c_tot_monto = ws_socios.cell(row=fila_s, column=8, value=f"=SUM(H{fila_s_inicio}:H{fila_s-1})")
        c_tot_monto.font = fuente_negrita
        c_tot_monto.alignment = Alignment(horizontal="right")
        c_tot_monto.number_format = "$#,##0.00"
        c_tot_monto.border = borde_doble_bottom

    anchos_s = {"A": 10, "B": 20, "C": 20, "D": 14, "E": 14, "F": 35, "G": 14, "H": 18}
    for col, w in anchos_s.items():
        ws_socios.column_dimensions[col].width = w
    # =========================================================================

    # 4. Guardar y enviar archivo
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    nombre_descarga = f"Balance_Caja_{fecha_desde}_al_{fecha_hasta}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nombre_descarga
    )
#FIN RUTA BALANCE - exportar a excel
###
if __name__ == "__main__":
    app.run(debug=True)