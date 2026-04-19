# app/module_incidents/services/notification_service.py
"""
Servicio de notificaciones push usando Firebase Cloud Messaging (FCM)
Integra con la tabla 'notifications' y envía push a dispositivos móviles
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.module_incidents.models import (
    Incident,
    Notification,
    NotificationType,
    WorkshopOffer,
)
from app.module_incidents.repositories import notification_repository
from app.module_workshops.models import Workshop

logger = logging.getLogger(__name__)


# =====================================================================
# CONFIGURACIÓN FCM (Firebase Cloud Messaging)
# =====================================================================

class FCMService:
    """
    Wrapper para Firebase Cloud Messaging
    En producción, inicializar con credenciales de Firebase Admin SDK
    """

    def __init__(self):
        # TODO: Inicializar Firebase Admin SDK
        # import firebase_admin
        # from firebase_admin import credentials, messaging
        # cred = credentials.Certificate("path/to/serviceAccountKey.json")
        # firebase_admin.initialize_app(cred)
        pass

    async def send_to_user(
            self,
            user_id: uuid.UUID,
            title: str,
            body: str,
            data: dict = None,
            priority: str = "normal"
    ) -> bool:
        """
        Enviar notificación push a un usuario específico

        Args:
            user_id: UUID del usuario
            title: Título de la notificación
            body: Cuerpo del mensaje
            data: Data payload adicional
            priority: "normal" | "high"

        Returns:
            True si se envió correctamente
        """

        try:
            # TODO: Implementar envío real con FCM
            # 1. Obtener FCM tokens del usuario desde BD
            # 2. Enviar mensaje usando firebase_admin.messaging.send_multicast

            logger.info(
                f"[FCM] Enviando a user {user_id}: {title} - {body}"
            )

            # Simulación (en producción reemplazar con código real)
            # from firebase_admin import messaging
            # tokens = get_user_fcm_tokens(user_id)
            # message = messaging.MulticastMessage(
            #     notification=messaging.Notification(title=title, body=body),
            #     data=data or {},
            #     tokens=tokens,
            #     android=messaging.AndroidConfig(priority=priority),
            #     apns=messaging.APNSConfig(...)
            # )
            # response = messaging.send_multicast(message)
            # return response.success_count > 0

            return True

        except Exception as e:
            logger.error(f"Error enviando FCM a user {user_id}: {e}")
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

    async def _send_notification(
            self,
            user_id: uuid.UUID,
            notification_type: NotificationType,
            title: str,
            body: str,
            incident_id: Optional[uuid.UUID] = None,
            priority: str = "normal"
    ) -> Notification:
        """
        Método base: guardar en BD + enviar FCM
        """

        # 1. Guardar en BD
        notification = Notification(
            user_id=user_id,
            incident_id=incident_id,
            type=notification_type,
            title=title,
            body=body,
            is_read=False,
            sent_at=datetime.now(timezone.utc),
        )

        notification = notification_repository.save_notification(self.db, notification)

        # 2. Enviar push vía FCM
        data = {
            "notification_id": str(notification.id),
            "incident_id": str(incident_id) if incident_id else "",
            "type": notification_type.value,
        }

        success = await fcm_service.send_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
            priority=priority
        )

        if success:
            logger.info(
                f"✅ Notificación enviada a user {user_id}: {title}"
            )
        else:
            logger.warning(
                f"⚠️ FCM falló para user {user_id}, pero guardada en BD"
            )

        return notification

    # =================================================================
    # NOTIFICACIONES A TALLERES
    # =================================================================

    async def notify_workshop_new_offer(
            self,
            workshop: Workshop,
            incident: Incident,
            offer: WorkshopOffer
    ) -> Notification:
        """
        🔔 Notificar al taller que tiene una nueva oferta
        Enviada cuando se crea la offer (CU10)
        """

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

        body = (
            f"{incident.ai_category or 'Problema mecánico'} - "
            f"Prioridad {incident.ai_priority.value if incident.ai_priority else 'MEDIUM'}"
        )

        if incident.ai_summary:
            body += f"\n{incident.ai_summary[:80]}..."

        if offer.distance_km:
            body += f"\nDistancia: {offer.distance_km:.1f} km"

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
        """
        🔔 Notificar al taller que otro taller ya aceptó
        Enviada cuando un offer pasa a "expired"
        """

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

    # =================================================================
    # NOTIFICACIONES AL CLIENTE
    # =================================================================

    async def notify_client_incident_created(
            self,
            client_id: uuid.UUID,
            incident: Incident
    ) -> Notification:
        """
        🔔 Confirmación al cliente de que su solicitud fue recibida
        """

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

    async def notify_client_offer_accepted(
            self,
            incident: Incident,
            workshop: Workshop,
            estimated_arrival_min: int
    ) -> Notification:
        """
        🔔 Notificar al cliente que un taller ACEPTÓ
        Esta es LA notificación clave para el cliente
        """

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
            priority="high"  # Alta prioridad (buena noticia)
        )

    async def notify_client_offer_rejected(
            self,
            incident: Incident,
            workshop: Workshop,
            reason: Optional[str] = None
    ) -> Notification:
        """
        🔔 Notificar al cliente que un taller rechazó
        (Opcional, puede ser molesto si rechaza el primero)
        """

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
        """
        🔔 Notificar al cliente que la IA necesita más información
        Cuando ai_confidence < 0.4
        """

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
        """
        🔔 Notificar al cliente que NO hay talleres disponibles
        """

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
        """
        🔔 Notificar al cliente que el técnico va en camino
        """

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


