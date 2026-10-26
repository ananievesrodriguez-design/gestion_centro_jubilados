import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def limpiar_dni(valor):
    if pd.isna(valor):
        return None
    # Eliminar puntos, espacios o caracteres decimales
    return str(valor).split(".")[0].replace(" ", "").strip()

def migrar_socios(csv_path="socios.csv"):
    print("\n--- INICIANDO MIGRACIÓN DE SOCIOS ---")
    # Indicamos sep=';' y quitamos espacios en blanco de los encabezados
    df = pd.read_csv(csv_path, sep=";")
    df.columns = df.columns.str.strip()

    # Mapeo exacto según tu cabecera
    mapeo = {
        "N° socio": "nro_socio",
        "Apellido": "apellido",
        "Nombre": "nombre",
        "DNI": "dni",
        "Fecha Nacimiento": "fecha_nacimiento",
        "Teléfono": "telefono",
        "Email": "email",
        "Dirección": "direccion",
        "Fecha Ingreso": "fecha_ingreso",
        "Estado": "estado",
        "Observaciones": "observaciones"
    }
    df = df.rename(columns=mapeo)
    
    # Limpieza de DNI y fechas
    df["dni"] = df["dni"].apply(limpiar_dni)
    df = df.dropna(subset=["dni"])
    df = df.drop_duplicates(subset=["dni"])

    for col_fecha in ["fecha_nacimiento", "fecha_ingreso"]:
        if col_fecha in df.columns:
            df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce", dayfirst=True)

    columnas_db = [c for c in mapeo.values() if c in df.columns]
    df[columnas_db].to_sql("socios", con=engine, if_exists="append", index=False)
    print(f"-> Se insertaron {len(df)} socios correctamente.")

######MIGRAR CUOTAS
def migrar_cuotas(csv_path="cobro_cuotas.csv"):
    print("\n--- INICIANDO MIGRACIÓN DE COBROS ---")
    
    # 1. Lectura del CSV
    df = pd.read_csv(csv_path, sep=";")
    df.columns = df.columns.str.strip()

    mapeo = {
        "N° Recibo": "nro_recibo",
        "Fecha Cobro": "fecha_cobro",
        "Nro Socio": "nro_socio",
        "Socio": "socio_nombre_csv",
        "DNI": "dni",
        "Período": "periodo",
        "Mes": "mes",
        "Año": "anio",
        "Monto": "monto",
        "Método de Pago": "metodo_pago",
        "Cobrador": "cobrador_nombre",
        "Estado": "estado",
        "Observaciones": "observaciones"
    }
    df = df.rename(columns=mapeo)
    df["dni"] = df["dni"].apply(limpiar_dni)

    # 2. Vincular con socios existentes por DNI para obtener socio_id
    socios_db = pd.read_sql("SELECT id AS socio_id, dni FROM socios", con=engine)
    socios_db["dni"] = socios_db["dni"].astype(str)
    df = df.merge(socios_db, on="dni", how="inner")

    # 3. Sincronizar cobradores usando DataFrames (evita errores de tipos en SQL)
    if "cobrador_nombre" in df.columns:
        cobradores_db = pd.read_sql("SELECT id AS cobrador_id, nombre FROM cobradores", con=engine)
        cobradores_existentes = set(cobradores_db["nombre"].str.strip().str.lower())

        cobradores_csv = [
            c.strip() for c in df["cobrador_nombre"].dropna().unique() 
            if str(c).strip() and str(c).strip().lower() not in cobradores_existentes
        ]

        # Insertar los cobradores nuevos que no figuren en la base
        if cobradores_csv:
            df_nuevos = pd.DataFrame({
                "nombre": cobradores_csv,
                "apellido": "",
                "activo": True
            })
            df_nuevos.to_sql("cobradores", con=engine, if_exists="append", index=False)

        # Volver a leer cobradores con sus IDs actualizados
        cobradores_db = pd.read_sql("SELECT id AS cobrador_id, LOWER(TRIM(nombre)) AS cobrador_norm FROM cobradores", con=engine)
        df["cobrador_norm"] = df["cobrador_nombre"].astype(str).str.strip().str.lower()
        df = df.merge(cobradores_db, on="cobrador_norm", how="left")
    else:
        df["cobrador_id"] = None

    # 4. Limpieza de datos (fechas, montos y números)
    df["fecha_cobro"] = pd.to_datetime(df["fecha_cobro"], errors="coerce", dayfirst=True)
    df["monto"] = pd.to_numeric(
        df["monto"].astype(str).str.replace("$", "", regex=False).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).str.strip(),
        errors="coerce"
    ).fillna(0.0)
    
    if "mes" in df.columns:
        df["mes"] = pd.to_numeric(df["mes"], errors="coerce")
    if "anio" in df.columns:
        df["anio"] = pd.to_numeric(df["anio"], errors="coerce").fillna(2026).astype(int)

    columnas_finales = [
        "nro_recibo", "fecha_cobro", "socio_id", "periodo", 
        "mes", "anio", "monto", "metodo_pago", "cobrador_id", 
        "estado", "observaciones"
    ]
    df_insert = df[[c for c in columnas_finales if c in df.columns]]
    
    df_insert.to_sql("cobro_cuotas", con=engine, if_exists="append", index=False)
    print(f"-> Se insertaron {len(df_insert)} cobros vinculados correctamente.")
    
#######################################################
#migrar caja
def migrar_caja(csv_path="movimientos_caja.csv"):
    print("\n--- INICIANDO MIGRACIÓN DE MOVIMIENTOS DE CAJA ---")
    df = pd.read_csv(csv_path, sep=";")

    mapeo = {
        "fecha": "fecha",
        "tipo": "tipo",
        "categoria": "categoria",
        "concepto": "concepto",
        "monto": "monto",
        "comprobante": "comprobante",
        "interviene": "interviene",
        "metodo": "metodo",
        "Observaciones": "observaciones"
    }
    df = df.rename(columns=mapeo)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0.0)

    columnas_validas = [c for c in mapeo.values() if c in df.columns]
    df[columnas_validas].to_sql("movimientos_caja", con=engine, if_exists="append", index=False)
    print(f"-> Se insertaron {len(df)} movimientos de caja.")

if __name__ == "__main__":
   # migrar_socios()
    migrar_cuotas()
   # migrar_caja()