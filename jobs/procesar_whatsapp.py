from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import text

from app import app
from config import WHATSAPP_BIRTHDAY_TEMPLATE, WHATSAPP_NEWS_TEMPLATE
from models import db
from whatsapp_service import send_whatsapp_template, whatsapp_template_configured

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")
MAXIMO_POR_EJECUCION = 50


def encolar_cumpleanos(hoy):
    if hoy.hour < 9 or not whatsapp_template_configured(WHATSAPP_BIRTHDAY_TEMPLATE):
        return 0

    resultado = db.session.execute(text("""
        INSERT INTO whatsapp_envios (
            socio_id, tipo, referencia, telefono, parametro_1
        )
        SELECT id, 'cumpleanos', :referencia,
               regexp_replace(telefono, '[^0-9]', '', 'g'),
               COALESCE(NULLIF(BTRIM(nombre), ''), 'socio')
        FROM socios
        WHERE whatsapp_autorizado IS TRUE
          AND telefono IS NOT NULL
          AND LENGTH(regexp_replace(telefono, '[^0-9]', '', 'g')) BETWEEN 11 AND 15
          AND regexp_replace(telefono, '[^0-9]', '', 'g') LIKE '54%'
          AND LOWER(COALESCE(estado, 'activo')) IN ('activo', 'vitalicio')
          AND fecha_nacimiento IS NOT NULL
          AND EXTRACT(MONTH FROM fecha_nacimiento) = :mes
          AND EXTRACT(DAY FROM fecha_nacimiento) = :dia
        ON CONFLICT (socio_id, tipo, referencia) DO NOTHING;
    """), {
        "referencia": hoy.date().isoformat(),
        "mes": hoy.month,
        "dia": hoy.day,
    })
    db.session.commit()
    return resultado.rowcount


def procesar_pendientes():
    db.session.execute(text("""
        UPDATE whatsapp_envios
        SET estado = 'pendiente', actualizado_en = NOW()
        WHERE estado = 'procesando'
          AND actualizado_en < NOW() - INTERVAL '30 minutes';
    """))
    envios = db.session.execute(text("""
        SELECT id, socio_id, tipo, telefono, parametro_1, parametro_2
        FROM whatsapp_envios
        WHERE estado = 'pendiente'
        ORDER BY id
        LIMIT :limite
        FOR UPDATE SKIP LOCKED;
    """), {"limite": MAXIMO_POR_EJECUCION}).mappings().all()
    if not envios:
        db.session.commit()
        return 0

    ids = [envio["id"] for envio in envios]
    db.session.execute(text("""
        UPDATE whatsapp_envios
        SET estado = 'procesando', error = NULL, actualizado_en = NOW()
        WHERE id = ANY(:ids);
    """), {"ids": ids})
    db.session.commit()

    procesados = 0
    for envio in envios:
        socio = db.session.execute(text("""
            SELECT whatsapp_autorizado, telefono, LOWER(COALESCE(estado, 'activo')) AS estado
            FROM socios
            WHERE id = :id;
        """), {"id": envio["socio_id"]}).mappings().first()
        if (
            not socio
            or not socio["whatsapp_autorizado"]
            or socio["estado"] not in {"activo", "vitalicio"}
            or not socio["telefono"]
        ):
            db.session.execute(text("""
                UPDATE whatsapp_envios
                SET estado = 'fallido',
                    error = 'El socio retiró la autorización o sus datos ya no permiten el envío.',
                    actualizado_en = NOW()
                WHERE id = :id;
            """), {"id": envio["id"]})
            db.session.commit()
            procesados += 1
            continue

        plantilla = (
            WHATSAPP_BIRTHDAY_TEMPLATE
            if envio["tipo"] == "cumpleanos"
            else WHATSAPP_NEWS_TEMPLATE
        )
        parametros = [envio["parametro_1"]]
        if envio["parametro_2"] is not None:
            parametros.append(envio["parametro_2"])
        try:
            send_whatsapp_template(socio["telefono"], plantilla, parametros)
            estado = "enviado"
            detalle = None
        except Exception as error:
            estado = "fallido"
            detalle = str(error)[:1000]
            current_app.logger.exception(
                "Falló el envío de WhatsApp con id %s", envio["id"]
            )
        db.session.execute(text("""
            UPDATE whatsapp_envios
            SET estado = :estado, telefono = :telefono, error = :error, actualizado_en = NOW()
            WHERE id = :id;
        """), {
            "id": envio["id"],
            "estado": estado,
            "telefono": socio["telefono"],
            "error": detalle,
        })
        db.session.commit()
        procesados += 1
    return procesados


def ejecutar():
    with app.app_context():
        ahora = datetime.now(ZONA_HORARIA)
        encolados = encolar_cumpleanos(ahora)
        procesados = procesar_pendientes()
        current_app.logger.info(
            "Proceso WhatsApp finalizado: %s cumpleaños en cola, %s mensajes procesados.",
            encolados,
            procesados,
        )


if __name__ == "__main__":
    ejecutar()
