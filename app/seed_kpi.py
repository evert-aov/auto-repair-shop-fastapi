import random
import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal, Base, engine
from app.users.models.user import User
from app.users.models.role import Role
from app.clients.models import Client, Vehicle, TransmissionType, FuelType
from app.workshops.models import Workshop, Technician, Specialty, WorkshopSpecialty
from app.incidents.models import (
    Incident, IncidentStatus, IncidentPriority,
    WorkshopOffer, OfferStatus, Rating, RejectionReason
)
from app.incidents.models.incident_status_history import IncidentStatusHistory
from app.payments.models import Payment, PaymentStatus, PaymentMethod


# Coordenadas de Santa Cruz de la Sierra, Bolivia
SCZ_CENTER_LAT = -17.783
SCZ_CENTER_LNG = -63.180

CATEGORIES = ["battery", "tire", "engine", "towing", "ac", "general", "transmission", "locksmith"]
PRIORITIES = [IncidentPriority.LOW, IncidentPriority.MEDIUM, IncidentPriority.HIGH, IncidentPriority.CRITICAL]

def generate_random_coords(zone: str) -> tuple[float, float]:
    lat_offset = random.uniform(0.005, 0.035)
    lng_offset = random.uniform(0.005, 0.035)
    
    if zone == "Norte":
        return SCZ_CENTER_LAT + lat_offset, SCZ_CENTER_LNG + random.uniform(-0.015, 0.015)
    elif zone == "Sur":
        return SCZ_CENTER_LAT - lat_offset, SCZ_CENTER_LNG + random.uniform(-0.015, 0.015)
    elif zone == "Este":
        return SCZ_CENTER_LAT + random.uniform(-0.015, 0.015), SCZ_CENTER_LNG + lng_offset
    elif zone == "Oeste":
        return SCZ_CENTER_LAT + random.uniform(-0.015, 0.015), SCZ_CENTER_LNG - lng_offset
    else: # Centro
        return SCZ_CENTER_LAT + random.uniform(-0.01, 0.01), SCZ_CENTER_LNG + random.uniform(-0.01, 0.01)


def clear_db(db: Session):
    print("🧹 Cleaning database...")
    db.execute(text("DELETE FROM ratings"))
    db.execute(text("DELETE FROM payments"))
    db.execute(text("DELETE FROM incident_status_history"))
    db.execute(text("DELETE FROM workshop_offers"))
    db.execute(text("DELETE FROM incident_evidence"))
    db.execute(text("DELETE FROM incidents"))
    db.execute(text("DELETE FROM vehicles"))
    db.execute(text("DELETE FROM workshop_specialties"))
    db.execute(text("DELETE FROM technicians"))
    db.execute(text("DELETE FROM workshops"))
    db.execute(text("DELETE FROM clients"))
    db.execute(text("DELETE FROM role_user"))
    db.execute(text("DELETE FROM notifications"))
    db.execute(text("DELETE FROM users"))
    db.commit()
    print("✨ Database cleaned successfully.")


