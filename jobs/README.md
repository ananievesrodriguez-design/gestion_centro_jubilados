# WhatsApp programado

El proceso `jobs.procesar_whatsapp` encola cumpleaños a las 9:00 (hora argentina) y procesa hasta 50 mensajes pendientes por ejecución. Configurá el programador del hosting para ejecutar cada 5 minutos:

```text
python -m jobs.procesar_whatsapp
```

Usá el intérprete Python del entorno virtual del despliegue. El proceso no envía mensajes si no encuentra las variables `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BIRTHDAY_TEMPLATE` y `WHATSAPP_NEWS_TEMPLATE`. `WHATSAPP_TEMPLATE_LANGUAGE` define el idioma de ambas plantillas y usa `es_AR` por defecto.

Las plantillas deben estar aprobadas en WhatsApp Business y tener parámetros de cuerpo en este orden:

- Cumpleaños: un parámetro, el nombre del socio.
- Novedad: dos parámetros, título y contenido (hasta 1.000 caracteres).

Solo se encola a socios activos o vitalicios que autorizaron recibir WhatsApp y cuyo teléfono tiene código internacional argentino (`+54`). Los envíos fallidos quedan visibles en la gestión de novedades; al pulsar nuevamente el envío se reintentan los fallidos, sin repetir los ya enviados.
