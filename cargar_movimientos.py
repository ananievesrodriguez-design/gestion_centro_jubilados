import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar variables de entorno
load_dotenv()
database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("❌ Error: No se encontró la variable DATABASE_URL en el archivo .env")
    exit()

# Ajuste para psycopg si es necesario
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(database_url)

csv_path = "movimientos_caja.csv"

if not os.path.exists(csv_path):
    print(f"❌ Error: No se encontró el archivo '{csv_path}' en la raíz del proyecto.")
    print("Asegurate de copiar el archivo en la misma carpeta donde está app.py.")
    exit()

print(f"📂 Leyendo archivo '{csv_path}'...")
# Intentamos leer con delimitador coma o punto y coma
try:
    # Intentamos primero con latin1 / cp1252 (formato estándar de Excel en español)
    df = pd.read_csv(csv_path, sep=None, engine="python", encoding="latin1")
except UnicodeDecodeError:
    # Fallback por si viniera en utf-8 con BOM
    df = pd.read_csv(csv_path, sep=None, engine="python", encoding="utf-8-sig")
except Exception as e:
    print(f"❌ Error al leer el CSV: {e}")
    exit()

# Normalizar nombres de columnas a minúsculas y sin espacios
df.columns = [c.strip().lower() for c in df.columns]
print("Columnas detectadas en el CSV:", list(df.columns))

# Mapeo flexible de columnas para contemplar variantes comunes
col_mapping = {
    'tipo': 'tipo',
    'categoria': 'categoria',
    'concepto': 'concepto',
    'detalle': 'concepto',
    'monto': 'monto',
    'importe': 'monto',
    'fecha': 'fecha',
    'comprobante': 'comprobante',
    'factura': 'comprobante',
    'interviene': 'interviene',
    'responsable': 'interviene',
    'metodo': 'metodo',
    'forma_pago': 'metodo',
    'observaciones': 'observaciones'
}

df = df.rename(columns=col_mapping)

registros_insertados = 0
registros_omitidos = 0

with engine.begin() as conn:
    for index, row in df.iterrows():
        # Limpieza y conversión de datos
        tipo = str(row.get('tipo', 'Egreso')).strip().capitalize()
        categoria = str(row.get('categoria', 'Varios')).strip()
        concepto = str(row.get('concepto', '')).strip()

        # Monto limpio (quita signos $ o comas decimales si vienen como string)
        raw_monto = str(row.get('monto', 0)).replace('$', '').replace(' ', '')
        if ',' in raw_monto and '.' in raw_monto:
            raw_monto = raw_monto.replace('.', '').replace(',', '.')
        elif ',' in raw_monto:
            raw_monto = raw_monto.replace(',', '.')
        try:
            monto = float(raw_monto)
        except ValueError:
            monto = 0.0

        if monto <= 0:
            registros_omitidos += 1
            continue

        # Formato de fecha flexible
        raw_fecha = str(row.get('fecha', '')).strip()
        fecha_final = None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
            try:
                fecha_final = datetime.strptime(raw_fecha, fmt).date()
                break
            except ValueError:
                pass
        
        if not fecha_final:
            fecha_final = datetime.today().date()

        comprobante = str(row.get('comprobante', '')).strip() if pd.notna(row.get('comprobante')) else None
        interviene = str(row.get('interviene', '')).strip() if pd.notna(row.get('interviene')) else None
        metodo = str(row.get('metodo', 'Efectivo')).strip() if pd.notna(row.get('metodo')) else 'Efectivo'
        observaciones = str(row.get('observaciones', '')).strip() if pd.notna(row.get('observaciones')) else None

        query = text("""
            INSERT INTO movimientos_caja (
                fecha, tipo, categoria, concepto, monto, comprobante, interviene, metodo, observaciones
            )
            VALUES (
                :fecha, :tipo, :categoria, :concepto, :monto, :comprobante, :interviene, :metodo, :observaciones
            );
        """)
        
        conn.execute(query, {
            "fecha": fecha_final,
            "tipo": tipo,
            "categoria": categoria,
            "concepto": concepto,
            "monto": monto,
            "comprobante": comprobante,
            "interviene": interviene,
            "metodo": metodo,
            "observaciones": observaciones
        })
        registros_insertados += 1

print(f"\n✅ ¡Migración completada con éxito!")
print(f"📦 Registros ingresados a movimientos_caja: {registros_insertados}")
if registros_omitidos > 0:
    print(f"⚠️ Registros omitidos (sin monto válido): {registros_omitidos}")