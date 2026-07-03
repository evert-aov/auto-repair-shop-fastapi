import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.incidents.models import Incident, WorkshopOffer
from app.notifications.models import Notification, NotificationType
from app.notifications.repositories.notification_repository import NotificationRepository
from app.workshops.models import Workshop

logger = logging.getLogger(__name__)


# =====================================================================
# CONFIGURACIÓN FCM (Firebase Cloud Messaging)
# =====================================================================

class FCMService:
    """
    Wrapper para Firebase Cloud Messaging usando firebase-admin SDK.
    Se inicializa automáticamente si FIREBASE_SERVICE_ACCOUNT_KEY está en el .env.
    """
    _initialized = False

    def __init__(self):
        if not FCMService._initialized:
            import os
            import firebase_admin
            from firebase_admin import credentials

            if firebase_admin._apps:
                FCMService._initialized = True
                return

            key_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
            if key_path and os.path.exists(key_path):
                try:
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(cred)
                    FCMService._initialized = True
                    logger.info(f"✅ Firebase Admin SDK inicializado vía archivo: {key_path}")
                    return
                except Exception as e:
                    logger.error(f"❌ Error al inicializar Firebase con archivo: {e}")

            try:
                firebase_admin.initialize_app()
                FCMService._initialized = True
                logger.info("✅ Firebase Admin SDK inicializado vía ADC (Cloud Run)")
                return
            except Exception as e:
                logger.warning(f"⚠️ No se pudo inicializar Firebase vía ADC ni archivo. Notificaciones deshabilitadas ({e}).")

    async def send_to_user(
            self,
            user_id: uuid.UUID,
            title: str,
            body: str,
            data: dict = None,
            priority: str = "normal",
            db=None,
    ) -> bool:
        try:
            fcm_token = None
            if db is not None:
                from app.users.models import User
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    fcm_token = user.fcm_token

            if not fcm_token:
                logger.info(f"[FCM] User {user_id} no tiene token FCM registrado — solo guardado en BD")
                return True

            if not FCMService._initialized:
                logger.warning(f"[FCM] SDK no inicializado — simulando envío a user {user_id}: {title}")
                return True

            import firebase_admin
            from firebase_admin import messaging

            str_data = {k: str(v) for k, v in (data or {}).items()}

            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=str_data,
                token=fcm_token,
                android=messaging.AndroidConfig(
                    priority="high" if priority == "high" else "normal",
                    notification=messaging.AndroidNotification(
                        icon="ic_notification",
                        color="#6366F1",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            alert=messaging.ApsAlert(title=title, body=body),
                            sound="default",
                        )
                    )
                ),
            )

            response = messaging.send(message)
            logger.info(f"✅ [FCM] Push enviado a user {user_id}: {title} → message_id={response}")
            return True

        except Exception as e:
            logger.error(f"❌ [FCM] Error enviando push a user {user_id}: {e}")
            return False


fcm_service = FCMService()


# =====================================================================
# SERVICIO DE NOTIFICACIONES
# =====================================================================

