import os
from flask import Flask, render_template
from sqlalchemy import text
from dotenv import load_dotenv
from config import SECRET_KEY, DATABASE_URL, inject_global_context
from models import db
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.socios import socios_bp
from werkzeug.exceptions import HTTPException

load_dotenv()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(socios_bp)
    app.context_processor(inject_global_context)

    with app.app_context():
        try:
            db.session.execute(text("""
                ALTER TABLE cobradores
                ADD COLUMN IF NOT EXISTS socio_id INTEGER;
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ADD COLUMN IF NOT EXISTS username VARCHAR(40);
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ADD COLUMN IF NOT EXISTS habilitado BOOLEAN;
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ADD COLUMN IF NOT EXISTS rol VARCHAR(20);
            """))
            db.session.execute(text("""
                UPDATE cobradores
                SET habilitado = (password IS NOT NULL)
                WHERE habilitado IS NULL;
            """))
            db.session.execute(text("""
                UPDATE cobradores
                SET rol = 'cobrador'
                WHERE rol IS NULL OR rol NOT IN ('cobrador', 'admin', 'superadmin');
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ALTER COLUMN habilitado SET DEFAULT TRUE;
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ALTER COLUMN habilitado SET NOT NULL;
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ALTER COLUMN rol SET DEFAULT 'cobrador';
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ALTER COLUMN rol SET NOT NULL;
            """))
            db.session.execute(text("""
                ALTER TABLE cobradores
                ALTER COLUMN email DROP NOT NULL;
            """))
            db.session.execute(text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_cobradores_socio_id'
                          AND conrelid = 'cobradores'::regclass
                    ) THEN
                        ALTER TABLE cobradores
                        ADD CONSTRAINT fk_cobradores_socio_id
                        FOREIGN KEY (socio_id) REFERENCES socios(id);
                    END IF;
                END $$;
            """))
            db.session.execute(text("""
                DO $$
                DECLARE definicion_rol TEXT;
                BEGIN
                    SELECT pg_get_constraintdef(oid)
                    INTO definicion_rol
                    FROM pg_constraint
                    WHERE conname = 'ck_cobradores_rol'
                      AND conrelid = 'cobradores'::regclass;

                    IF definicion_rol IS NULL THEN
                        ALTER TABLE cobradores
                        ADD CONSTRAINT ck_cobradores_rol
                        CHECK (rol IN ('cobrador', 'admin', 'superadmin'));
                    ELSIF position('superadmin' IN definicion_rol) = 0 THEN
                        ALTER TABLE cobradores
                        DROP CONSTRAINT ck_cobradores_rol;
                        ALTER TABLE cobradores
                        ADD CONSTRAINT ck_cobradores_rol
                        CHECK (rol IN ('cobrador', 'admin', 'superadmin'));
                    END IF;
                END $$;
            """))
            db.session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_cobradores_username
                ON cobradores (LOWER(username))
                WHERE username IS NOT NULL;
            """))
            db.session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_cobradores_socio_id
                ON cobradores (socio_id)
                WHERE socio_id IS NOT NULL;
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS auth_cobrador_challenges (
                    cobrador_id INTEGER PRIMARY KEY REFERENCES cobradores(id) ON DELETE CASCADE,
                    username VARCHAR(40) NOT NULL,
                    codigo_hash VARCHAR(64) NOT NULL,
                    expira_en TIMESTAMPTZ NOT NULL,
                    reintentos INTEGER NOT NULL DEFAULT 0,
                    proximo_envio TIMESTAMPTZ NOT NULL,
                    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
            db.session.execute(text("""
                ALTER TABLE socios
                ADD COLUMN IF NOT EXISTS whatsapp_autorizado BOOLEAN NOT NULL DEFAULT FALSE;
            """))
            db.session.execute(text("""
                ALTER TABLE socios
                ADD COLUMN IF NOT EXISTS whatsapp_autorizado_en TIMESTAMPTZ;
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS whatsapp_envios (
                    id BIGSERIAL PRIMARY KEY,
                    socio_id INTEGER NOT NULL REFERENCES socios(id) ON DELETE CASCADE,
                    tipo VARCHAR(20) NOT NULL,
                    referencia VARCHAR(100) NOT NULL,
                    telefono VARCHAR(30) NOT NULL,
                    parametro_1 TEXT NOT NULL,
                    parametro_2 TEXT,
                    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
                    error TEXT,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_whatsapp_envio UNIQUE (socio_id, tipo, referencia),
                    CONSTRAINT ck_whatsapp_envio_tipo CHECK (tipo IN ('cumpleanos', 'novedad')),
                    CONSTRAINT ck_whatsapp_envio_estado
                        CHECK (estado IN ('pendiente', 'procesando', 'enviado', 'fallido'))
                );
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("No se pudo preparar el acceso seguro de cobradores")
            raise

        try:
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
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS archivos_portal (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(200) NOT NULL,
                    descripcion TEXT,
                    tipo VARCHAR(50) NOT NULL,
                    archivo VARCHAR(255) NOT NULL,
                    fecha_subida TIMESTAMP DEFAULT NOW(),
                    activa BOOLEAN DEFAULT TRUE,
                    orden INT DEFAULT 0
                );
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("No se pudieron inicializar las tablas auxiliares")

    @app.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template(
            "error.html",
            titulo="Página no encontrada",
            mensaje="La página solicitada no existe o ya no está disponible.",
        ), 404

    @app.errorhandler(Exception)
    def error_no_controlado(error):
        if isinstance(error, HTTPException):
            return error
        db.session.rollback()
        app.logger.exception("Error no controlado durante la solicitud")
        return render_template(
            "error.html",
            titulo="No se pudo completar la solicitud",
            mensaje="Ocurrió un error inesperado. Inténtelo nuevamente o vuelva a la página anterior.",
        ), 500

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(debug=debug)
