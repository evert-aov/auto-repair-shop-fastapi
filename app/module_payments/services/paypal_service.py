import base64
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_SANDBOX_URL = "https://api-m.sandbox.paypal.com"
_LIVE_URL = "https://api-m.paypal.com"

RETURN_URL = "https://auxilio-mecanico.app/payment/success"
CANCEL_URL = "https://auxilio-mecanico.app/payment/cancel"


def _base_url() -> str:
    return _SANDBOX_URL if os.getenv("PAYPAL_MODE", "sandbox") == "sandbox" else _LIVE_URL


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("PAYPAL_CLIENT_ID", "")
    secret = os.getenv("PAYPAL_SECRET", "")
    return client_id, secret


async def get_access_token() -> str:
    client_id, secret = _credentials()
    token = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials",
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def create_order(amount_usd: float, incident_id: str) -> dict:
    """
    Crea una orden PayPal. Devuelve {order_id, approve_url}.
    amount_usd: monto en USD (en sandbox se usa el mismo número que el BOB del incidente).
    """
    access_token = await get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/v2/checkout/orders",
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


async def capture_order(order_id: str) -> dict:
    """
    Captura el pago de una orden aprobada. Devuelve los detalles de la captura.
    """
    access_token = await get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/v2/checkout/orders/{order_id}/capture",
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
