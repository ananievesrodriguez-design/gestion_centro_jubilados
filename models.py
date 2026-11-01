from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Socio(db.Model):
    __tablename__ = "socios"
    id = db.Column(db.Integer, primary_key=True)
    nro_socio = db.Column(db.Integer)
    dni = db.Column(db.String(15), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(30), default="Activo")


class Cobrador(db.Model):
    __tablename__ = "cobradores"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100))
    email = db.Column(db.String(255))
    password = db.Column(db.String(255))
