from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for, current_app
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os
import io
import re
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from auth_manager import admin_required, login_required
from models import db
from config import (
    DOCUMENTOS_UPLOAD_FOLDER, FOTOS_PORTAL_UPLOAD_FOLDER, cargar_config,
)

socios_bp = Blueprint("socios", __name__)

NOMBRES_MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)


def _periodos_cubiertos(cobro):
    periodo = str(cobro.get("periodo") or "").strip().lower()
    try:
        anio = int(cobro.get("anio")) if cobro.get("anio") else None
    except (TypeError, ValueError):
        anio = None
    if not anio:
        fecha_cobro = cobro.get("fecha_cobro")
        anio = fecha_cobro.year if hasattr(fecha_cobro, "year") else None
    anio_en_periodo = re.search(r"\b(?:19|20)\d{2}\b", periodo)
    if anio_en_periodo:
        anio = int(anio_en_periodo.group())

    try:
        mes = int(cobro.get("mes")) if cobro.get("mes") else None
    except (TypeError, ValueError):
        mes = None
    if mes and 1 <= mes <= 12 and anio:
        return {(anio, mes)}

    mapa_meses = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
        "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    }
    mes_encontrado = next(
        (numero for prefijo, numero in mapa_meses.items() if periodo.startswith(prefijo)),
        None,
    )
    if mes_encontrado and anio:
        return {(anio, mes_encontrado)}
    if not anio:
        return set()
    if any(palabra in periodo for palabra in ("anual", "año", "completo")):
        return {(anio, numero) for numero in range(1, 13)}
    if "semestre" in periodo:
        if "segundo" in periodo or re.search(r"\b2(?:do|°|º)?\s*semestre\b", periodo) or re.search(
            r"\bsemestre\s*2\b", periodo
        ):
            return {(anio, numero) for numero in range(7, 13)}
        if "primer" in periodo or re.search(r"\b1(?:er|ro|°|º)?\s*semestre\b", periodo) or re.search(
            r"\bsemestre\s*1\b", periodo
        ):
            return {(anio, numero) for numero in range(1, 7)}
    return set()


def _cuotas_del_mismo_cobro(cuota):
    if not cuota.get("nro_recibo"):
        return [cuota]
    return db.session.execute(text("""
        SELECT id, monto, periodo, mes, anio
        FROM cobro_cuotas
        WHERE nro_recibo = :nro_recibo
          AND socio_id = :socio_id
          AND fecha_cobro = :fecha_cobro
          AND tipo_concepto IS NOT DISTINCT FROM :tipo_concepto
        ORDER BY anio, mes, id;
    """), {
        "nro_recibo": cuota["nro_recibo"],
        "socio_id": cuota["socio_id"],
        "fecha_cobro": cuota["fecha_cobro"],
        "tipo_concepto": cuota.get("tipo_concepto"),
    }).mappings().all()


