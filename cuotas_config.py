from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import text

from models import db


_CAMPOS_MONTO = (
    "valor_cuota_mensual",
    "valor_anual_promocional",
    "valor_anual_estandar",
    "valor_inscripcion",
)
_MONTO_MAXIMO = Decimal("9999999999.99")

_VALORES_POR_DEFECTO = {
    "valor_cuota_mensual": Decimal("200.00"),
    "valor_anual_promocional": Decimal("1500.00"),
    "valor_anual_estandar": Decimal("2000.00"),
    "valor_inscripcion": Decimal("2000.00"),
}


def _convertir_monto(valor, campo):
    try:
        monto = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"El valor de {campo.replace('_', ' ')} no es válido.")
    if not monto.is_finite() or monto < 0:
        raise ValueError(f"El valor de {campo.replace('_', ' ')} debe ser cero o mayor.")
    if monto > _MONTO_MAXIMO:
        raise ValueError(f"El valor de {campo.replace('_', ' ')} supera el máximo permitido.")
    return monto


def parsear_valores_cuota(formulario):
    valores = {}
    for campo in _CAMPOS_MONTO:
        valor = formulario.get(campo, "")
        if not str(valor).strip():
            raise ValueError(f"Complete el valor de {campo.replace('_', ' ')}.")
        valores[campo] = _convertir_monto(valor, campo)
    return valores


def _valores_iniciales(config):
    reglas = config.get("reglas_negocio", {})
    valores = {}
    equivalencias_anteriores = {
        "valor_cuota_mensual": "valor_cuota_estandar",
        "valor_anual_promocional": "valor_cuota_promocional",
    }
    for campo, defecto in _VALORES_POR_DEFECTO.items():
        valor = reglas.get(campo) or reglas.get(equivalencias_anteriores.get(campo)) or defecto
        valores[campo] = _convertir_monto(valor, campo)
    return valores


def inicializar_valores_cuota(config):
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS configuracion_cuotas (
            id SMALLINT PRIMARY KEY CHECK (id = 1),
            valor_cuota_mensual NUMERIC(12, 2) NOT NULL,
            valor_anual_promocional NUMERIC(12, 2) NOT NULL,
            valor_anual_estandar NUMERIC(12, 2) NOT NULL,
            valor_inscripcion NUMERIC(12, 2) NOT NULL,
            actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """))
    db.session.execute(text("""
        INSERT INTO configuracion_cuotas (
            id, valor_cuota_mensual, valor_anual_promocional,
            valor_anual_estandar, valor_inscripcion
        )
        VALUES (
            1, :valor_cuota_mensual, :valor_anual_promocional,
            :valor_anual_estandar, :valor_inscripcion
        )
        ON CONFLICT (id) DO NOTHING;
    """), _valores_iniciales(config))


def obtener_valores_cuota():
    valores = db.session.execute(text("""
        SELECT valor_cuota_mensual, valor_anual_promocional,
               valor_anual_estandar, valor_inscripcion
        FROM configuracion_cuotas
        WHERE id = 1;
    """)).mappings().one()
    return dict(valores)


def guardar_valores_cuota(valores):
    db.session.execute(text("""
        UPDATE configuracion_cuotas
        SET valor_cuota_mensual = :valor_cuota_mensual,
            valor_anual_promocional = :valor_anual_promocional,
            valor_anual_estandar = :valor_anual_estandar,
            valor_inscripcion = :valor_inscripcion,
            actualizado_en = NOW()
        WHERE id = 1;
    """), valores)
