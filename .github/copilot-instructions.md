# Copilot instructions

## Run and validate

- Start the Flask development server from the repository root with `python app.py`. On Windows, use `.\venv\Scripts\python.exe app.py` if the local environment is available.
- Install dependencies with `python -m pip install -r requirements.txt`. Run isolated tests with `python -m unittest discover -s tests -v`.
- Copy `.env.example` to `.env` and set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SECRET_KEY`, and `DATABASE_URL`. `SUPABASE_SERVICE_ROLE_KEY` is optional and falls back to the public Supabase client when unset.
- `test_conexion.py` is ignored by Git and may exist only in a local checkout; when present, it is a live database connectivity smoke check, not an isolated unit test.

## Architecture

- `app.py` creates the Flask app, configures sessions and SQLAlchemy, registers the `auth`, `admin`, and `socios` blueprints, and initializes required PostgreSQL columns and tables at startup.
- `routes/auth.py` handles Supabase Auth sign-in, sign-out, legacy WhatsApp registration, and password reset. New local accounts are managed in `routes/admin.py` and authenticate against password hashes in `cobradores`. `auth_manager.py` provides `login_required` and `admin_required`.
- `routes/admin.py` manages users and roles, institution settings, news, and portal files. `jobs/procesar_whatsapp.py` queues birthday reminders and sends approved WhatsApp templates; run it periodically as a Render Cron Job.
- `routes/socios.py` serves both the public member portal and the internal member registry, dues, receipts, and cash-management workflows. Use the existing authentication decorators for protected views.
- `models.py` initializes Flask-SQLAlchemy and defines only a subset of the existing database schema. Most queries use SQLAlchemy `text()` against PostgreSQL.
- `supabase_client.py` provides public and optional admin Supabase clients. `config.py` loads environment settings and handles the local institution JSON configuration, upload directories, and allowed file extensions.
- `whatsapp_service.py` sends approved WhatsApp Cloud API templates. Only send to members with explicit `whatsapp_autorizado` consent and an international-format phone; the existing WhatsApp group is not an API destination.
- Templates are Jinja files under `templates/`, with shared layout/context in `base.html`; browser behavior and styling live under `static/`.
- `migrar_datos.py` and `cargar_movimientos.py` are standalone CSV-to-PostgreSQL import scripts, not part of app startup.

## Repository-specific conventions

- Keep route handlers in existing blueprints and register any new blueprint in `app.py`. Use Flask endpoint names in templates and redirects (for example, `url_for("socios.listar_socios")`).
- Query PostgreSQL through `db.session.execute(text(...), params)` and bind values as named parameters rather than interpolating request data into SQL.
- Keep authentication checks on protected route handlers. Authentication state is stored in the Flask session.
- Reuse `config.py` helpers for institution settings, uploads, and extension checks. The local `.env`, institution JSON, CSVs, and uploaded files are ignored by Git; do not rely on personal/local data in a clean checkout.
- Use `.mappings().first()` when reading SQLAlchemy result columns by name; use `.first()` only for positional access or a truthiness check.
- Never commit `.env`, Supabase secrets, WhatsApp tokens, or member data.
- Extend the shared Jinja layout with its existing `{% block %}` sections where appropriate. Page-specific browser scripts belong in `static/js/`.
