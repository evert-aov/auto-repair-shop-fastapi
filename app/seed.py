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
from app.module_workshops.models.models import Workshop, Technician, Specialty


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

# ── Usuario admin por defecto ────────────────────────────────────────────────

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


def run_seed():
    # Asegurar que todas las tablas existan (incluyendo las nuevas de workshops)
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

        # 2. Crear roles y asignar permisos
        role_map: dict[str, Role] = {}
        for role_name, config in ROLES.items():
            existing = db.query(Role).filter(Role.name == role_name).first()
            if existing:
                role_map[role_name] = existing
                print(f"  ⏭  Rol ya existe: {role_name}")
            else:
                role = Role(name=role_name, description=config["description"])

                # Asignar permisos
                if config["actions"] == "*":
                    role.permissions = list(perm_map.values())
                else:
                    role.permissions = [perm_map[a] for a in config["actions"]]

                db.add(role)
                db.flush()
                role_map[role_name] = role
                print(f"  ✅ Rol creado: {role_name} ({len(role.permissions)} permisos)")

        # 3. Crear usuario admin
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
            print(f"  ✅ Usuario admin creado: {ADMIN_USER['username']} / {ADMIN_USER['password']}")

        # 4. Crear Especialidades por defecto
        for spec_data in DEFAULT_SPECIALTIES:
            existing = db.query(Specialty).filter(Specialty.name == spec_data["name"]).first()
            if not existing:
                spec = Specialty(**spec_data)
                db.add(spec)
                print(f"  ✅ Especialidad creada: {spec_data['name']}")

        # 5. Crear un taller de prueba si no existe
        existing_workshop = db.query(Workshop).filter(Workshop.ruc_nit == "1234567-0").first()
        existing_owner = db.query(User).filter(User.username == OWNER_USER["username"]).first()

        if existing_owner:
            owner = existing_owner
            owner_id = owner.id
        elif existing_workshop:
            owner = None
            owner_id = existing_workshop.owner_user_id
        else:
            owner = None
            owner_id = uuid.uuid4()

        if not existing_workshop:
            workshop_id = uuid.uuid4()
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
                rating_avg=0.0,
                total_services=0,
            )
            db.add(workshop)
            print(f"  ✅ Taller de prueba creado: {workshop.name}")
        else:
            workshop = existing_workshop
            workshop_id = workshop.id
            workshop.owner_user_id = owner_id

        # 6. Crear dueño del taller (Technician)
        if owner:
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
                type="technician", # Importante: el tipo debe coincidir con el rol/modelo
                workshop_id=workshop_id,
                is_active=True,
                is_available=True,
            )
            owner.roles = [role_map["workshop_owner"], role_map["technician"]]
            db.add(owner)
            print(f"  ✅ Usuario dueño creado: {OWNER_USER['username']} / {OWNER_USER['password']}")

        if hasattr(owner, "workshop_id"):
            owner.workshop_id = workshop_id

        db.commit()
        print("\n🎉 Seed completado exitosamente!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error en el seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
