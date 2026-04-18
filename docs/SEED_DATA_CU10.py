"""
Seed script para cargar datos de prueba para CU10.
Crea specialties, workshops y technicians.

Uso:
    python docs/SEED_DATA_CU10.py
"""

import uuid
from app.database import SessionLocal
from app.module_workshops.models import Workshop, Specialty, WorkshopSpecialty, Technician

# IDs de usuarios existentes (obtener del seed.py o crear)
OWNER_USER_ID = uuid.UUID("12345678-1234-1234-1234-123456789abc")
TECH_USER_1 = uuid.UUID("12345678-1234-1234-1234-123456789bbb")
TECH_USER_2 = uuid.UUID("12345678-1234-1234-1234-123456789ccc")
TECH_USER_3 = uuid.UUID("12345678-1234-1234-1234-123456789ddd")

def main():
    db = SessionLocal()

    try:
        # 1. Crear especialidades
        specialties_data = [
            ("battery", "Baterías"),
            ("tire", "Llantas"),
            ("engine", "Motor"),
            ("ac", "Aire Acondicionado"),
            ("transmission", "Transmisión"),
            ("towing", "Grúa"),
            ("locksmith", "Cerrajería"),
            ("general", "General"),
        ]

        specialties = {}
        for name, _ in specialties_data:
            existing = db.query(Specialty).filter(Specialty.name == name).first()
            if existing:
                specialties[name] = existing
            else:
                spec = Specialty(name=name)
                db.add(spec)
                db.flush()
                specialties[name] = spec
                print(f"✓ Especialidad creada: {name}")

        db.commit()

        # 2. Crear talleres
        workshops_data = [
            {
                "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
                "business_name": "Taller Especialista en Llantas",
                "latitude": -17.75,
                "longitude": -63.20,
                "rating_avg": 4.8,
                "specialty": "tire",
            },
            {
                "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
                "business_name": "Taller Rápido Servicios",
                "latitude": -17.85,
                "longitude": -63.25,
                "rating_avg": 4.2,
                "specialty": "tire",
            },
            {
                "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
                "business_name": 'Taller General "Juan y Cia"',
                "latitude": -17.80,
                "longitude": -63.15,
                "rating_avg": 3.9,
                "specialty": "general",
            },
        ]

        workshops = {}
        for ws_data in workshops_data:
            existing = db.query(Workshop).filter(Workshop.id == ws_data["id"]).first()
            if existing:
                workshops[ws_data["id"]] = existing
            else:
                ws = Workshop(
                    id=ws_data["id"],
                    owner_user_id=OWNER_USER_ID,
                    business_name=ws_data["business_name"],
                    latitude=ws_data["latitude"],
                    longitude=ws_data["longitude"],
                    commission_rate=10.0,
                    rating_avg=ws_data["rating_avg"],
                    is_active=True,
                )
                db.add(ws)
                db.flush()
                workshops[ws_data["id"]] = ws
                print(f"✓ Taller creado: {ws_data['business_name']}")

                # Asignar especialidad
                spec = specialties[ws_data["specialty"]]
                ws_spec = WorkshopSpecialty(
                    workshop_id=ws.id,
                    specialty_id=spec.id,
                    is_mobile=(ws_data["specialty"] == "general"),
                )
                db.add(ws_spec)

        db.commit()

        # 3. Crear técnicos
        technicians_data = [
            {
                "user_id": TECH_USER_1,
                "workshop_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
                "name": "Pedro (Taller Llantas)",
            },
            {
                "user_id": TECH_USER_2,
                "workshop_id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
                "name": "Carlos (Taller Rápido)",
            },
            {
                "user_id": TECH_USER_3,
                "workshop_id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
                "name": "Juan (Taller General)",
            },
        ]

        for tech_data in technicians_data:
            existing = db.query(Technician).filter(
                Technician.user_id == tech_data["user_id"]
            ).first()
            if existing:
                existing.is_available = True
                db.add(existing)
            else:
                tech = Technician(
                    id=uuid.uuid4(),
                    user_id=tech_data["user_id"],
                    workshop_id=tech_data["workshop_id"],
                    is_available=True,
                )
                db.add(tech)
                print(f"✓ Técnico creado: {tech_data['name']}")

        db.commit()

        # Resumen
        print("\n✅ Seed completado:")
        print(f"  - Especialidades: {db.query(Specialty).count()}")
        print(f"  - Talleres: {db.query(Workshop).count()}")
        print(f"  - Técnicos: {db.query(Technician).count()}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