def run_kpi_seed():
    # Precompute bcrypt hashes for speed
    print("⏳ Precomputing password hashes...")
    HASHED_PASSWORD123 = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8")
    HASHED_ADMIN123 = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")
    print("✅ Password hashes precomputed.")

    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        # Clear the database before seeding to guarantee exact counts and fresh status
        clear_db(db)

        # Ensure Roles and Specialties exist (recreate if empty after clear or on a fresh DB)
        role_map = {role.name: role for role in db.query(Role).all()}
        all_specs = db.query(Specialty).all()
        
        if not role_map:
            print("🌱 Roles not found. Creating default roles...")
            for rname in ["admin", "workshop_owner", "technician", "client"]:
                role = Role(name=rname, description=f"Rol {rname}")
                db.add(role)
            db.commit()
            role_map = {role.name: role for role in db.query(Role).all()}

        if not all_specs:
            print("🌱 Specialties not found. Creating default specialties...")
            for sname in ["general", "battery", "tire", "engine", "ac", "transmission", "towing", "locksmith"]:
                spec = Specialty(name=sname)
                db.add(spec)
            db.commit()
            all_specs = db.query(Specialty).all()

        # 1. Create exactly 1 admin user with password 'admin123'
        print("🌱 Creating admin user...")
        admin_user = User(
            id=uuid.uuid4(),
            username="admin",
            name="Administrador",
            last_name="Sistema",
            email="admin@autorepair.com",
            password=HASHED_ADMIN123,
            phone="70000000",
            type="user"
        )
        admin_user.roles = [role_map["admin"]]
        db.add(admin_user)
        db.flush()
        print("  ✅ Admin user created.")

        # Lists for random names/makes for clients & vehicles
        FIRST_NAMES = ["Juan", "Maria", "Pedro", "Ana", "Carlos", "Lucia", "Luis", "Elena", "Jose", "Sofia",
                       "Miguel", "Laura", "Jorge", "David", "Valeria", "Diego", "Paula", "Andres", "Camila", "Mateo"]
        LAST_NAMES = ["Perez", "Gomez", "Rodriguez", "Gonzalez", "Fernandez", "Lopez", "Martinez", "Sanchez", "Romero", "Torres",
                      "Ruiz", "Diaz", "Vargas", "Morales", "Ortiz", "Castro", "Rios", "Alvarez", "Mendoza", "Rojas"]
                      
        VEHICLE_MAKES = ["Toyota", "Suzuki", "Honda", "Hyundai", "Nissan", "Ford", "Chevrolet", "Kia", "Mitsubishi", "Mazda"]
        VEHICLE_MODELS = {
            "Toyota": ["Corolla", "Hilux", "RAV4", "Yaris"],
            "Suzuki": ["Swift", "Grand Vitara", "Jimny", "Carry"],
            "Honda": ["Civic", "CR-V", "Fit", "Accord"],
            "Hyundai": ["Tucson", "Accent", "Santa Fe", "i10"],
            "Nissan": ["Sentra", "Frontier", "Kicks", "Versa"],
            "Ford": ["Ranger", "Explorer", "Fiesta", "EcoSport"],
            "Chevrolet": ["Onix", "Tracker", "S10", "Cruze"],
            "Kia": ["Rio", "Sportage", "Picanto", "Cerato"],
            "Mitsubishi": ["L200", "Outlander", "Montero", "ASX"],
            "Mazda": ["Mazda 3", "CX-5", "CX-3", "BT-50"]
        }
        COLORS = ["Blanco", "Negro", "Gris", "Plata", "Rojo", "Azul", "Verde"]

        # 2. Create exactly 300 client users
        print("🌱 Creating 300 client users...")
        clients = []
        for i in range(1, 301):
            fname = FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]
            lname = LAST_NAMES[(i - 1) % len(LAST_NAMES)]
            username = f"{fname.lower()}_{lname.lower()}_{i}"
            email = f"{username}@gmail.com"
            phone = f"7{i:07d}"
            address = f"Calle {random.choice(['Los Pinos', 'Las Palmas', 'San Martin', 'Equipetrol', 'Banzer', 'Grigota'])} #{random.randint(10, 500)}"
            
            # Random registration date between Jan 1, 2026 and now (roughly 160 days)
            reg_days_ago = random.uniform(0, 160)
            c_created = now - timedelta(days=reg_days_ago)

            client = Client(
                id=uuid.uuid4(),
                username=username,
                name=fname,
                last_name=lname,
                email=email,
                password=HASHED_PASSWORD123,
                phone=phone,
                address=address,
                type="client",
                created_at=c_created,
                updated_at=c_created
            )
            client.roles = [role_map["client"]]
            db.add(client)
            db.flush()
            clients.append(client)
            
            # Create 1 or 2 vehicles per client
            num_vehicles = random.choice([1, 2])
            for v_idx in range(num_vehicles):
                make = random.choice(VEHICLE_MAKES)
                model = random.choice(VEHICLE_MODELS[make])
                license_plate = f"{1000 + i:04d}-{random.choice(['ABC', 'XYZ', 'KPL', 'MTR'])}{v_idx}"
                vehicle = Vehicle(
                    id=uuid.uuid4(),
                    client_id=client.id,
                    make=make,
                    model=model,
                    year=random.randint(2015, 2024),
                    license_plate=license_plate,
                    color=random.choice(COLORS),
                    transmission_type=random.choice([TransmissionType.automatic, TransmissionType.manual]),
                    fuel_type=random.choice([FuelType.gasoline, FuelType.diesel, FuelType.electric])
                )
                db.add(vehicle)
        db.flush()
        print("  ✅ 300 clients and vehicles created.")

        # 3. Create exactly 50 workshops
        print("🌱 Creating 50 workshops and their technicians...")
        workshops = []
        zones = ["Centro", "Norte", "Sur", "Este", "Oeste"]
        
        for i in range(1, 51):
            wname = f"Taller {FIRST_NAMES[(i - 1) % len(FIRST_NAMES)]} {i}"
            business_name = f"{wname} S.R.L."
            ruc_nit = f"NIT-8899{i:03d}-1"
            address = f"Av. {random.choice(['Banzer', 'Santos Dumont', 'Virgen de Cotoca', 'Grigota', 'San Aurelio'])} y {random.randint(2, 8)}to Anillo"
            phone = f"3344{i:04d}"
            
            zone = zones[(i - 1) % len(zones)]
            lat, lng = generate_random_coords(zone)
            
            o_id = uuid.uuid4()
            w_id = uuid.uuid4()
            
            # Random registration date between Jan 1, 2026 and now (roughly 160 days)
            reg_days_ago = random.uniform(0, 160)
            w_created = now - timedelta(days=reg_days_ago)

            workshop = Workshop(
                id=w_id,
                owner_user_id=o_id,
                name=wname,
                business_name=business_name,
                ruc_nit=ruc_nit,
                address=address,
                phone=phone,
                latitude=lat,
                longitude=lng,
                is_active=True,
                is_available=True,
                is_verified=True,
                commission_rate=10.0,
                rating_avg=5.0,
                total_services=0,
                created_at=w_created,
                updated_at=w_created
            )
            db.add(workshop)
            db.flush()
            workshops.append(workshop)
            
            # Associate specialties
            for spec in all_specs:
                ws = WorkshopSpecialty(workshop_id=w_id, specialty_id=spec.id)
                db.add(ws)
            
            # Owner (Technician)
            owner = Technician(
                id=o_id,
                username=f"owner_{i}",
                name=f"Dueño {wname}",
                last_name="Taller",
                email=f"owner_{i}@gmail.com",
                password=HASHED_PASSWORD123,
                phone=phone,
                type="technician",
                workshop_id=w_id,
                is_active=True,
                is_available=True,
                current_latitude=lat,
                current_longitude=lng,
                created_at=w_created,
                updated_at=w_created
            )
            owner.roles = [role_map["workshop_owner"], role_map["technician"]]
            db.add(owner)
            
            # Auxiliary Technician
            tech_id = uuid.uuid4()
            tech = Technician(
                id=tech_id,
                username=f"tech_{i}",
                name=f"Técnico {wname}",
                last_name="Auxiliar",
                email=f"tech_{i}@gmail.com",
                password=HASHED_PASSWORD123,
                phone=phone,
                type="technician",
                workshop_id=w_id,
                is_active=True,
                is_available=True,
                current_latitude=lat + random.uniform(-0.002, 0.002),
                current_longitude=lng + random.uniform(-0.002, 0.002),
                created_at=w_created,
                updated_at=w_created
            )
            tech.roles = [role_map["technician"]]
            db.add(tech)
        db.flush()
        print("  ✅ 50 workshops and technicians created.")

        # 4. Create completed services (at least 10 completed incidents per workshop)
        print("🌱 Seeding completed services (exactly 10 per workshop)...")
        
        COMMENTS = [
            "Excelente servicio, muy rápido y profesional.",
            "Solucionaron el problema en poco tiempo. Muy recomendado.",
            "Muy amables y puntuales. Excelente atención.",
            "Buen trabajo, el técnico fue muy cuidadoso.",
            "Precios justos y servicio confiable.",
            "Llegaron más rápido de lo esperado, excelente.",
            "Muy conforme con la reparación de mi vehículo.",
            "Atención impecable y diagnóstico acertado.",
            "Gran profesionalismo y excelente trato al cliente.",
            "Todo excelente, volveré a contratarlos si lo necesito."
        ]
        
        for w_idx, workshop in enumerate(workshops):
            technicians = db.query(Technician).filter(Technician.workshop_id == workshop.id).all()
            
            # Every workshop must have completed at least 10 services
            for inc_idx in range(10):
                client = random.choice(clients)
                vehicles = db.query(Vehicle).filter(Vehicle.client_id == client.id).all()
                vehicle = random.choice(vehicles) if vehicles else None
                
                category = random.choice(CATEGORIES)
                priority = random.choice(PRIORITIES)
                
                # Coordinates relative to workshop
                lat = float(workshop.latitude) + random.uniform(-0.01, 0.01)
                lng = float(workshop.longitude) + random.uniform(-0.01, 0.01)
                
                # Coherent date: must be after both client and workshop registration
                client_created = client.created_at
                workshop_created = workshop.created_at
                latest_created = max(client_created, workshop_created)
                
                time_window_seconds = (now - latest_created).total_seconds()
                if time_window_seconds > 0:
                    created_at = latest_created + timedelta(seconds=random.uniform(0, time_window_seconds))
                else:
                    created_at = now
                
                incident_id = uuid.uuid7()
                gross = round(random.uniform(100.0, 800.0), 2)
                comm = round(gross * 0.10, 2)
                net = round(gross - comm, 2)
                
                tech = random.choice(technicians)
                est_arrival = random.randint(10, 25)
                
                incident = Incident(
                    id=incident_id,
                    client_id=client.id,
                    vehicle_id=vehicle.id if vehicle else None,
                    description=f"Auxilio mecánico por falla de {category}",
                    incident_lat=lat,
                    incident_lng=lng,
                    status=IncidentStatus.COMPLETED,
                    ai_category=category,
                    ai_priority=priority,
                    ai_summary=f"El cliente solicita asistencia debido a un problema con {category}.",
                    ai_confidence=round(random.uniform(0.75, 0.99), 2),
                    created_at=created_at,
                    updated_at=created_at + timedelta(minutes=random.uniform(30, 90)),
                    assigned_workshop_id=workshop.id,
                    assigned_technician_id=tech.id,
                    estimated_arrival_min=est_arrival,
                    total_cost=gross
                )
                db.add(incident)
                db.flush()
                
                # History logs
                t_pending = created_at
                t_analyzing = t_pending + timedelta(seconds=10)
                t_matched = t_analyzing + timedelta(seconds=20)
                t_assigned = t_matched + timedelta(seconds=random.uniform(30, 120))
                t_arrival = t_assigned + timedelta(minutes=random.uniform(5, est_arrival + 5))
                t_completed = t_arrival + timedelta(minutes=random.uniform(20, 45))
                
                histories = [
                    IncidentStatusHistory(incident_id=incident_id, previous_status=None, new_status=IncidentStatus.PENDING.value, reason="Incidente reportado", created_at=t_pending),
                    IncidentStatusHistory(incident_id=incident_id, previous_status=IncidentStatus.PENDING.value, new_status=IncidentStatus.ANALYZING.value, reason="IA analizando", created_at=t_analyzing),
                    IncidentStatusHistory(incident_id=incident_id, previous_status=IncidentStatus.ANALYZING.value, new_status=IncidentStatus.MATCHED.value, reason="Taller óptimo encontrado", created_at=t_matched),
                    IncidentStatusHistory(incident_id=incident_id, previous_status=IncidentStatus.MATCHED.value, new_status=IncidentStatus.ASSIGNED.value, reason="Taller aceptó el servicio", created_at=t_assigned),
                    IncidentStatusHistory(incident_id=incident_id, previous_status=IncidentStatus.ASSIGNED.value, new_status=IncidentStatus.IN_PROGRESS.value, reason="Técnico llegó al lugar", created_at=t_arrival),
                    IncidentStatusHistory(incident_id=incident_id, previous_status=IncidentStatus.IN_PROGRESS.value, new_status=IncidentStatus.COMPLETED.value, reason="Servicio concluido exitosamente", created_at=t_completed)
                ]
                for h in histories:
                    db.add(h)
                    
                # Workshop offer
                offer = WorkshopOffer(
                    id=uuid.uuid4(),
                    incident_id=incident_id,
                    workshop_id=workshop.id,
                    status=OfferStatus.ACCEPTED,
                    distance_km=round(random.uniform(1.0, 10.0), 2),
                    ai_score=round(random.uniform(0.70, 0.99), 2),
                    notified_at=t_matched,
                    accepted_at=t_assigned,
                    created_at=t_matched,
                    expires_at=t_matched + timedelta(minutes=3)
                )
                db.add(offer)
                
                # Payment
                payment = Payment(
                    id=uuid.uuid7(),
                    incident_id=incident_id,
                    client_id=client.id,
                    workshop_id=workshop.id,
                    gross_amount=gross,
                    commission_amount=comm,
                    net_amount=net,
                    currency="BOB",
                    payment_method=random.choice([PaymentMethod.QR, PaymentMethod.CARD, PaymentMethod.CASH]),
                    status=PaymentStatus.COMPLETED,
                    paid_at=t_completed,
                    created_at=t_completed
                )
                db.add(payment)
                
                # Rating
                rating = Rating(
                    id=uuid.uuid4(),
                    incident_id=incident_id,
                    client_id=client.id,
                    workshop_id=workshop.id,
                    score=random.choice([4, 5, 5, 5, 3]),
                    response_time_score=random.choice([4, 5, 5]),
                    quality_score=random.choice([4, 5, 5, 5]),
                    comment=random.choice(COMMENTS),
                    created_at=t_completed + timedelta(minutes=random.randint(5, 30))
                )
                db.add(rating)
        db.flush()
        print("  ✅ All completed incidents, payments, ratings, and histories created.")

        # 5. Update workshops stats aggregates (rating_avg and total_services)
        print("🌱 Updating workshops stats aggregates...")
        for workshop in workshops:
            ratings = db.query(Rating.score).filter(Rating.workshop_id == workshop.id).all()
            if ratings:
                avg_score = sum(r[0] for r in ratings) / len(ratings)
                workshop.rating_avg = round(avg_score, 2)
            else:
                workshop.rating_avg = 5.0
            
            completed_count = db.query(Incident).filter(
                Incident.assigned_workshop_id == workshop.id,
                Incident.status == IncidentStatus.COMPLETED
            ).count()
            workshop.total_services = completed_count

        db.commit()
        print("\n🎉 Seeding de KPI con alto volumen completado exitosamente!")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error al sembrar datos de KPI: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_kpi_seed()
