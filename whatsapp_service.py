import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_GRAPH_API_VERSION,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TEMPLATE_LANGUAGE,
)


def whatsapp_template_configured(template_name):
    return bool(
        WHATSAPP_ACCESS_TOKEN
        and WHATSAPP_PHONE_NUMBER_ID
        and template_name
    )


def send_whatsapp_template(telefono, template_name, parameters):
    if not whatsapp_template_configured(template_name):
        raise ValueError("Falta configurar WhatsApp o la plantilla aprobada para este envío.")

    destinatario = re.sub(r"\D", "", telefono or "")
    if not destinatario.startswith("54") or not 11 <= len(destinatario) <= 15:
        raise ValueError("El teléfono debe incluir el código internacional argentino (+54).")

    datos = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": WHATSAPP_TEMPLATE_LANGUAGE},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(parameter)}
                    for parameter in parameters
                ],
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
        with urlopen(req, timeout=20) as respuesta:
            respuesta.read()
    except HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"WhatsApp rechazó el envío (HTTP {error.code}): {detalle[:500]}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"No se pudo conectar con WhatsApp: {error}") from error
