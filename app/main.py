from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.module_users.controller.user_controller import router as users_router
from app.security.controller.auth_controller import router as auth_router
from app.module_users.controller.role_controller import router as role_route
from app.module_users.controller.permission_controller import router as permission_route
from app.module_clients.controller.client_controller import router as client_route
from app.module_clients.controller.vehicle_controller import router as vehicle_route

app = FastAPI(
    title="Plataforma de Auxilio Mecánico",
    version="1.0.0",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, usa una lista de dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(role_route)
app.include_router(permission_route)
app.include_router(client_route)
app.include_router(vehicle_route)