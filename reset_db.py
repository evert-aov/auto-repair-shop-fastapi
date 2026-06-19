from sqlalchemy import text
from app.database import SessionLocal

print("Dropping all tables with CASCADE...")
db = SessionLocal()
try:
    result = db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    tables = [row[0] for row in result.fetchall()]
    for table in tables:
        db.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    db.commit()
    print("All tables dropped with CASCADE.")
except Exception as e:
    db.rollback()
    print(f"Error dropping tables: {e}")
finally:
    db.close()
