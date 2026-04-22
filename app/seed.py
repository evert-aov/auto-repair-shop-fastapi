"""
Seed inicial: crea permisos, roles (con permisos asignados) y un usuario admin.

Ejecutar:
    python -m app.seed
"""
import bcrypt
import uuid
from sqlalchemy.orm import Session

from app.database import SessionLocal, Base, engine
from app.module_users.models.models import Permission, Role, User
from app.security.models.models import Client, Vehicle, TransmissionType, FuelType
from app.module_workshops.models.models import Workshop, Technician, Specialty, WorkshopSpecialty
from app.module_incidents.models.models import Notification, Incident, IncidentEvidence, WorkshopOffer, Payment, Rating


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ── Permisos ─────────────────────────────────────────────────────────────────

PERMISSIONS = [
    # Usuarios
    {"name": "Crear usuarios",      "action": "users:create",      "description": "Permite crear usuarios"},
    {"name": "Ver usuarios",        "action": "users:read",        "description": "Permite ver usuarios"},
    {"name": "Editar usuarios",     "action": "users:update",      "description": "Permite editar usuarios"},
    {"name": "Eliminar usuarios",   "action": "users:delete",      "description": "Permite eliminar usuarios"},
    # Roles
    {"name": "Crear roles",         "action": "roles:create",      "description": "Permite crear roles"},
    {"name": "Ver roles",           "action": "roles:read",        "description": "Permite ver roles"},
    {"name": "Editar roles",        "action": "roles:update",      "description": "Permite editar roles"},
    {"name": "Eliminar roles",      "action": "roles:delete",      "description": "Permite eliminar roles"},
    # Permisos
    {"name": "Crear permisos",      "action": "permissions:create", "description": "Permite crear permisos"},
    {"name": "Ver permisos",        "action": "permissions:read",   "description": "Permite ver permisos"},
    {"name": "Editar permisos",     "action": "permissions:update", "description": "Permite editar permisos"},
    {"name": "Eliminar permisos",   "action": "permissions:delete", "description": "Permite eliminar permisos"},
    # Talleres
    {"name": "Crear talleres",      "action": "workshops:create",  "description": "Permite crear talleres"},
    {"name": "Ver talleres",        "action": "workshops:read",    "description": "Permite ver talleres"},
    {"name": "Editar talleres",     "action": "workshops:update",  "description": "Permite editar talleres"},
    {"name": "Eliminar talleres",   "action": "workshops:delete",  "description": "Permite eliminar talleres"},
    # Vehículos
    {"name": "Crear vehículos",     "action": "vehicles:create",   "description": "Permite crear vehículos"},
    {"name": "Ver vehículos",       "action": "vehicles:read",     "description": "Permite ver vehículos"},
    {"name": "Editar vehículos",    "action": "vehicles:update",   "description": "Permite editar vehículos"},
    {"name": "Eliminar vehículos",  "action": "vehicles:delete",   "description": "Permite eliminar vehículos"},
    # Incidentes
    {"name": "Crear incidentes",    "action": "incidents:create",  "description": "Permite crear incidentes"},
    {"name": "Ver incidentes",      "action": "incidents:read",    "description": "Permite ver incidentes"},
    {"name": "Editar incidentes",   "action": "incidents:update",  "description": "Permite editar incidentes"},
    {"name": "Eliminar incidentes", "action": "incidents:delete",  "description": "Permite eliminar incidentes"},
]

# ── Roles y sus permisos (por prefijo de action) ────────────────────────────

ROLES = {
    "admin": {
        "description": "Administrador del sistema con acceso total",
        "actions": "*",  # todos los permisos
    },
    "workshop_owner": {
        "description": "Dueño de taller mecánico",
        "actions": [
            "users:read",
            "workshops:create", "workshops:read", "workshops:update",
            "vehicles:read",
            "incidents:read", "incidents:update",
        ],
    },
    "technician": {
        "description": "Técnico mecánico",
        "actions": [
            "workshops:read",
            "vehicles:read",
            "incidents:read", "incidents:update",
        ],
    },
    "client": {
        "description": "Cliente de la plataforma",
        "actions": [
            "vehicles:create", "vehicles:read", "vehicles:update", "vehicles:delete",
            "incidents:create", "incidents:read",
        ],
    },
}

# ── Usuarios por defecto ───────────────────────────────────────────────────

ADMIN_USER = {
    "username": "admin",
    "name": "Administrador",
    "last_name": "Sistema",
    "email": "admin@autorepair.com",
    "password": "admin123",
    "phone": None,
}

OWNER_USER = {
    "username": "owner",
    "name": "Taller",
    "last_name": "Dueño",
    "email": "owner@tallercentral.com",
    "password": "owner123",
    "phone": "77889900",
}

