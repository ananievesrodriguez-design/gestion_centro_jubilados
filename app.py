import os
from flask import Flask
from sqlalchemy import text
from dotenv import load_dotenv
from config import SECRET_KEY, DATABASE_URL, inject_global_context
from models import db
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.socios import socios_bp

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
        except Exception as e:
            db.session.rollback()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