def _obtener_matriz_cuotas(anio, busqueda=""):
    socios_sql = """
        SELECT id, nro_socio, apellido, nombre, dni, telefono,
               COALESCE(estado, 'Activo') AS estado
        FROM socios
        WHERE LOWER(TRIM(COALESCE(estado, 'Activo'))) <> 'baja'
    """
    params = {"anio": anio}
    if busqueda:
        socios_sql += """
          AND (apellido ILIKE :busqueda OR nombre ILIKE :busqueda
               OR CAST(nro_socio AS TEXT) ILIKE :busqueda
               OR CAST(id AS TEXT) ILIKE :busqueda)
        """
        params["busqueda"] = f"%{busqueda}%"
    socios_sql += " ORDER BY apellido ASC, nombre ASC;"
    socios = db.session.execute(text(socios_sql), params).mappings().all()

    cobros = db.session.execute(text("""
        SELECT socio_id, mes, periodo, anio, fecha_cobro,
               LOWER(COALESCE(tipo_concepto, 'cuota')) AS concepto, monto
        FROM cobro_cuotas
        WHERE (anio = :anio OR (anio IS NULL AND EXTRACT(YEAR FROM fecha_cobro) = :anio))
          AND (LOWER(estado) = 'pagado' OR estado IS NULL);
    """), {"anio": anio}).mappings().all()

    pagos_por_socio = {}
    for cobro in cobros:
        pagos_por_socio.setdefault(cobro["socio_id"], []).append(cobro)

    matriz = []
    total_socios_activos = 0
    for socio in socios:
        if (socio["estado"] or "").lower() == "activo":
            total_socios_activos += 1

        meses_cubiertos = set()
        montos_por_mes = [Decimal("0.00")] * 12
        tiene_inscripcion = False
        total_abonado = 0.0
        for cobro in pagos_por_socio.get(socio["id"], []):
            monto_cobro = Decimal(str(cobro["monto"] or 0))
            total_abonado += float(monto_cobro)
            concepto = str(cobro["concepto"] or "").lower()
            periodo = str(cobro["periodo"] or "").strip().lower()
            if "inscrip" in concepto or "inscrip" in periodo:
                tiene_inscripcion = True
            periodos_cubiertos = sorted(_periodos_cubiertos(cobro))
            if not periodos_cubiertos:
                continue
            importe_mensual = (monto_cobro / len(periodos_cubiertos)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            importes = [importe_mensual] * (len(periodos_cubiertos) - 1)
            importes.append(monto_cobro - sum(importes, Decimal("0.00")))
            for (anio_cubierto, mes_cubierto), importe in zip(periodos_cubiertos, importes):
                if anio_cubierto == anio:
                    meses_cubiertos.add(mes_cubierto)
                    montos_por_mes[mes_cubierto - 1] += importe

        matriz.append({
            **socio,
            "inscripcion": tiene_inscripcion,
            "meses": [mes in meses_cubiertos for mes in range(1, 13)],
            "montos_por_mes": montos_por_mes,
            "total_abonado": total_abonado,
        })
    return matriz, total_socios_activos


def _texto_pdf(texto):
    contenido = str(texto).encode("cp1252", errors="replace")
    contenido = contenido.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + contenido + b")"


def _generar_pdf_matriz(matriz, anio):
    ancho_pagina, alto_pagina = 842, 595
    anchos_columnas = [42, 142, 42] + [34] * 12 + [58]
    ancho_tabla = sum(anchos_columnas)
    inicio_x = (ancho_pagina - ancho_tabla) / 2
    alto_fila = 18
    encabezado = ["Socio", "Apellido y Nombre", "Inscrip."] + [
        nombre[:3] for nombre in NOMBRES_MESES
    ] + ["Total"]
    filas_por_pagina = 27
    grupos = [
        matriz[inicio:inicio + filas_por_pagina]
        for inicio in range(0, len(matriz), filas_por_pagina)
    ] or [[]]

    contenidos = []
    for numero_pagina, filas in enumerate(grupos, start=1):
        comandos = []
        y = alto_pagina - 54
        comandos.extend([
            "0 0 0 rg",
            f"BT /F1 14 Tf {inicio_x:.2f} {alto_pagina - 30} Td ".encode("ascii")
            + _texto_pdf(f"Matriz anual de cuotas - {anio}") + b" Tj ET",
            f"BT /F1 8 Tf {inicio_x:.2f} {alto_pagina - 43} Td ".encode("ascii")
            + _texto_pdf(f"Socios incluidos: {len(matriz)}") + b" Tj ET",
        ])
        x = inicio_x
        comandos.append("0.12 0.25 0.42 rg")
        for ancho, texto in zip(anchos_columnas, encabezado):
            comandos.append(f"{x:.2f} {y - alto_fila + 3} {ancho:.2f} {alto_fila} re f")
            comandos.append(
                f"BT /F1 7 Tf 1 1 1 rg {x + 3:.2f} {y - 11:.2f} Td ".encode("ascii")
                + _texto_pdf(texto) + b" Tj ET"
            )
            x += ancho
        y -= alto_fila

        for indice, socio in enumerate(filas):
            x = inicio_x
            if indice % 2:
                comandos.append("0.94 0.96 0.98 rg")
                comandos.append(f"{inicio_x:.2f} {y - alto_fila + 3} {ancho_tabla:.2f} {alto_fila} re f")
            valores = [
                f"#{socio.get('nro_socio') or socio['id']}",
                f"{socio.get('apellido') or ''}, {socio.get('nombre') or ''}"[:30],
                "Si" if socio["inscripcion"] else "-",
                *["X" if mes_pagado else "-" for mes_pagado in socio["meses"]],
                f"${socio['total_abonado']:,.2f}",
            ]
            comandos.append("0 0 0 rg")
            for ancho, valor in zip(anchos_columnas, valores):
                comandos.append(
                    f"BT /F1 7 Tf {x + 3:.2f} {y - 11:.2f} Td ".encode("ascii")
                    + _texto_pdf(valor) + b" Tj ET"
                )
                x += ancho
            y -= alto_fila

        comandos.append(
            f"BT /F1 7 Tf {inicio_x:.2f} 22 Td ".encode("ascii")
            + _texto_pdf(f"Página {numero_pagina} de {len(grupos)}") + b" Tj ET"
        )
        contenidos.append(b"\n".join(
            item if isinstance(item, bytes) else item.encode("ascii")
            for item in comandos
        ))

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" + b" ".join(
            f"{4 + indice * 2} 0 R".encode("ascii") for indice in range(len(grupos))
        ) + b"] /Count " + str(len(grupos)).encode("ascii") + b" >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for indice, contenido in enumerate(contenidos):
        id_pagina = 4 + indice * 2
        id_contenido = id_pagina + 1
        objetos.extend([
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ancho_pagina} {alto_pagina}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {id_contenido} 0 R >>"
            ).encode("ascii"),
            b"<< /Length " + str(len(contenido)).encode("ascii")
            + b" >>\nstream\n" + contenido + b"\nendstream",
        ])

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for numero, objeto in enumerate(objetos, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{numero} 0 obj\n".encode("ascii"))
        pdf.extend(objeto)
        pdf.extend(b"\nendobj\n")
    posicion_xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{posicion_xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


@socios_bp.route("/", methods=["GET", "POST"])
def portal_socios():
    socio_encontrado = None
    cuotas_socio = []
    ultimo_pago = None
    busqueda_realizada = False
    termino_busqueda = ""
    es_cumpleanos_hoy = False
    es_mes_cumpleanos = False

    config = cargar_config()
    comision = config.get("comision_directiva", [])
    hoy = date.today()

    sql_novedades = """
        SELECT id, titulo, contenido, imagen, fecha_publicacion
        FROM novedades
        WHERE activa = TRUE
        ORDER BY orden DESC, fecha_publicacion DESC
        LIMIT 6;
    """
    novedades = db.session.execute(text(sql_novedades)).mappings().all()

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

    def _calcular_edad(fn):
        if not fn:
            return None
        try:
            fn_date = datetime.strptime(fn[:10], "%Y-%m-%d").date() if isinstance(fn, str) else fn
            return hoy.year - fn_date.year - ((hoy.month, hoy.day) < (fn_date.month, fn_date.day))
        except Exception:
            return None

    cumple_hoy_con_edad = [dict(c, edad=_calcular_edad(c.get("fecha_nacimiento"))) for c in cumple_hoy]
    cumple_mes_con_edad = [dict(m, edad=_calcular_edad(m.get("fecha_nacimiento"))) for m in cumple_mes]

    sql_archivos = """
        SELECT id, titulo, descripcion, tipo, archivo, fecha_subida
        FROM archivos_portal
        WHERE activa = TRUE
        ORDER BY tipo, orden DESC, fecha_subida DESC;
    """
    archivos_portal = db.session.execute(text(sql_archivos)).mappings().all()
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
                fn = socio_encontrado.get("fecha_nacimiento")
                if fn:
                    try:
                        fn_date = datetime.strptime(fn[:10], "%Y-%m-%d").date() if isinstance(fn, str) else fn
                        if fn_date.day == hoy.day and fn_date.month == hoy.month:
                            es_cumpleanos_hoy = True
                        elif fn_date.month == hoy.month:
                            es_mes_cumpleanos = True
                    except Exception:
                        pass

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


@socios_bp.route("/socios/cumpleanos")
@admin_required
def cumpleanos_socios():
    hoy = date.today()
    mes_actual = hoy.month
    dia_actual = hoy.day
    mes_filtro = int(request.args.get("mes", mes_actual))

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


@socios_bp.route("/archivos-portal/descargar/<int:id>")
def descargar_archivo_portal(id):
    sql = "SELECT archivo, tipo, titulo FROM archivos_portal WHERE id = :id AND activa = TRUE;"
    archivo = db.session.execute(text(sql), {"id": id}).mappings().first()
    if not archivo:
        flash("Archivo no encontrado o no disponible.", "warning")
        return redirect(url_for("socios.portal_socios"))

    carpeta = DOCUMENTOS_UPLOAD_FOLDER if archivo["tipo"] in ("estatuto", "memoria_balance") else FOTOS_PORTAL_UPLOAD_FOLDER
    ruta = os.path.join(carpeta, archivo["archivo"])
    if not os.path.exists(ruta):
        flash("El archivo físico no existe en el servidor.", "warning")
        return redirect(url_for("socios.portal_socios"))

    return send_file(
        ruta,
        as_attachment=True,
        download_name=f"{archivo['titulo']}.{archivo['archivo'].rsplit('.', 1)[1].lower()}"
    )


@socios_bp.route("/socios")
@admin_required
def listar_socios():
    try:
        db.session.execute(text("UPDATE socios SET nro_socio = id WHERE nro_socio IS NULL;"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    sql_socios = """
        SELECT id, COALESCE(nro_socio, id) AS nro_socio, apellido, nombre, dni, telefono, direccion, fecha_ingreso, COALESCE(estado, 'Activo') AS estado
        FROM socios
        ORDER BY apellido ASC, nombre ASC;
    """
    socios = db.session.execute(text(sql_socios)).mappings().all()
    return render_template("listar_socios.html", socios=socios)


@socios_bp.route("/socios/<int:id>")
@admin_required
def ficha_socio(id):
    socio = db.session.execute(text("SELECT * FROM socios WHERE id = :id;"), {"id": id}).mappings().first()
    if not socio:
        flash(f"El socio con ID {id} no fue encontrado.", "warning")
        return redirect(url_for("socios.listar_socios"))

    sql_cuotas = """
        SELECT id, fecha_cobro, periodo, anio, monto, COALESCE(nro_recibo, '-') AS comprobante, COALESCE(metodo_pago, 'Efectivo') AS metodo, COALESCE(estado, 'PAGADO') AS estado, observaciones
        FROM cobro_cuotas
        WHERE socio_id = :socio_id
        ORDER BY fecha_cobro DESC, id DESC;
    """
    cuotas = db.session.execute(text(sql_cuotas), {"socio_id": id}).mappings().all()
    total_aportado = sum(float(c.get("monto") or 0) for c in cuotas if str(c.get("estado", "")).lower() == 'pagado')

    return render_template("ficha_socio.html", socio=socio, cuotas=cuotas, total_aportado=total_aportado)


@socios_bp.route("/socios/<int:id>/eliminar", methods=["POST"])
@admin_required
def eliminar_socio(id):
    try:
        socio_existe = db.session.execute(
            text("SELECT 1 FROM socios WHERE id = :id;"), {"id": id}
        ).scalar_one_or_none()
        if socio_existe is None:
            db.session.rollback()
            flash("El socio no fue encontrado; no se realizó ningún cambio.", "warning")
            return redirect(url_for("socios.listar_socios"))

        cantidad_cuotas_validas = db.session.execute(
            text("""
                SELECT COUNT(*)
                FROM cobro_cuotas
                WHERE socio_id = :id
                  AND UPPER(TRIM(COALESCE(estado, 'PAGADO'))) <> 'ANULADO';
            """),
            {"id": id},
        ).scalar_one()
        if cantidad_cuotas_validas:
            db.session.execute(
                text("UPDATE socios SET estado = 'Baja' WHERE id = :id;"), {"id": id}
            )
            db.session.commit()
            flash(
                f"No se puede borrar definitivamente: el socio tiene {cantidad_cuotas_validas} "
                "cuota(s) no anulada(s). Se conservó su historial y el socio quedó con estado Baja.",
                "warning",
            )
            return redirect(url_for("socios.ficha_socio", id=id))

        db.session.execute(text("""
            DELETE FROM cobro_cuotas
            WHERE socio_id = :id
              AND UPPER(TRIM(COALESCE(estado, 'PAGADO'))) = 'ANULADO';
        """), {"id": id})
        eliminado = db.session.execute(
            text("DELETE FROM socios WHERE id = :id RETURNING id;"), {"id": id}
        ).scalar_one_or_none()
        if eliminado is None:
            db.session.rollback()
            flash("No se pudo eliminar el socio. Inténtelo nuevamente.", "danger")
            return redirect(url_for("socios.ficha_socio", id=id))

        db.session.commit()
        flash("El socio y sus comprobantes anulados fueron eliminados definitivamente.", "success")
        return redirect(url_for("socios.listar_socios"))
    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning(
            "No se pudo eliminar el socio %s porque tiene registros relacionados", id, exc_info=True
        )
        flash(
            "No se pudo borrar el socio porque tiene otros registros relacionados. "
            "No se eliminó ningún dato.",
            "warning",
        )
        return redirect(url_for("socios.ficha_socio", id=id))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("No se pudo eliminar el socio %s", id)
        flash("No se pudo eliminar el socio. Inténtelo nuevamente.", "danger")
        return redirect(url_for("socios.ficha_socio", id=id))


@socios_bp.route("/socios/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_socio():
    if request.method == "POST":
        apellido = request.form.get("apellido", "").strip().upper()
        nombre = request.form.get("nombre", "").strip().title()
        dni = request.form.get("dni", "").strip()
        fecha_nacimiento = request.form.get("fecha_nacimiento") or None
        telefono = request.form.get("telefono", "").strip()
        whatsapp_autorizado = request.form.get("whatsapp_autorizado") == "on"
        email = request.form.get("email", "").strip()
        direccion = request.form.get("direccion", "").strip()
        fecha_ingreso = request.form.get("fecha_ingreso") or date.today()
        estado = request.form.get("estado", "Activo")
        observaciones = request.form.get("observaciones", "").strip()

        try:
            sql_insert = text("""
                INSERT INTO socios (
                    apellido, nombre, dni, fecha_nacimiento, telefono, whatsapp_autorizado,
                    whatsapp_autorizado_en, email, direccion, fecha_ingreso, estado, observaciones
                )
                VALUES (
                    :apellido, :nombre, :dni, :fecha_nacimiento, :telefono, :whatsapp_autorizado,
                    CASE WHEN :whatsapp_autorizado THEN NOW() ELSE NULL END,
                    :email, :direccion, :fecha_ingreso, :estado, :observaciones
                )
                RETURNING id;
            """)
            res = db.session.execute(sql_insert, {
                "apellido": apellido, "nombre": nombre, "dni": dni, "fecha_nacimiento": fecha_nacimiento,
                "telefono": telefono, "whatsapp_autorizado": whatsapp_autorizado,
                "email": email, "direccion": direccion, "fecha_ingreso": fecha_ingreso,
                "estado": estado, "observaciones": observaciones
            })
            nuevo_id = res.fetchone()[0]
            db.session.execute(text("UPDATE socios SET nro_socio = :id WHERE id = :id;"), {"id": nuevo_id})
            db.session.commit()

            flash(f"Socio N° {nuevo_id} ({apellido}, {nombre}) registrado exitosamente.", "success")
            return redirect(url_for("socios.listar_socios"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("No se pudo registrar el socio")
            flash("No se pudo registrar el socio. Verifique los datos e inténtelo nuevamente.", "danger")

    return render_template("socio_form.html", socio=None)


@socios_bp.route("/socios/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_socio(id):
    socio = db.session.execute(
        text("SELECT * FROM socios WHERE id = :id;"),
        {"id": id},
    ).mappings().first()
    if not socio:
        flash("El socio que desea modificar no fue encontrado.", "warning")
        return redirect(url_for("socios.listar_socios"))
    socio = dict(socio)

    if request.method == "POST":
        try:
            nro_socio_form = request.form.get("nro_socio", "").strip()
            nro_socio = int(nro_socio_form) if nro_socio_form else None
            apellido = request.form.get("apellido", "").strip()
            nombre = request.form.get("nombre", "").strip()
            dni = request.form.get("dni", "").strip()
            if not apellido or not nombre or not dni:
                raise ValueError("Apellido, nombre y DNI son obligatorios.")
            if nro_socio is not None and nro_socio <= 0:
                raise ValueError("El número de socio debe ser mayor que cero.")

            estado = request.form.get("estado", "Activo")
            if estado not in {"Activo", "Inactivo", "Vitalicio", "Baja"}:
                raise ValueError("Seleccione un estado válido.")

            fecha_nacimiento_raw = request.form.get("fecha_nacimiento", "").strip()
            fecha_ingreso_raw = request.form.get("fecha_ingreso", "").strip()
            fecha_nacimiento = (
                datetime.strptime(fecha_nacimiento_raw, "%Y-%m-%d").date()
                if fecha_nacimiento_raw else None
            )
            fecha_ingreso = (
                datetime.strptime(fecha_ingreso_raw, "%Y-%m-%d").date()
                if fecha_ingreso_raw else None
            )

            db.session.execute(text("""
                UPDATE socios
                SET nro_socio = :nro_socio, apellido = :apellido, nombre = :nombre, dni = :dni,
                    fecha_nacimiento = :fecha_nacimiento, fecha_ingreso = :fecha_ingreso,
                    telefono = :telefono, whatsapp_autorizado = :whatsapp_autorizado,
                    whatsapp_autorizado_en = CASE
                        WHEN :whatsapp_autorizado THEN COALESCE(whatsapp_autorizado_en, NOW())
                        ELSE NULL
                    END,
                    email = :email, direccion = :direccion,
                    estado = :estado, observaciones = :observaciones
                WHERE id = :id;
            """), {
                "id": id,
                "nro_socio": nro_socio,
                "apellido": apellido,
                "nombre": nombre,
                "dni": dni,
                "fecha_nacimiento": fecha_nacimiento,
                "fecha_ingreso": fecha_ingreso,
                "telefono": request.form.get("telefono", "").strip(),
                "whatsapp_autorizado": request.form.get("whatsapp_autorizado") == "on",
                "email": request.form.get("email", "").strip(),
                "direccion": request.form.get("direccion", "").strip(),
                "estado": estado,
                "observaciones": request.form.get("observaciones", "").strip(),
            })
            db.session.commit()
            flash("Datos del socio actualizados correctamente.", "success")
            return redirect(url_for("socios.ficha_socio", id=id))
        except (TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error) or "Revise los datos ingresados.", "warning")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("No se pudieron actualizar los datos del socio %s", id)
            flash("No se pudieron guardar los cambios. Revise que el DNI o número de socio no estén duplicados.", "danger")
        for campo in (
            "nro_socio", "apellido", "nombre", "dni", "fecha_nacimiento",
            "fecha_ingreso", "telefono", "email", "direccion", "estado", "observaciones",
        ):
            if campo in request.form:
                socio[campo] = request.form.get(campo, "").strip()
        socio["whatsapp_autorizado"] = request.form.get("whatsapp_autorizado") == "on"

    return render_template("editar_socio.html", socio=socio)


@socios_bp.route("/socios/morosidad")
@admin_required
def control_morosidad():
    config = cargar_config()
    reglas = config.get("reglas_negocio", {})
    valor_cuota = float(reglas.get("valor_cuota_mensual", 200.0) or 200.0)

    hoy = date.today()
    mes_actual = hoy.month
    anio_actual = hoy.year

    sql_morosos = """
        SELECT s.id, COALESCE(s.nro_socio, s.id) AS nro_socio, s.apellido, s.nombre, s.dni, s.telefono, s.direccion, s.estado, s.fecha_ingreso,
               MAX(c.anio) AS ultimo_anio_pago, MAX(c.fecha_cobro) AS ultima_fecha_cobro
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
        if not ultimo_anio:
            meses_deuda = 12
            estado_mora = "Sin Pagos Registrados"
            badge_class = "danger"
        else:
            anios_dif = anio_actual - ultimo_anio
            if anios_dif > 0:
                meses_deuda = (anios_dif * 12) + mes_actual
                estado_mora = f"Debe años anteriores ({ultimo_anio})"
                badge_class = "danger"
            else:
                sql_pagos_anio = "SELECT periodo FROM cobro_cuotas WHERE socio_id = :socio_id AND anio = :anio GROUP BY periodo;"
                pagos = db.session.execute(text(sql_pagos_anio), {"socio_id": s["id"], "anio": anio_actual}).mappings().all()
                cant_pagos = len(pagos)
                if cant_pagos >= mes_actual:
                    meses_deuda = 0
                    estado_mora = "Al Día"
                    badge_class = "success"
                else:
                    meses_deuda = mes_actual - cant_pagos
                    estado_mora = f"Mora Leve ({meses_deuda} m.)" if meses_deuda <= 2 else f"Mora Crítica ({meses_deuda} m.)"
                    badge_class = "warning" if meses_deuda <= 2 else "danger"

        if meses_deuda > 0:
            monto_estimado = meses_deuda * valor_cuota
            total_deuda_acumulada += monto_estimado
            apellido_c = s.get("apellido") or ""
            nombre_c = s.get("nombre") or ""
            listado_deudores.append({
                "id": s["id"], "nro_socio": s["nro_socio"], "nombre_completo": f"{apellido_c}, {nombre_c}",
                "dni": s["dni"], "telefono": s["telefono"], "direccion": s["direccion"], "estado_socio": s["estado"],
                "ultima_fecha": s["ultima_fecha_cobro"], "meses_deuda": meses_deuda, "monto_estimado": monto_estimado,
                "estado_mora": estado_mora, "badge_class": badge_class
            })

    listado_deudores.sort(key=lambda x: x["meses_deuda"], reverse=True)
    return render_template(
        "morosidad.html", deudores=listado_deudores, total_deudores=len(listado_deudores),
        total_deuda=total_deuda_acumulada, valor_cuota=valor_cuota, hoy=hoy.strftime("%d/%m/%Y")
    )


@socios_bp.route("/socios/<int:id>/cambiar-estado", methods=["POST"])
@admin_required
def cambiar_estado_socio(id):
    nuevo_estado = request.form.get("estado", "Activo")
    if nuevo_estado not in ["Activo", "Baja", "Vitalicio"]:
        nuevo_estado = "Activo"

    try:
        db.session.execute(text("UPDATE socios SET estado = :estado WHERE id = :id;"), {"estado": nuevo_estado, "id": id})
        db.session.commit()
        flash(f"Estado del socio actualizado a '{nuevo_estado}'.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("No se pudo cambiar el estado del socio %s", id)
        flash("No se pudo cambiar el estado del socio. Inténtelo nuevamente.", "danger")

    return redirect(url_for("socios.ficha_socio", id=id))


@socios_bp.route("/socios/padron-imprimir")
@admin_required
def imprimir_padron():
    sql_socios = """
        SELECT id, COALESCE(nro_socio, id) AS nro_socio, apellido, nombre, dni, telefono, direccion, fecha_ingreso, COALESCE(estado, 'Activo') AS estado
        FROM socios ORDER BY apellido ASC, nombre ASC;
    """
    socios = db.session.execute(text(sql_socios)).mappings().all()
    return render_template(
        "padron_imprimir.html", socios=socios, total_socios=len(socios),
        total_activos=sum(1 for s in socios if (s.get("estado") or "").lower() == "activo"),
        total_vitalicios=sum(1 for s in socios if (s.get("estado") or "").lower() == "vitalicio"),
        total_bajas=sum(1 for s in socios if (s.get("estado") or "").lower() == "baja"),
        fecha_emision=datetime.now().strftime("%d/%m/%Y %H:%M")
    )


@socios_bp.route("/cuotas")
@admin_required
def listar_cuotas():
    sql = text("""
        SELECT c.id, c.nro_recibo, c.fecha_cobro, c.periodo, c.anio, c.monto, c.metodo_pago, c.estado, c.observaciones,
               s.nro_socio, s.apellido AS socio_apellido, s.nombre AS socio_nombre, s.dni AS socio_dni,
               cob.nombre AS cobrador_nombre, cob.apellido AS cobrador_apellido
        FROM cobro_cuotas c
        INNER JOIN socios s ON c.socio_id = s.id
        LEFT JOIN cobradores cob ON c.cobrador_id = cob.id
        ORDER BY c.fecha_cobro DESC, c.id DESC;
    """)
    resultados = db.session.execute(sql).fetchall()
    return render_template("listar_cuotas.html", cuotas=resultados)



@socios_bp.route("/matriz-cuotas")
@admin_required
def matriz_cuotas():
    anio_param = request.args.get("anio", "")
    anio = int(anio_param) if anio_param.isdigit() else date.today().year
    busqueda = request.args.get("q", "").strip()
    matriz, total_socios_activos = _obtener_matriz_cuotas(anio, busqueda)

    return render_template(
        "matriz_cuotas.html",
        matriz=matriz,
        anio=anio,
        busqueda=busqueda,
        total_socios_activos=total_socios_activos,
    )


@socios_bp.route("/matriz-cuotas/descargar-pdf")
@admin_required
def descargar_matriz_cuotas_pdf():
    anio_param = request.args.get("anio", "")
    anio = int(anio_param) if anio_param.isdigit() else date.today().year
    busqueda = request.args.get("q", "").strip()
    matriz, _ = _obtener_matriz_cuotas(anio, busqueda)
    archivo = io.BytesIO(_generar_pdf_matriz(matriz, anio))
    return send_file(
        archivo,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"matriz_cuotas_{anio}.pdf",
    )


@socios_bp.route("/cobrador")
@login_required
def inicio_cobrador():
    if session.get("user", {}).get("role") != "cobrador":
        return redirect(url_for("socios.listar_socios"))

    busqueda = request.args.get("q", "").strip()
    socios = db.session.execute(text("""
        SELECT id, nro_socio, apellido, nombre
        FROM socios
        WHERE LOWER(COALESCE(estado, 'Activo')) = 'activo'
          AND (
              :busqueda = ''
              OR apellido ILIKE :patron
              OR nombre ILIKE :patron
              OR CAST(nro_socio AS TEXT) = :busqueda
          )
        ORDER BY apellido, nombre
        LIMIT 100;
    """), {
        "busqueda": busqueda,
        "patron": f"%{busqueda}%",
    }).mappings().all()
    return render_template("cobrador_inicio.html", socios=socios, busqueda=busqueda)


@socios_bp.route("/cobrador/movimiento", methods=["GET", "POST"])
@login_required
def movimiento_cobrador():
    if session.get("user", {}).get("role") != "cobrador":
        return redirect(url_for("socios.listar_socios"))

    if request.method == "POST":
        try:
            tipo_movimiento = request.form.get("tipo_movimiento", "")
            if tipo_movimiento not in {"compra", "subsidio"}:
                raise ValueError("Seleccioná compra o subsidio.")
            monto = Decimal(request.form.get("monto") or "0").quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if monto <= 0:
                raise ValueError("El monto debe ser mayor que cero.")
            fecha = datetime.strptime(
                request.form.get("fecha") or str(date.today()), "%Y-%m-%d"
            ).date()
            concepto = request.form.get("concepto", "").strip()
            if not concepto or len(concepto) > 300:
                raise ValueError("Indicá un detalle de hasta 300 caracteres.")
            metodo = request.form.get("metodo", "Efectivo")
            if metodo not in {"Efectivo", "Transferencia", "Débito / Cheque"}:
                raise ValueError("Seleccioná un medio de pago válido.")

            es_subsidio = tipo_movimiento == "subsidio"
            db.session.execute(text("""
                INSERT INTO movimientos_caja (
                    fecha, tipo, categoria, concepto, monto, comprobante, interviene,
                    metodo, observaciones
                )
                VALUES (
                    :fecha, :tipo, :categoria, :concepto, :monto, :comprobante,
                    :interviene, :metodo, :observaciones
                );
            """), {
                "fecha": fecha,
                "tipo": "Ingreso" if es_subsidio else "Egreso",
                "categoria": "Subsidios Oficiales" if es_subsidio else "Compras",
                "concepto": concepto,
                "monto": monto,
                "comprobante": request.form.get("comprobante", "").strip() or None,
                "interviene": session["user"]["nombre"],
                "metodo": metodo,
                "observaciones": request.form.get("observaciones", "").strip() or None,
            })
            db.session.commit()
            flash(
                "Subsidio registrado en caja." if es_subsidio else "Compra registrada en caja.",
                "success",
            )
            return redirect(url_for("socios.inicio_cobrador"))
        except (InvalidOperation, TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "warning")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("No se pudo registrar un movimiento de cobrador")
            flash("No se pudo registrar el movimiento. Verificá los datos e intentá nuevamente.", "danger")

    return render_template(
        "movimiento_cobrador.html",
        hoy=date.today().isoformat(),
        datos=request.form,
    )


@socios_bp.route("/registrar-cuota/<int:socio_id>", methods=["GET", "POST"])
@login_required
def registrar_cuota(socio_id):
    es_cobrador = session.get("user", {}).get("role") == "cobrador"
    consulta_socio = """
        SELECT id, nro_socio, apellido, nombre, dni
        FROM socios
        WHERE id = :id
    """
    if es_cobrador:
        consulta_socio += " AND LOWER(COALESCE(estado, 'Activo')) = 'activo'"
    socio = db.session.execute(
        text(consulta_socio + ";"), {"id": socio_id}
    ).mappings().first()
    if not socio:
        flash("Socio no encontrado.", "warning")
        destino = "socios.inicio_cobrador" if es_cobrador else "socios.matriz_cuotas"
        return redirect(url_for(destino))

    if request.method == "POST":
        try:
            monto_total = Decimal(request.form.get("monto") or "0").quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if monto_total <= 0:
                raise ValueError("El monto debe ser mayor que cero.")
            fecha_cobro = request.form.get("fecha_cobro") or str(date.today())
            fecha = datetime.strptime(fecha_cobro, "%Y-%m-%d").date()
            periodo = request.form.get("periodo", "").strip()
            tipo_concepto = request.form.get("tipo_concepto", "cuota_mensual")
            if tipo_concepto not in {
                "cuota_mensual", "cuota_semestral", "cuota_anual",
                "cuota_personalizada", "inscripcion", "otro",
            }:
                raise ValueError("Seleccione una modalidad de pago válida.")
            metodo_pago = request.form.get("metodo_pago", "Efectivo")
            if metodo_pago not in {"Efectivo", "Transferencia"}:
                raise ValueError("Seleccione un método de pago válido.")
            cobrador_id = (
                session.get("cobrador_id")
                if es_cobrador else request.form.get("cobrador_id") or None
            )
            nro_recibo = request.form.get("nro_recibo", "").strip() or None
            cantidad_meses = {
                "cuota_mensual": 1,
                "cuota_semestral": 6,
                "cuota_anual": 12,
            }.get(tipo_concepto)
            if tipo_concepto == "cuota_personalizada":
                try:
                    cantidad_meses = int(request.form.get("cantidad_meses") or 0)
                except ValueError:
                    raise ValueError("Indique una cantidad de meses válida.")
                if not 1 <= cantidad_meses <= 12:
                    raise ValueError("La cantidad de meses debe estar entre 1 y 12.")

            if cantidad_meses:
                try:
                    mes_inicio = datetime.strptime(
                        request.form.get("mes_inicio", ""), "%Y-%m"
                    ).date().replace(day=1)
                except ValueError:
                    raise ValueError("Seleccione el primer mes que cubrirá el pago.")
                periodos = []
                for desplazamiento in range(cantidad_meses):
                    indice_mes = mes_inicio.month - 1 + desplazamiento
                    anio_periodo = mes_inicio.year + indice_mes // 12
                    mes_periodo = indice_mes % 12 + 1
                    periodos.append((anio_periodo, mes_periodo))

                cobros_existentes = db.session.execute(text("""
                    SELECT mes, periodo, anio, fecha_cobro, tipo_concepto
                    FROM cobro_cuotas
                    WHERE socio_id = :socio_id
                      AND (LOWER(estado) = 'pagado' OR estado IS NULL);
                """), {"socio_id": socio_id}).mappings().all()
                meses_ya_pagados = set()
                for cobro_existente in cobros_existentes:
                    meses_ya_pagados.update(_periodos_cubiertos(cobro_existente))
                repetidos = [p for p in periodos if p in meses_ya_pagados]
                if repetidos:
                    primer_anio, primer_mes = repetidos[0]
                    raise ValueError(
                        f"El período {NOMBRES_MESES[primer_mes - 1]} {primer_anio} "
                        "ya figura pagado. Revise los meses seleccionados."
                    )

                importe_por_mes = (monto_total / cantidad_meses).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                importes = [importe_por_mes] * (cantidad_meses - 1)
                importes.append(monto_total - sum(importes, Decimal("0.00")))
                asignaciones = [
                    {
                        "periodo": f"{NOMBRES_MESES[mes_periodo - 1]} {anio_periodo}",
                        "mes": mes_periodo,
                        "anio": anio_periodo,
                        "monto": importe,
                    }
                    for (anio_periodo, mes_periodo), importe in zip(periodos, importes)
                ]
            else:
                if tipo_concepto == "inscripcion":
                    periodo = f"Inscripción {fecha.year}"
                if not periodo:
                    raise ValueError("Debe indicar el período que se está cobrando.")
                asignaciones = [{
                    "periodo": periodo,
                    "mes": None,
                    "anio": fecha.year,
                    "monto": monto_total,
                }]

            if len(asignaciones) > 1 and not nro_recibo:
                nro_recibo = f"AUTO-{uuid4().hex[:8].upper()}"
            cobrador_id = int(cobrador_id) if cobrador_id else None

            cobrador = db.session.execute(
                text("SELECT nombre, apellido FROM cobradores WHERE id = :id"),
                {"id": cobrador_id},
            ).mappings().first() if cobrador_id else None
            nombre_cobrador = (
                f"{cobrador['nombre']} {cobrador['apellido'] or ''}".strip()
                if cobrador else "Sede Central"
            )
            categoria = "Inscripción" if tipo_concepto == "inscripcion" else "Cuota Social"
            observaciones = request.form.get("observaciones", "").strip()
            primer_cuota_id = None
            for asignacion in asignaciones:
                result = db.session.execute(text("""
                    INSERT INTO cobro_cuotas (
                        nro_recibo, fecha_cobro, socio_id, periodo, mes, anio, monto,
                        metodo_pago, cobrador_id, estado, observaciones, tipo_concepto
                    )
                    VALUES (
                        :recibo, :fecha, :socio_id, :periodo, :mes, :anio, :monto,
                        :metodo, :cobrador_id, 'PAGADO', :observaciones, :tipo_concepto
                    )
                    RETURNING id;
                """), {
                    "recibo": nro_recibo,
                    "fecha": fecha,
                    "socio_id": socio_id,
                    "periodo": asignacion["periodo"],
                    "mes": asignacion["mes"],
                    "anio": asignacion["anio"],
                    "monto": asignacion["monto"],
                    "metodo": metodo_pago,
                    "cobrador_id": cobrador_id,
                    "observaciones": observaciones,
                    "tipo_concepto": tipo_concepto,
                })
                cuota_id = result.scalar_one()
                if primer_cuota_id is None:
                    primer_cuota_id = cuota_id
                db.session.execute(text("""
                    INSERT INTO movimientos_caja (
                        fecha, tipo, categoria, concepto, monto, comprobante, interviene,
                        metodo, cuota_id, observaciones
                    )
                    VALUES (
                        :fecha, 'Ingreso', :categoria, :concepto, :monto, :comprobante,
                        :interviene, :metodo, :cuota_id, :observaciones
                    );
                """), {
                    "fecha": fecha,
                    "categoria": categoria,
                    "concepto": f"Cobro {asignacion['periodo']} - Socio: {socio['apellido']}, {socio['nombre']}",
                    "monto": asignacion["monto"],
                    "comprobante": nro_recibo,
                    "interviene": nombre_cobrador,
                    "metodo": metodo_pago,
                    "cuota_id": cuota_id,
                    "observaciones": observaciones,
                })
            db.session.commit()
            flash(
                f"¡Cobro de ${monto_total:,.2f} registrado y distribuido en "
                f"{len(asignaciones)} período(s)!", "success"
            )
            if es_cobrador:
                return redirect(url_for("socios.imprimir_recibo", cuota_id=primer_cuota_id))
            if request.form.get("volver_matriz") == "1":
                return redirect(url_for(
                    "socios.matriz_cuotas",
                    anio=request.form.get("anio_matriz") or asignaciones[0]["anio"],
                ))
            return redirect(url_for("socios.ficha_socio", id=socio_id))
        except (InvalidOperation, TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "warning")
        except Exception as error:
            db.session.rollback()
            current_app.logger.exception("No se pudo registrar el cobro del socio %s", socio_id)
            flash("No se pudo registrar el cobro. Verifique los datos e inténtelo nuevamente.", "danger")

    cobradores = db.session.execute(text("""
        SELECT id, nombre, apellido
        FROM cobradores
        WHERE password IS NOT NULL
        ORDER BY nombre, apellido;
    """)).mappings().all()
    requested_anio = request.args.get("anio", str(date.today().year))
    requested_mes = request.args.get("mes", str(date.today().month))
    try:
        mes = int(requested_mes)
        anio = int(requested_anio)
        if not 1 <= mes <= 12:
            raise ValueError
        mes_inicio = date(anio, mes, 1).strftime("%Y-%m")
    except ValueError:
        mes_inicio = date.today().replace(day=1).strftime("%Y-%m")
    periodo_inicial = request.args.get(
        "periodo", f"{NOMBRES_MESES[int(mes_inicio[5:7]) - 1]} {mes_inicio[:4]}"
    )
    return render_template(
        "registrar_cuota.html",
        socios=[socio],
        cobradores=cobradores,
        socio_id=socio_id,
        hoy=request.form.get("fecha_cobro") or date.today().isoformat(),
        mes_inicio=request.form.get("mes_inicio") or mes_inicio,
        socio_id_inicial=socio_id,
        periodo_inicial=request.form.get("periodo") or periodo_inicial,
        tipo_concepto_inicial=request.form.get(
            "tipo_concepto", request.args.get("tipo_concepto", "cuota_mensual")
        ),
        cantidad_meses_inicial=request.form.get("cantidad_meses", "1"),
        monto_inicial=request.form.get("monto", ""),
        volver_matriz=request.args.get("volver_matriz") == "1",
        anio_matriz=request.args.get("anio", mes_inicio[:4]),
        es_cobrador=es_cobrador,
    )


@socios_bp.route("/imprimir-recibo/<int:cuota_id>")
@login_required
def imprimir_recibo(cuota_id):
    cuota = db.session.execute(text("SELECT * FROM cobro_cuotas WHERE id = :id;"), {"id": cuota_id}).mappings().first()
    if not cuota:
        flash("Recibo no encontrado.", "warning")
        destino = "socios.inicio_cobrador" if session.get("user", {}).get("role") == "cobrador" else "socios.listar_cuotas"
        return redirect(url_for(destino))
    if (
        session.get("user", {}).get("role") == "cobrador"
        and cuota["cobrador_id"] != session.get("cobrador_id")
    ):
        abort(403)
    cuotas_del_cobro = _cuotas_del_mismo_cobro(cuota)
    if len(cuotas_del_cobro) > 1:
        cuota = dict(cuota)
        cuota["monto"] = sum(
            (Decimal(str(item["monto"] or 0)) for item in cuotas_del_cobro),
            Decimal("0.00"),
        )
        cuota["periodo"] = " / ".join(item["periodo"] or "Cuota" for item in cuotas_del_cobro)
    return render_template("recibo_imprimir.html", cuota=cuota)


@socios_bp.route("/cuotas/editar/<int:cuota_id>", methods=["GET", "POST"])
@admin_required
def editar_cuota(cuota_id):
    cuota_resultado = db.session.execute(
        text("SELECT * FROM cobro_cuotas WHERE id = :id;"),
        {"id": cuota_id},
    ).mappings().first()
    if not cuota_resultado:
        flash("La cuota que desea editar no fue encontrada.", "warning")
        return redirect(url_for("socios.listar_cuotas"))
    cuotas_del_cobro = _cuotas_del_mismo_cobro(cuota_resultado)
    cuota = dict(cuota_resultado)
    if len(cuotas_del_cobro) > 1:
        cuota["monto"] = sum(
            (Decimal(str(item["monto"] or 0)) for item in cuotas_del_cobro),
            Decimal("0.00"),
        )
        cuota["periodo"] = " / ".join(item["periodo"] or "Cuota" for item in cuotas_del_cobro)
        cuota["cantidad_periodos"] = len(cuotas_del_cobro)

    if request.method == "POST":
        try:
            monto_total = Decimal(request.form.get("monto") or "0").quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if monto_total <= 0:
                raise ValueError("El monto debe ser mayor que cero.")
            metodo_pago = request.form.get("metodo_pago") or "Efectivo"
            if metodo_pago not in {"Efectivo", "Transferencia"}:
                raise ValueError("Seleccione un método de pago válido.")
            estado = request.form.get("estado", "PAGADO").upper()
            if estado not in {"PAGADO", "PENDIENTE", "ANULADO"}:
                raise ValueError("Seleccione un estado válido para la cuota.")

            cantidad = len(cuotas_del_cobro)
            importe = (monto_total / cantidad).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            importes = [importe] * (cantidad - 1)
            importes.append(monto_total - sum(importes, Decimal("0.00")))
            for item, importe_periodo in zip(cuotas_del_cobro, importes):
                db.session.execute(text("""
                    UPDATE cobro_cuotas
                    SET monto = :monto, estado = :estado, metodo_pago = :metodo_pago
                    WHERE id = :id;
                """), {
                    "monto": importe_periodo,
                    "estado": estado,
                    "metodo_pago": metodo_pago,
                    "id": item["id"],
                })
                db.session.execute(text("""
                    UPDATE movimientos_caja
                    SET monto = :monto, metodo = :metodo
                    WHERE cuota_id = :cuota_id;
                """), {
                    "monto": importe_periodo,
                    "metodo": metodo_pago,
                    "cuota_id": item["id"],
                })
            db.session.commit()
            flash("Cuota actualizada correctamente.", "success")
            return redirect(url_for("socios.listar_cuotas"))
        except (InvalidOperation, TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "warning")
            cuota["monto"] = request.form.get("monto", cuota["monto"])
        except Exception:
            db.session.rollback()
            current_app.logger.exception("No se pudo actualizar la cuota %s", cuota_id)
            flash("No se pudo actualizar la cuota. Verifique los datos e inténtelo nuevamente.", "danger")

    cobradores = db.session.execute(text("""
        SELECT id, nombre, apellido
        FROM cobradores
        WHERE password IS NOT NULL
        ORDER BY nombre, apellido;
    """)).mappings().all()
    return render_template("editar_cuota.html", cuota=cuota, cobradores=cobradores)


@socios_bp.route("/caja", methods=["GET"])
@admin_required
def listar_caja():
    anio_param = request.args.get("anio", "")
    mes_param = request.args.get("mes", "")
    params = {}
    filtro_cuotas = ""
    filtro_caja = ""
    if anio_param:
        if not anio_param.isdigit():
            flash("El año seleccionado no es válido.", "warning")
            return redirect(url_for("socios.listar_caja"))
        params["anio"] = int(anio_param)
        filtro_cuotas += " AND EXTRACT(YEAR FROM fecha_cobro) = :anio"
        filtro_caja += " AND EXTRACT(YEAR FROM fecha) = :anio"
    if mes_param:
        if not mes_param.isdigit() or not 1 <= int(mes_param) <= 12 or not anio_param:
            flash("Seleccione un mes válido junto con un año.", "warning")
            return redirect(url_for("socios.listar_caja", anio=anio_param or None))
        params["mes"] = int(mes_param)
        filtro_cuotas += " AND EXTRACT(MONTH FROM fecha_cobro) = :mes"
        filtro_caja += " AND EXTRACT(MONTH FROM fecha) = :mes"

    meses_nombre = (
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    )
    etiqueta_periodo = (
        f"{meses_nombre[int(mes_param) - 1]} {anio_param}" if mes_param
        else f"Año {anio_param}" if anio_param
        else "Histórico Acumulado"
    )
    total_socios = float(db.session.execute(text(f"""
        SELECT COALESCE(SUM(monto), 0)
        FROM cobro_cuotas
        WHERE (LOWER(estado) = 'pagado' OR estado IS NULL){filtro_cuotas};
    """), params).scalar() or 0)
    otros_ingresos_items = db.session.execute(text(f"""
        SELECT id, fecha, categoria, concepto, comprobante, interviene, metodo,
               monto AS total_concepto
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'ingreso' AND cuota_id IS NULL{filtro_caja}
        ORDER BY fecha DESC, id DESC;
    """), params).mappings().all()
    egresos_items = db.session.execute(text(f"""
        SELECT id, fecha, categoria, concepto, comprobante, interviene, metodo,
               monto AS total_concepto
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'egreso'{filtro_caja}
        ORDER BY fecha DESC, id DESC;
    """), params).mappings().all()
    total_otros_ingresos = sum(float(item["total_concepto"] or 0) for item in otros_ingresos_items)
    total_egresos = sum(float(item["total_concepto"] or 0) for item in egresos_items)
    total_ingresos = total_socios + total_otros_ingresos
    return render_template(
        "listar_caja.html",
        etiqueta_periodo=etiqueta_periodo,
        anio_param=anio_param,
        anio_actual=date.today().year,
        mes_param=mes_param,
        total_socios=total_socios,
        otros_ingresos_items=otros_ingresos_items,
        total_otros_ingresos=total_otros_ingresos,
        total_ingresos=total_ingresos,
        egresos_items=egresos_items,
        total_egresos=total_egresos,
        saldo_actual=total_ingresos - total_egresos,
    )


@socios_bp.route("/caja/nuevo", methods=["GET", "POST"])
@admin_required
def nuevo_movimiento_caja():
    if request.method == "POST":
        tipo = request.form.get("tipo", "").strip().capitalize()
        try:
            monto = float(request.form.get("monto") or 0)
            if tipo not in {"Ingreso", "Egreso"} or monto <= 0:
                raise ValueError("Indique si es ingreso o egreso y un monto mayor que cero.")
            fecha = datetime.strptime(request.form.get("fecha") or str(date.today()), "%Y-%m-%d").date()
            db.session.execute(text("""
                INSERT INTO movimientos_caja (
                    fecha, tipo, categoria, concepto, monto, comprobante, interviene,
                    metodo, observaciones
                )
                VALUES (
                    :fecha, :tipo, :categoria, :concepto, :monto, :comprobante, :interviene,
                    :metodo, :observaciones
                );
            """), {
                "fecha": fecha,
                "tipo": tipo,
                "categoria": request.form.get("categoria", "").strip(),
                "concepto": request.form.get("concepto", "").strip(),
                "monto": monto,
                "comprobante": request.form.get("comprobante", "").strip() or None,
                "interviene": request.form.get("interviene", "").strip() or None,
                "metodo": request.form.get("metodo", "Efectivo"),
                "observaciones": request.form.get("observaciones", "").strip() or None,
            })
            db.session.commit()
            flash("Movimiento asentado en caja correctamente.", "success")
            return redirect(url_for("socios.listar_caja", anio=fecha.year))
        except (TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "warning")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("No se pudo registrar el movimiento de caja")
            flash("No se pudo registrar el movimiento. Verifique los datos e inténtelo nuevamente.", "danger")
    return render_template("nuevo_movimiento.html", socios=[])


@socios_bp.route("/caja/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_movimiento_caja(id):
    if request.method == "POST":
        try:
            monto = float(request.form.get("monto") or 0)
            if monto <= 0:
                raise ValueError("El monto debe ser mayor que cero.")
            fecha = datetime.strptime(request.form.get("fecha") or str(date.today()), "%Y-%m-%d").date()
            db.session.execute(text("""
                UPDATE movimientos_caja
                SET fecha = :fecha, tipo = :tipo, categoria = :categoria, concepto = :concepto,
                    monto = :monto, comprobante = :comprobante, interviene = :interviene,
                    metodo = :metodo, observaciones = :observaciones
                WHERE id = :id AND cuota_id IS NULL;
            """), {
                "fecha": fecha,
                "tipo": request.form.get("tipo", "Egreso"),
                "categoria": request.form.get("categoria", "").strip(),
                "concepto": request.form.get("concepto", "").strip(),
                "monto": monto,
                "comprobante": request.form.get("comprobante", "").strip() or None,
                "interviene": request.form.get("interviene", "").strip() or None,
                "metodo": request.form.get("metodo", "Efectivo"),
                "observaciones": request.form.get("observaciones", "").strip() or None,
                "id": id,
            })
            db.session.commit()
            flash("Movimiento actualizado.", "success")
            return redirect(url_for("socios.listar_caja", anio=fecha.year))
        except (TypeError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "warning")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("No se pudo actualizar el movimiento de caja %s", id)
            flash("No se pudo actualizar el movimiento. Verifique los datos e inténtelo nuevamente.", "danger")
    mov = db.session.execute(text("""
        SELECT * FROM movimientos_caja WHERE id = :id AND cuota_id IS NULL;
    """), {"id": id}).mappings().first()
    if not mov:
        flash("Movimiento no encontrado o corresponde a un cobro protegido.", "warning")
        return redirect(url_for("socios.listar_caja"))
    return render_template("editar_movimiento.html", m=mov)


@socios_bp.route("/caja/exportar_excel", methods=["GET"])
@admin_required
def caja_exportar_excel():
    from openpyxl import Workbook

    anio_param = request.args.get("anio", "")
    mes_param = request.args.get("mes", "")
    params = {}
    filtro_cuotas = ""
    filtro_caja = ""
    if anio_param:
        if not anio_param.isdigit():
            flash("El año seleccionado no es válido.", "warning")
            return redirect(url_for("socios.listar_caja"))
        params["anio"] = int(anio_param)
        filtro_cuotas += " AND EXTRACT(YEAR FROM c.fecha_cobro) = :anio"
        filtro_caja += " AND EXTRACT(YEAR FROM m.fecha) = :anio"
    if mes_param:
        if not mes_param.isdigit() or not 1 <= int(mes_param) <= 12 or not anio_param:
            flash("Seleccione un mes válido junto con un año.", "warning")
            return redirect(url_for("socios.listar_caja", anio=anio_param or None))
        params["mes"] = int(mes_param)
        filtro_cuotas += " AND EXTRACT(MONTH FROM c.fecha_cobro) = :mes"
        filtro_caja += " AND EXTRACT(MONTH FROM m.fecha) = :mes"

    wb = Workbook()
    ws = wb.active
    ws.title = "Caja"
    ws.append(["Fecha", "Tipo", "Categoría", "Concepto", "Comprobante", "Medio", "Monto", "Socio"])
    movimientos = db.session.execute(text("""
        SELECT c.fecha_cobro AS fecha, 'Ingreso' AS tipo, 'Cuota social' AS categoria,
               'Cobro ' || COALESCE(c.periodo, 'Cuota') || ' - ' || s.apellido || ', ' || s.nombre AS concepto,
               c.nro_recibo AS comprobante, COALESCE(c.metodo_pago, 'Efectivo') AS metodo,
               c.monto, s.apellido || ', ' || s.nombre AS socio
        FROM cobro_cuotas c
        INNER JOIN socios s ON c.socio_id = s.id
        WHERE (LOWER(c.estado) = 'pagado' OR c.estado IS NULL)""" + filtro_cuotas + """
        UNION ALL
        SELECT m.fecha, m.tipo, m.categoria, m.concepto, m.comprobante, m.metodo,
               m.monto, NULL AS socio
        FROM movimientos_caja m
        WHERE m.cuota_id IS NULL""" + filtro_caja + """
        ORDER BY fecha DESC;
    """), params).mappings().all()
    for m in movimientos:
        ws.append([
            str(m["fecha"])[:10] if m["fecha"] else "",
            m["tipo"], m["categoria"], m["concepto"], m["comprobante"],
            m["metodo"], float(m["monto"] or 0), m["socio"],
        ])
    archivo = io.BytesIO()
    wb.save(archivo)
    archivo.seek(0)
    nombre = f"caja_{anio_param or 'historico'}"
    if mes_param:
        nombre += f"_{mes_param.zfill(2)}"
    return send_file(
        archivo,
        as_attachment=True,
        download_name=f"{nombre}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@socios_bp.route("/caja/balance", methods=["GET"])
@admin_required
def balance_periodic():
    try:
        fecha_desde = datetime.strptime(
            request.args.get("fecha_desde", f"{date.today().year}-{date.today().month:02d}-01"),
            "%Y-%m-%d",
        ).date()
        fecha_hasta = datetime.strptime(
            request.args.get("fecha_hasta", str(date.today())),
            "%Y-%m-%d",
        ).date()
        if fecha_desde > fecha_hasta:
            raise ValueError("La fecha inicial debe ser anterior a la fecha final.")
    except ValueError as error:
        flash(str(error) or "Ingrese un rango de fechas válido.", "warning")
        fecha_desde = date.today().replace(day=1)
        fecha_hasta = date.today()

    params = {"desde": fecha_desde, "hasta": fecha_hasta}
    cuotas = db.session.execute(text("""
        SELECT c.socio_id, s.nro_socio, s.apellido, s.nombre, s.dni,
               COUNT(c.id) AS cantidad_cuotas,
               STRING_AGG(DISTINCT c.periodo, ', ' ORDER BY c.periodo) AS periodos_pagados,
               MAX(c.fecha_cobro) AS ultima_fecha_pago, SUM(c.monto) AS total_pagado
        FROM cobro_cuotas c
        INNER JOIN socios s ON s.id = c.socio_id
        WHERE c.fecha_cobro >= :desde AND c.fecha_cobro < :hasta + INTERVAL '1 day'
          AND (LOWER(c.estado) = 'pagado' OR c.estado IS NULL)
        GROUP BY c.socio_id, s.nro_socio, s.apellido, s.nombre, s.dni
        ORDER BY s.apellido, s.nombre;
    """), params).mappings().all()
    movimientos = db.session.execute(text("""
        SELECT fecha, tipo, concepto, comprobante, monto, observaciones
        FROM (
            SELECT c.fecha_cobro AS fecha, 'Ingreso' AS tipo,
                   'Cuotas sociales - ' || s.apellido || ', ' || s.nombre AS concepto,
                   c.nro_recibo AS comprobante, c.monto, c.observaciones
            FROM cobro_cuotas c
            INNER JOIN socios s ON s.id = c.socio_id
            WHERE c.fecha_cobro >= :desde AND c.fecha_cobro < :hasta + INTERVAL '1 day'
              AND (LOWER(c.estado) = 'pagado' OR c.estado IS NULL)
            UNION ALL
            SELECT m.fecha, m.tipo, m.concepto, m.comprobante, m.monto, m.observaciones
            FROM movimientos_caja m
            WHERE m.cuota_id IS NULL
              AND m.fecha >= :desde AND m.fecha < :hasta + INTERVAL '1 day'
        ) AS libro
        ORDER BY fecha DESC;
    """), params).mappings().all()
    ingresos_cat = db.session.execute(text("""
        SELECT concepto, SUM(cantidad)::int AS cantidad, SUM(total) AS total
        FROM (
            SELECT 'Cuotas sociales' AS concepto, COUNT(*) AS cantidad, COALESCE(SUM(monto), 0) AS total
            FROM cobro_cuotas
            WHERE fecha_cobro >= :desde AND fecha_cobro < :hasta + INTERVAL '1 day'
              AND (LOWER(estado) = 'pagado' OR estado IS NULL)
            UNION ALL
            SELECT categoria AS concepto, COUNT(*) AS cantidad, COALESCE(SUM(monto), 0) AS total
            FROM movimientos_caja
            WHERE LOWER(tipo) = 'ingreso' AND cuota_id IS NULL
              AND fecha >= :desde AND fecha < :hasta + INTERVAL '1 day'
            GROUP BY categoria
        ) AS ingresos
        GROUP BY concepto ORDER BY concepto;
    """), params).mappings().all()
    egresos_cat = db.session.execute(text("""
        SELECT categoria AS concepto, COUNT(*) AS cantidad, COALESCE(SUM(monto), 0) AS total
        FROM movimientos_caja
        WHERE LOWER(tipo) = 'egreso'
          AND fecha >= :desde AND fecha < :hasta + INTERVAL '1 day'
        GROUP BY categoria ORDER BY categoria;
    """), params).mappings().all()

    total_cuotas_monto = sum(float(socio["total_pagado"] or 0) for socio in cuotas)
    total_otros_ingresos = sum(
        float(item["total"] or 0) for item in ingresos_cat if item["concepto"] != "Cuotas sociales"
    )
    total_egresos = sum(float(item["total"] or 0) for item in egresos_cat)
    return render_template(
        "balance_periodico.html",
        fecha_desde=fecha_desde.isoformat(),
        fecha_hasta=fecha_hasta.isoformat(),
        anio=fecha_desde.year,
        mes=fecha_desde.month,
        cantidad_cuotas=sum(int(socio["cantidad_cuotas"]) for socio in cuotas),
        total_cuotas_monto=total_cuotas_monto,
        total_ingresos=total_cuotas_monto + total_otros_ingresos,
        total_egresos=total_egresos,
        saldo_periodo=total_cuotas_monto + total_otros_ingresos - total_egresos,
        ingresos_cat=ingresos_cat,
        egresos_cat=egresos_cat,
        socios_cobros=cuotas,
        movimientos=movimientos,
    )


@socios_bp.route("/caja/balance/exportar_excel", methods=["GET"])
@admin_required
def exportar_balance_excel():
    from openpyxl import Workbook

    try:
        fecha_desde = datetime.strptime(request.args["fecha_desde"], "%Y-%m-%d").date()
        fecha_hasta = datetime.strptime(request.args["fecha_hasta"], "%Y-%m-%d").date()
        if fecha_desde > fecha_hasta:
            raise ValueError("La fecha inicial debe ser anterior a la fecha final.")
    except (KeyError, ValueError):
        flash("El rango de fechas para exportar no es válido.", "warning")
        return redirect(url_for("socios.balance_periodic"))

    wb = Workbook()
    ws = wb.active
    ws.title = "Balance"
    ws.append(["Fecha", "Tipo", "Concepto", "Comprobante", "Ingreso", "Egreso", "Observaciones"])
    movimientos = db.session.execute(text("""
        SELECT fecha, tipo, concepto, comprobante, monto, observaciones
        FROM (
            SELECT c.fecha_cobro AS fecha, 'Ingreso' AS tipo,
                   'Cuotas sociales - ' || s.apellido || ', ' || s.nombre AS concepto,
                   c.nro_recibo AS comprobante, c.monto, c.observaciones
            FROM cobro_cuotas c
            INNER JOIN socios s ON s.id = c.socio_id
            WHERE c.fecha_cobro >= :desde AND c.fecha_cobro < :hasta + INTERVAL '1 day'
              AND (LOWER(c.estado) = 'pagado' OR c.estado IS NULL)
            UNION ALL
            SELECT m.fecha, m.tipo, m.concepto, m.comprobante, m.monto, m.observaciones
            FROM movimientos_caja m
            WHERE m.cuota_id IS NULL
              AND m.fecha >= :desde AND m.fecha < :hasta + INTERVAL '1 day'
        ) AS libro
        ORDER BY fecha DESC;
    """), {"desde": fecha_desde, "hasta": fecha_hasta}).mappings().all()
    for movimiento in movimientos:
        ingreso = float(movimiento["monto"] or 0) if movimiento["tipo"].lower() == "ingreso" else None
        egreso = float(movimiento["monto"] or 0) if movimiento["tipo"].lower() == "egreso" else None
        ws.append([
            str(movimiento["fecha"])[:10] if movimiento["fecha"] else "",
            movimiento["tipo"],
            movimiento["concepto"],
            movimiento["comprobante"],
            ingreso,
            egreso,
            movimiento["observaciones"],
        ])
    archivo = io.BytesIO()
    wb.save(archivo)
    archivo.seek(0)
    return send_file(
        archivo,
        as_attachment=True,
        download_name=f"balance_{fecha_desde}_{fecha_hasta}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