class NotificationService:
    """
    Maneja la creación y envío de notificaciones
    Guarda en BD y envía push vía FCM
    """

    def __init__(self, db: Session):
        self.db = db
        self.notification_repository = NotificationRepository(db)

    async def _send_notification(
            self,
            user_id: uuid.UUID,
            notification_type: NotificationType,
            title: str,
            body: str,
            incident_id: Optional[uuid.UUID] = None,
            priority: str = "normal"
    ) -> Notification:
        # Persistir SIEMPRE en BD para que aparezca en la campana/listado in-app,
        # no solo las de tipo SERVICE_COMPLETED. El push vía FCM es adicional.
        notification = Notification(
            user_id=user_id,
            incident_id=incident_id,
            type=notification_type,
            title=title,
            body=body,
            is_read=False,
            sent_at=datetime.now(timezone.utc),
        )
        notification = self.notification_repository.save(notification)

        data = {
            "notification_id": str(notification.id) if notification else str(uuid.uuid4()),
            "incident_id": str(incident_id) if incident_id else "",
            "type": notification_type.value,
        }

        from app.users.models import User
        target_user = self.db.query(User).filter(User.id == user_id).first()
        target_name = target_user.username if target_user else str(user_id)

        logger.warning(f"📣 ENVIANDO PUSH a '{target_name}' (ID: {user_id}): {title}")

        success = await fcm_service.send_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
            priority=priority,
            db=self.db,
        )

        if success:
            logger.info(f"✅ Notificación física enviada con éxito a '{target_name}'")
        else:
            logger.warning(f"⚠️ El envío físico falló para '{target_name}', pero la notificación quedó guardada en la campana (web).")

        return notification

    async def notify_workshop_new_offer(
            self,
            workshop: Workshop,
            incident: Incident,
            offer: WorkshopOffer
    ) -> Notification:
        priority_emoji = {
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "CRITICAL": "🔴"
        }

        emoji = priority_emoji.get(
            incident.ai_priority.value if incident.ai_priority else "MEDIUM",
            "🟡"
        )

        title = f"{emoji} Nueva solicitud de auxilio"

        # Obtener el nombre del cliente
        from app.users.models import User, Role
        client_user = self.db.query(User).filter(User.id == incident.client_id).first()
        client_name = f"{client_user.name} {client_user.last_name}" if client_user else "Cliente desconocido"

        # Cuerpo original de la notificación
        body_content = (
            f"{incident.ai_category or 'Problema mecánico'} - "
            f"Prioridad {incident.ai_priority.value if incident.ai_priority else 'MEDIUM'}"
        )

        if incident.ai_summary:
            body_content += f"\n{incident.ai_summary[:80]}..."

        if offer.distance_km:
            body_content += f"\nDistancia: {offer.distance_km:.1f} km"

        # Anteponemos el taller y cliente al principio del mensaje
        body = f"Taller: {workshop.name} | Cliente: {client_name}\n\n{body_content}"

        # Enviar copia a todos los administradores
        try:
            admins = self.db.query(User).join(User.roles).filter(Role.name == "admin").all()
            for admin in admins:
                if admin.id != workshop.owner_user_id:
                    await self._send_notification(
                        user_id=admin.id,
                        notification_type=NotificationType.NEW_REQUEST,
                        title=f"[Admin Copy] {title}",
                        body=body,
                        incident_id=incident.id,
                        priority="high",
                    )
        except Exception as admin_exc:
            logger.error(f"Error enviando copia de notificación a administradores: {admin_exc}")

        return await self._send_notification(
            user_id=workshop.owner_user_id,
            notification_type=NotificationType.NEW_REQUEST,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high",
        )

    async def notify_workshop_offer_expired(
            self,
            workshop: Workshop,
            incident: Incident
    ) -> Notification:
        title = "Solicitud ya asignada"
        body = f"Otro taller aceptó la solicitud #{str(incident.id)[:8]}"

        return await self._send_notification(
            user_id=workshop.owner_user_id,
            notification_type=NotificationType.STATUS_UPDATE,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="normal",
        )

    async def notify_client_incident_created(
            self,
            client_id: uuid.UUID,
            incident: Incident
    ) -> Notification:
        title = "Solicitud recibida"
        body = f"Tu solicitud de auxilio #{str(incident.id)[:8]} está siendo procesada"

        return await self._send_notification(
            user_id=client_id,
            notification_type=NotificationType.STATUS_UPDATE,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="normal"
        )

    async def notify_client_payment_pending(
            self,
            incident: Incident
    ) -> Notification:
        title = "Pago pendiente"

        monto = f" de BOB {incident.total_cost:.2f}" if incident.total_cost else ""
        body = (
            f"Tienes un pago pendiente{monto} por el servicio "
            f"#{str(incident.id)[:8]}. Realiza el pago para poder solicitar otro auxilio."
        )

        return await self._send_notification(
            user_id=incident.client_id,
            notification_type=NotificationType.PAYMENT,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high"
        )

    async def notify_client_offer_accepted(
            self,
            incident: Incident,
            workshop: Workshop,
            estimated_arrival_min: int
    ) -> Notification:
        title = f"✅ {workshop.name} aceptó tu solicitud"

        body = f"Tiempo estimado de llegada: {estimated_arrival_min} min"

        if workshop.rating_avg > 0:
            body += f"\nCalificación: {workshop.rating_avg:.1f}⭐"

        return await self._send_notification(
            user_id=incident.client_id,
            notification_type=NotificationType.ACCEPTED,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high"
        )

    async def notify_client_offer_rejected(
            self,
            incident: Incident,
            workshop: Workshop,
            reason: Optional[str] = None
    ) -> Notification:
        title = "Buscando otro taller..."

        body = f"{workshop.name} no está disponible en este momento."

        if reason and reason != "no_reason_provided":
            reason_map = {
                "busy": "Ocupado con otro servicio",
                "far_from_zone": "Fuera de zona de cobertura",
                "no_parts": "Sin repuestos disponibles",
                "no_technician": "Sin técnico disponible"
            }
            body += f" Motivo: {reason_map.get(reason, reason)}"

        body += " Intentando con otro taller..."

        return await self._send_notification(
            user_id=incident.client_id,
            notification_type=NotificationType.REJECTED,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="normal"
        )

    async def notify_client_needs_more_info(
            self,
            incident: Incident
    ) -> Notification:
        title = "Necesitamos más detalles"

        body = (
            "Por favor, agrega más información sobre el problema: "
            "una foto clara, audio describiendo qué pasó, o más detalles escritos."
        )

        return await self._send_notification(
            user_id=incident.client_id,
            notification_type=NotificationType.STATUS_UPDATE,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high"
        )

    async def notify_client_no_workshops(
            self,
            incident: Incident
    ) -> Notification:
        title = "No hay talleres disponibles"

        body = (
            "Lo sentimos, no encontramos talleres disponibles en tu zona "
            "en este momento. Intenta de nuevo en unos minutos o contacta "
            "a soporte."
        )

        return await self._send_notification(
            user_id=incident.client_id,
            notification_type=NotificationType.SYSTEM,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high"
        )

    async def notify_client_technician_on_way(
            self,
            incident: Incident,
            workshop: Workshop,
            technician_name: str
    ) -> Notification:
        title = f"🚗 {technician_name} está en camino"

        body = f"Taller: {workshop.name}"

        if incident.estimated_arrival_min:
            body += f"\nLlegada estimada: {incident.estimated_arrival_min} min"

        return await self._send_notification(
            user_id=incident.client_id,
            notification_type=NotificationType.STATUS_UPDATE,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high"
        )

    async def notify_technician_assigned(
            self,
            technician_id: uuid.UUID,
            incident: Incident,
            workshop: Workshop
    ) -> Notification:
        title = "🚗 Nuevo servicio asignado"
        body = (
            f"Se te ha asignado un nuevo servicio de auxilio mecánico.\n"
            f"Categoría: {incident.ai_category or 'Problema mecánico'}.\n"
            f"Taller: {workshop.name}"
        )

        return await self._send_notification(
            user_id=technician_id,
            notification_type=NotificationType.NEW_REQUEST,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high",
        )

    async def notify_workshop_incident_cancelled(
            self,
            workshop_owner_id: uuid.UUID,
            incident: Incident
    ) -> Notification:
        title = "❌ Solicitud cancelada por el cliente"
        body = f"La solicitud de auxilio #{str(incident.id)[:8]} ha sido cancelada por el cliente."

        return await self._send_notification(
            user_id=workshop_owner_id,
            notification_type=NotificationType.STATUS_UPDATE,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high",
        )

    async def notify_technician_incident_cancelled(
            self,
            technician_id: uuid.UUID,
            incident: Incident
    ) -> Notification:
        title = "❌ Servicio cancelado por el cliente"
        body = f"El servicio asignado #{str(incident.id)[:8]} ha sido cancelada por el cliente."

        return await self._send_notification(
            user_id=technician_id,
            notification_type=NotificationType.STATUS_UPDATE,
            title=title,
            body=body,
            incident_id=incident.id,
            priority="high",
        )
