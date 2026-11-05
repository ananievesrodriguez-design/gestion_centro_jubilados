# Gestión del Centro de Jubilados

Aplicación web para administrar socios, cuotas, caja, cobradores y el portal público del Centro. Está hecha con Flask, PostgreSQL/Supabase y plantillas Jinja.

## Requisitos

- Python 3.12 (versión fijada en `.python-version`).
- Una base PostgreSQL con el esquema institucional existente.
- Un proyecto Supabase y las variables de entorno indicadas abajo.

Instalación local en Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completá `.env` con valores reales antes de iniciar la app. No subas ese archivo al repositorio.

```powershell
python app.py
```

La aplicación prepara al iniciar algunas columnas e índices de `cobradores`, la autorización de WhatsApp en `socios`, la cola de mensajes y las tablas auxiliares del portal. El resto del esquema de socios, cuotas y caja debe existir previamente en PostgreSQL.

## Variables de entorno

Obligatorias para la aplicación:

| Variable | Descripción |
|---|---|
| `SUPABASE_URL` | URL del proyecto Supabase. |
| `SUPABASE_ANON_KEY` | Clave pública del proyecto Supabase. |
| `SECRET_KEY` | Secreto largo y aleatorio para firmar las sesiones Flask. Debe ser el mismo en el servidor web y el cron job. |
| `DATABASE_URL` | URL de conexión PostgreSQL usada por SQLAlchemy. |

Opcionales:

| Variable | Descripción |
|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | Clave administrativa para funciones de Supabase que la requieran. Nunca debe exponerse al navegador. |
| `WHATSAPP_ACCESS_TOKEN` | Token de WhatsApp Cloud API. |
| `WHATSAPP_PHONE_NUMBER_ID` | Identificador del número emisor de WhatsApp Business. |
| `WHATSAPP_BIRTHDAY_TEMPLATE` | Nombre de la plantilla aprobada para cumpleaños; cuerpo con un parámetro: nombre. |
| `WHATSAPP_NEWS_TEMPLATE` | Nombre de la plantilla aprobada para novedades; cuerpo con dos parámetros: título y contenido. |
| `WHATSAPP_TEMPLATE_LANGUAGE` | Idioma aprobado de las plantillas; por defecto `es_AR`. |
| `WHATSAPP_GRAPH_API_VERSION` | Versión de Graph API; por defecto `v23.0`. |

Los envíos de WhatsApp permanecen desactivados hasta configurar token, identificador y nombre de la plantilla correspondiente. No se envían mensajes a teléfonos sin autorización expresa en la ficha del socio.

## Usuarios y permisos

El alta y mantenimiento de cuentas se realiza en **Administración → Usuarios y permisos**. Las cuentas administradoras se guardan en la tabla `cobradores` y pueden ingresar con su nombre de usuario y clave local. Los roles disponibles son `cobrador`, `admin` y `superadmin`. Los cobradores deben estar asociados a un socio activo; las cuentas administrativas no.

Las claves se almacenan como hashes generados por Werkzeug, nunca como texto plano. La cuenta de superadministrador debe mantenerse en manos de una persona responsable y las sesiones administrativas requieren credenciales válidas.

La autenticación existente de Supabase por correo sigue habilitada para cuentas de administración previamente configuradas. No se requiere Supabase Auth para las nuevas cuentas locales creadas desde el formulario de usuarios.

## Despliegue en Render

### Servicio web

- Conectá el repositorio y su rama de despliegue.
- Build command: `pip install -r requirements.txt`.
- Start command: `gunicorn app:app`.
- Configurá las variables obligatorias y cualquier variable opcional en **Environment**.
- La URL de PostgreSQL debe ser accesible desde Render. Si se usa Supabase, comprobá que la cadena corresponda al modo de conexión y al driver indicados por Supabase.

### Cron de WhatsApp

Para cumpleaños y la cola de novedades, creá un Render Cron Job con el mismo repositorio, rama, Python y variables de entorno:

- Command: `python -m jobs.procesar_whatsapp`
- Schedule: `*/5 * * * *` (Render interpreta el cron en UTC; el programa usa `America/Argentina/Buenos_Aires`).

El proceso encola los cumpleaños desde las 9:00 hora argentina y procesa hasta 50 mensajes pendientes por ejecución. Los envíos son individuales; crear una novedad no la envía automáticamente. El botón **Enviar por WhatsApp** permite revisar y ponerla en cola.

### Archivos subidos

Los documentos y fotos se guardan hoy dentro de `static/`. El disco de un servicio Render puede ser efímero y los Cron Jobs no comparten un disco persistente con el servicio web. Antes de depender de archivos cargados en producción, migrá esos archivos a almacenamiento persistente (por ejemplo, Supabase Storage) o configurá una solución compatible; no asumas que los archivos sobrevivirán a un redeploy o reinicio.

## Estructura principal

| Ruta | Responsabilidad |
|---|---|
| `app.py` | Crea la aplicación, registra blueprints y prepara parte del esquema inicial. |
| `routes/auth.py` | Inicio/cierre de sesión, registro heredado por WhatsApp y recuperación de contraseña. |
| `auth_manager.py` | Decoradores de acceso y validación/refresco de sesiones Supabase. |
| `routes/admin.py` | Usuarios, configuración institucional, novedades y archivos del portal. |
| `routes/socios.py` | Portal público, padrón, cuotas, recibos y caja. |
| `models.py` | Inicializa SQLAlchemy y declara los modelos ORM disponibles. La mayoría de consultas usan SQL explícito porque el esquema es preexistente. |
| `config.py` | Variables de entorno, clientes Supabase, archivos y configuración institucional. |
| `whatsapp_service.py` | Envío de plantillas aprobadas por WhatsApp Cloud API. |
| `jobs/procesar_whatsapp.py` | Cola y envío periódico de cumpleaños y novedades. |
| `templates/` | Vistas Jinja. |
| `static/` | JavaScript, CSS, imágenes y archivos servidos por el sitio. |

Los scripts `migrar_datos.py` y `cargar_movimientos.py` son importadores puntuales de CSV; no forman parte del arranque del sitio. Revisá sus datos de entrada y hacé un respaldo de la base antes de usarlos.

## Validación local

```powershell
python -m compileall -q app.py auth_manager.py config.py models.py routes jobs whatsapp_service.py
python -m unittest discover -s tests -v
```

`test_conexion.py`, cuando exista en una copia local, es una prueba de conectividad en vivo: no es una prueba aislada y puede acceder a la base configurada en `.env`.

## Mantenimiento y seguridad operativa

- No publiques `.env`, claves de Supabase, tokens de WhatsApp ni datos personales de socios.
- Conservá copias de seguridad de PostgreSQL antes de desplegar cambios de esquema o importar CSV.
- Las columnas migradas por `app.py` se agregan en el arranque; para cambios mayores, preferí migraciones versionadas y revisables.
- Las pruebas unitarias no llaman a WhatsApp ni a la base de producción. Antes de un envío real, verificá el consentimiento, la plantilla aprobada, el número emisor y una cuenta de prueba.
- Los grupos de WhatsApp existentes no son destino de la Cloud API utilizada aquí. El sistema envía mensajes uno a uno a los socios que autorizaron recibirlos.
