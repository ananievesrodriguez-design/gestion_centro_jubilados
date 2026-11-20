CARGOS_COMISION = (
    "Presidente",
    "Secretaria",
    "Tesorera",
    "Vocal titular 1",
    "Vocal titular 2",
    "Vocal suplente 1",
    "Vocal suplente 2",
    "Revisor de cuentas titular",
    "Revisor de cuentas suplente",
)

CARGOS_COMISION_EXCLUSIVOS = frozenset(CARGOS_COMISION[:7])
ORDEN_CARGOS_COMISION = {
    cargo.casefold(): orden for orden, cargo in enumerate(CARGOS_COMISION)
}


def ordenar_integrantes_comision(integrantes):
    return sorted(
        integrantes,
        key=lambda integrante: (
            ORDEN_CARGOS_COMISION.get(
                str(integrante.get("cargo") or "").strip().casefold(),
                len(ORDEN_CARGOS_COMISION),
            ),
            str(integrante.get("apellido") or "").casefold(),
            str(integrante.get("nombre") or "").casefold(),
        ),
    )
