from app import app, db
from sqlalchemy import text

with app.app_context():
    result = db.session.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'archivos_portal'
        ORDER BY ordinal_position;
    """)).fetchall()
    for row in result:
        print(row)