ADMIN_CLIENT_USER = {
    "username": "admin_client",
    "name": "Admin",
    "last_name": "Cliente",
    "email": "admin_client@autorepair.com",
    "password": "admin123",
    "phone": "70000001",
    "address": "Sede Central Admin",
}

ADMIN_TECH_USER = {
    "username": "admin_tech",
    "name": "Admin",
    "last_name": "Tecnico",
    "email": "admin_tech@autorepair.com",
    "password": "admin123",
    "phone": "70000002",
}

DEFAULT_SPECIALTIES = [
    {"name": "general"},
    {"name": "battery"},
    {"name": "tire"},
    {"name": "engine"},
    {"name": "ac"},
    {"name": "transmission"},
    {"name": "towing"},
    {"name": "locksmith"},
]

DEFAULT_CLIENTS = [
    {
        "username": "juanp",
        "name": "Juan",
        "last_name": "Pérez",
        "email": "juanp@gmail.com",
        "password": "client123",
        "phone": "700112233",
        "address": "Calle 1, Los Olivos",
        "vehicles": [
            {"make": "Toyota", "model": "Corolla", "year": 2020, "license_plate": "ABC-123", "color": "Blanco", "transmission_type": TransmissionType.automatic, "fuel_type": FuelType.gasoline},
            {"make": "Suzuki", "model": "Swift", "year": 2018, "license_plate": "DEF-456", "color": "Rojo", "transmission_type": TransmissionType.manual, "fuel_type": FuelType.gasoline},
        ]
    },
    {
        "username": "mariag",
        "name": "María",
        "last_name": "García",
        "email": "mariag@gmail.com",
        "password": "client123",
        "phone": "700445566",
        "address": "Av. Principal 456",
        "vehicles": [
            {"make": "Honda", "model": "Civic", "year": 2021, "license_plate": "GHI-789", "color": "Gris", "transmission_type": TransmissionType.automatic, "fuel_type": FuelType.gasoline},
            {"make": "Hyundai", "model": "Tucson", "year": 2019, "license_plate": "JKL-012", "color": "Azul", "transmission_type": TransmissionType.automatic, "fuel_type": FuelType.diesel},
        ]
    }
]


ADDITIONAL_WORKSHOPS = [
    {
        "name": "Taller Los Rápidos",
        "business_name": "Servicios Rápidos S.R.L.",
        "ruc_nit": "2233445-5",
        "address": "Calle Falsa 123",
        "phone": "33445566",
        "latitude": -17.7947,
        "longitude": -63.1333,
        "owner": {
            "username": "carlosp",
            "name": "Carlos",
            "last_name": "Pérez",
            "email": "carlosp@rapidos.com",
            "password": "password123",
            "phone": "70011122",
        },
        "technicians": [
            {
                "username": "luism",
                "name": "Luis",
                "last_name": "Morales",
                "email": "luism@rapidos.com",
                "password": "password123",
                "phone": "70033344",
            }
        ]
    },
    {
        "name": "Doctor Auto",
        "business_name": "Clínica Automotriz Dr. Auto",
        "ruc_nit": "3344556-6",
        "address": "Av. Busch #456",
        "phone": "33221100",
        "latitude": -17.7711,
        "longitude": -63.1922,
        "owner": {
            "username": "robertog",
            "name": "Roberto",
            "last_name": "Gomez",
            "email": "robertog@drauto.com",
            "password": "password123",
            "phone": "70055566",
        },
        "technicians": []
    },
    {
        "name": "Motores y Más",
        "business_name": "Motores y Más S.A.",
        "ruc_nit": "4455667-7",
        "address": "4to Anillo y Roca y Coronado",
        "phone": "33112233",
        "latitude": -17.7865,
        "longitude": -63.2100,
        "owner": {
            "username": "fernandor",
            "name": "Fernando",
            "last_name": "Rivas",
            "email": "fernandor@motores.com",
            "password": "password123",
            "phone": "70077788",
        },
        "technicians": [
            {
                "username": "jorges",
                "name": "Jorge",
                "last_name": "Soliz",
                "email": "jorges@motores.com",
                "password": "password123",
                "phone": "70099900",
            }
        ]
    }
]



