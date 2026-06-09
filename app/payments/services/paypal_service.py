import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_SANDBOX_URL = "https://api-m.sandbox.paypal.com"
_LIVE_URL = "https://api-m.paypal.com"

RETURN_URL = "https://auxilio-mecanico.app/payment/success"
CANCEL_URL = "https://auxilio-mecanico.app/payment/cancel"


class PaypalService:

    @staticmethod
    def _base_url() -> str:
        return _SANDBOX_URL if os.getenv("PAYPAL_MODE", "sandbox") == "sandbox" else _LIVE_URL

    @staticmethod
    def _credentials() -> tuple[str, str]:
        client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        secret = os.getenv("PAYPAL_SECRET", "")
        return client_id, secret

    @classmethod
    async def get_access_token(cls) -> str:
        client_id, secret = cls._credentials()
        token = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{cls._base_url()}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data="grant_type=client_credentials",
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    @classmethod
    async def create_order(cls, amount_usd: float, incident_id: str) -> dict:
        """
        Crea una orden PayPal. Devuelve {order_id, approve_url}.
        amount_usd: monto en USD (en sandbox se usa el mismo número que el BOB del incidente).
        """
        access_token = await cls.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{cls._base_url()}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [
                        {
                            "reference_id": incident_id,
                            "description": f"Servicio de Auxilio Mecánico #{incident_id[:8]}",
                            "amount": {
                                "currency_code": "USD",
                                "value": f"{amount_usd:.2f}",
                            },
                        }
                    ],
                    "application_context": {
                        "brand_name": "Auxilio Mecánico",
                        "landing_page": "LOGIN",
                        "user_action": "PAY_NOW",
                        "return_url": RETURN_URL,
                        "cancel_url": CANCEL_URL,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        order_id = data["id"]
        approve_url = next(
            (link["href"] for link in data["links"] if link["rel"] == "approve"), None
        )
        if not approve_url:
            raise ValueError("PayPal no devolvió URL de aprobación")

        logger.info(f"[PayPal] Orden creada: {order_id} — {amount_usd:.2f} USD")
        return {"order_id": order_id, "approve_url": approve_url}

    @classmethod
    async def send_payout(
        cls,
        workshop_email: str,
        net_amount: float,
        currency: str,
        payment_id: str,
        incident_id: str,
    ) -> dict:
        """
        Envía el monto neto al taller via PayPal Payouts API.
        La plataforma retiene la comisión; el taller recibe net_amount.
        """
        access_token = await cls.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{cls._base_url()}/v1/payments/payouts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "sender_batch_header": {
                        "sender_batch_id": f"payout_{payment_id}",
                        "email_subject": "Pago por servicio de Auxilio Mecánico",
                        "email_message": (
                            f"Has recibido el pago correspondiente al servicio "
                            f"#{incident_id[:8].upper()}. ¡Gracias por usar Auxilio Mecánico!"
                        ),
                    },
                    "items": [
                        {
                            "recipient_type": "EMAIL",
                            "amount": {"value": f"{net_amount:.2f}", "currency": currency},
                            "note": f"Servicio #{incident_id[:8].upper()} — monto neto descontada comisión de plataforma",
                            "sender_item_id": f"item_{payment_id}",
                            "receiver": workshop_email,
                        }
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        batch_id = data["batch_header"]["payout_batch_id"]
        batch_status = data["batch_header"]["batch_status"]
        logger.info(
            f"[PayPal Payout] {net_amount:.2f} {currency} → {workshop_email} "
            f"| batch: {batch_id} | status: {batch_status}"
        )
        return {"payout_id": batch_id, "payout_status": batch_status}

    @classmethod
    async def capture_order(cls, order_id: str) -> dict:
        """
        Captura el pago de una orden aprobada. Devuelve los detalles de la captura.
        """
        access_token = await cls.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{cls._base_url()}/v2/checkout/orders/{order_id}/capture",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        capture = data["purchase_units"][0]["payments"]["captures"][0]
        logger.info(f"[PayPal] Captura exitosa: {capture['id']} — {capture['amount']['value']} {capture['amount']['currency_code']}")
        return {
            "capture_id": capture["id"],
            "status": capture["status"],
            "amount": float(capture["amount"]["value"]),
            "currency": capture["amount"]["currency_code"],
        }
