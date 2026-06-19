import os
import sys

# Add current path to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("🧹 Limpiando datos de la base de datos...")
    db.execute(text("TRUNCATE TABLE ratings, payments, incident_status_history, workshop_offers, incident_evidence, incidents, vehicles, workshop_specialties, technicians, workshops, clients, role_user, notifications, users RESTART IDENTITY CASCADE;"))
    db.commit()
    print("✨ ¡Base de datos limpiada con éxito!")
except Exception as e:
    db.rollback()
    print("❌ Error al limpiar la base de datos:", e)
finally:
    db.close()