def run_seed():
    # Asegurar que todas las tablas existan
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()

    try:
        # 1. Crear permisos
        perm_map: dict[str, Permission] = {}
        for p in PERMISSIONS:
            existing = db.query(Permission).filter(Permission.action == p["action"]).first()
            if existing:
                perm_map[p["action"]] = existing
                print(f"  ⏭  Permiso ya existe: {p['action']}")
            else:
                perm = Permission(**p)
                db.add(perm)
                db.flush()
                perm_map[p["action"]] = perm
                print(f"  ✅ Permiso creado: {p['action']}")

        # 2. Crear roles
        role_map: dict[str, Role] = {}
        for role_name, config in ROLES.items():
            existing = db.query(Role).filter(Role.name == role_name).first()
            if existing:
                role_map[role_name] = existing
                print(f"  ⏭  Rol ya existe: {role_name}")
            else:
                role = Role(name=role_name, description=config["description"])
                if config["actions"] == "*":
                    role.permissions = list(perm_map.values())
                else:
                    role.permissions = [perm_map[a] for a in config["actions"]]
                db.add(role)
                db.flush()
                role_map[role_name] = role
                print(f"  ✅ Rol creado: {role_name} ({len(role.permissions)} permisos)")

        # 3. Crear usuario admin básico
        existing_admin = db.query(User).filter(User.username == ADMIN_USER["username"]).first()
        if existing_admin:
            print(f"  ⏭  Usuario admin ya existe: {ADMIN_USER['username']}")
        else:
            admin = User(
                username=ADMIN_USER["username"],
                name=ADMIN_USER["name"],
                last_name=ADMIN_USER["last_name"],
                email=ADMIN_USER["email"],
                password=_hash(ADMIN_USER["password"]),
                phone=ADMIN_USER["phone"],
                type="user",
            )
            admin.roles = [role_map["admin"]]
            db.add(admin)
            print(f"  ✅ Usuario admin creado: {ADMIN_USER['username']}")

        # 4. Crear Especialidades
        for spec_data in DEFAULT_SPECIALTIES:
            existing = db.query(Specialty).filter(Specialty.name == spec_data["name"]).first()
            if not existing:
                spec = Specialty(**spec_data)
                db.add(spec)
                print(f"  ✅ Especialidad creada: {spec_data['name']}")

        # 5. Crear Taller de Prueba (Original)
        existing_workshop = db.query(Workshop).filter(Workshop.ruc_nit == "1234567-0").first()
        existing_owner = db.query(User).filter(User.username == OWNER_USER["username"]).first()

        owner_id = existing_owner.id if existing_owner else uuid.uuid4()
        workshop_id = existing_workshop.id if existing_workshop else uuid.uuid4()

        if not existing_workshop:
            workshop = Workshop(
                id=workshop_id,
                owner_user_id=owner_id,
                name="Taller Central",
                business_name="Talleres Automotrices S.A.",
                ruc_nit="1234567-0",
                address="Av. Panamericana #123",
                phone="44556677",
                latitude=-17.7833,
                longitude=-63.1821,
                is_active=True,
                is_available=True,
                is_verified=True,
                commission_rate=10.0,
            )
            db.add(workshop)
            db.flush()
            
            # Vincular todas las especialidades al taller de prueba
            all_specs = db.query(Specialty).all()
            for spec in all_specs:
                ws = WorkshopSpecialty(workshop_id=workshop.id, specialty_id=spec.id)
                db.add(ws)
            print(f"  ✅ Taller de prueba creado y vinculado a {len(all_specs)} especialidades")
        else:
            workshop = existing_workshop
            workshop_id = workshop.id

        # 6. Crear Dueño de Taller (Technician) Central
        if existing_owner:
            print(f"  ⏭  Usuario dueño ya existe: {OWNER_USER['username']}")
        else:
            owner = Technician(
                id=owner_id,
                username=OWNER_USER["username"],
                name=OWNER_USER["name"],
                last_name=OWNER_USER["last_name"],
                email=OWNER_USER["email"],
                password=_hash(OWNER_USER["password"]),
                phone=OWNER_USER["phone"],
                type="technician",
                workshop_id=workshop_id,
                is_active=True,
                is_available=True,
            )
            owner.roles = [role_map["workshop_owner"], role_map["technician"]]
            db.add(owner)
            print(f"  ✅ Usuario dueño creado: {OWNER_USER['username']}")

        # 6.1 Crear Talleres y Técnicos Adicionales
        for w_data in ADDITIONAL_WORKSHOPS:
            owner_data = w_data.pop("owner")
            techs_data = w_data.pop("technicians")
            
            existing_w = db.query(Workshop).filter(Workshop.ruc_nit == w_data["ruc_nit"]).first()
            if not existing_w:
                # Primero crear al dueño como técnico si no existe
                existing_o = db.query(User).filter(User.username == owner_data["username"]).first()
                o_id = existing_o.id if existing_o else uuid.uuid4()
                w_id = uuid.uuid4()
                
                workshop = Workshop(id=w_id, owner_user_id=o_id, rating_avg=5.0, **w_data)
                db.add(workshop)
                db.flush()
                
                # Vincular especialidades
                all_specs = db.query(Specialty).all()
                for spec in all_specs:
                    ws = WorkshopSpecialty(workshop_id=workshop.id, specialty_id=spec.id)
                    db.add(ws)
                
                if not existing_o:
                    owner = Technician(
                        id=o_id,
                        username=owner_data["username"],
                        name=owner_data["name"],
                        last_name=owner_data["last_name"],
                        email=owner_data["email"],
                        password=_hash(owner_data["password"]),
                        phone=owner_data["phone"],
                        type="technician",
                        workshop_id=w_id,
                        is_active=True,
                        is_available=True,
                    )
                    owner.roles = [role_map["workshop_owner"], role_map["technician"]]
                    db.add(owner)
                
                print(f"  ✅ Taller adicional creado: {w_data['name']} (Dueño: {owner_data['username']})")
                
                # Crear técnicos adicionales
                for t_data in techs_data:
                    existing_t = db.query(User).filter(User.username == t_data["username"]).first()
                    if not existing_t:
                        tech = Technician(
                            username=t_data["username"],
                            name=t_data["name"],
                            last_name=t_data["last_name"],
                            email=t_data["email"],
                            password=_hash(t_data["password"]),
                            phone=t_data["phone"],
                            type="technician",
                            workshop_id=w_id,
                            is_active=True,
                            is_available=True,
                        )
                        tech.roles = [role_map["technician"]]
                        db.add(tech)
                        print(f"      🔧 Técnico creado: {t_data['username']}")
            else:
                print(f"  ⏭  Taller ya existe: {w_data['name']}")

        # 7. Crear Clientes y sus Vehículos
        for c_data in DEFAULT_CLIENTS:
            vehicles_data = c_data.pop("vehicles", [])
            password_plain = c_data.pop("password", "client123")
            
            existing_client = db.query(Client).filter(Client.username == c_data["username"]).first()
            if existing_client:
                client = existing_client
                print(f"  ⏭  Cliente ya existe: {c_data['username']}")
            else:
                client = Client(
                    **c_data,
                    password=_hash(password_plain),
                    type="client"
                )
                client.roles = [role_map["client"]]
                db.add(client)
                db.flush()
                print(f"  ✅ Cliente creado: {c_data['username']}")
                
            for v_data in vehicles_data:
                existing_v = db.query(Vehicle).filter(Vehicle.license_plate == v_data["license_plate"]).first()
                if not existing_v:
                    vehicle = Vehicle(**v_data, client_id=client.id)
                    db.add(vehicle)
                    print(f"      🚗 Vehículo creado: {v_data['license_plate']}")

        # 8. Crear Admin-Cliente (Híbrido)
        existing_admin_client = db.query(Client).filter(Client.username == ADMIN_CLIENT_USER["username"]).first()
        if not existing_admin_client:
            admin_client = Client(
                username=ADMIN_CLIENT_USER["username"],
                name=ADMIN_CLIENT_USER["name"],
                last_name=ADMIN_CLIENT_USER["last_name"],
                email=ADMIN_CLIENT_USER["email"],
                password=_hash(ADMIN_CLIENT_USER["password"]),
                phone=ADMIN_CLIENT_USER["phone"],
                address=ADMIN_CLIENT_USER["address"],
                type="client"
            )
            admin_client.roles = [role_map["admin"], role_map["client"]]
            db.add(admin_client)
            db.flush()
            
            v_admin = Vehicle(
                client_id=admin_client.id,
                make="Porsche",
                model="Taycan",
                year=2023,
                license_plate="ADM-999",
                color="Dorado",
                transmission_type=TransmissionType.automatic,
                fuel_type=FuelType.electric
            )
            db.add(v_admin)
            print(f"  ✅ Admin-Cliente creado con vehículo ADM-999")

        # 9. Crear Admin-Tecnico (Híbrido)
        existing_admin_tech = db.query(Technician).filter(Technician.username == ADMIN_TECH_USER["username"]).first()
        if not existing_admin_tech:
            admin_tech = Technician(
                username=ADMIN_TECH_USER["username"],
                name=ADMIN_TECH_USER["name"],
                last_name=ADMIN_TECH_USER["last_name"],
                email=ADMIN_TECH_USER["email"],
                password=_hash(ADMIN_TECH_USER["password"]),
                phone=ADMIN_TECH_USER["phone"],
                workshop_id=workshop_id,
                type="technician"
            )
            admin_tech.roles = [role_map["admin"], role_map["technician"]]
            db.add(admin_tech)
            print(f"  ✅ Admin-Tecnico creado: {ADMIN_TECH_USER['username']}")

        db.commit()
        print("\n🎉 Seed híbrido completado exitosamente!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error en el seed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
