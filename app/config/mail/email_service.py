import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio de envío de correos electrónicos.
    Port directo de EmailService.java (main-si2) usando smtplib stdlib."""

    def __init__(self):
        self._host = os.getenv("SMTP_HOST", "")
        self._port = int(os.getenv("SMTP_PORT", "587"))
        self._username = os.getenv("SMTP_USERNAME", "")
        self._password = os.getenv("SMTP_PASSWORD", "")
        self._from = os.getenv("SMTP_FROM", "restobar_lagaira@googlegroups.com")
        self._group_copy = os.getenv("SMTP_GROUP_COPY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._host and self._username and self._password)

    def send_verification_code(self, to: str, username: str, code: str) -> bool:
        subject = "Código de verificación - Auto Repair"
        content = (
            "<div style='font-family: Arial, sans-serif; max-width: 600px; margin: auto; "
            "border: 1px solid #eee; padding: 20px;'>"
            "<h2 style='color: #0056b3;'>Verificación de Correo Electrónico</h2>"
            f"<p>Hola <strong>{username}</strong>,</p>"
            "<p>Has solicitado verificar tu correo en nuestro sistema. "
            "Utiliza el siguiente código para confirmar tu identidad:</p>"
            "<div style='background-color: #f9f9f9; padding: 15px; text-align: center; "
            "font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #333; "
            "margin: 20px 0; border-radius: 8px;'>"
            f"{code}"
            "</div>"
            "<p>Este código vencerá en 10 minutos.</p>"
            "<p>Si no has solicitado este código, puedes ignorar este correo.</p>"
            "<br><p>Atentamente,<br><strong>Equipo de Auto Repair</strong></p>"
            "</div>"
        )
        return self._send_email(to, subject, content)

    def send_new_password(self, to: str, username: str, new_password: str) -> bool:
        subject = "Tus credenciales de acceso - Auto Repair"
        content = (
            "<div style='font-family: Arial, sans-serif; max-width: 600px; margin: auto; "
            "border: 1px solid #eee; padding: 20px;'>"
            "<h2 style='color: #0056b3;'>Credenciales de Acceso</h2>"
            "<p>Hola,</p>"
            "<p>Tu cuenta ha sido creada exitosamente. A continuación tus credenciales de acceso:</p>"
            f"<p><strong>Usuario:</strong> {username}</p>"
            "<p>Tu contraseña de acceso es:</p>"
            "<div style='background-color: #f9f9f9; padding: 15px; text-align: center; "
            "font-size: 20px; font-weight: bold; color: #0056b3; "
            "margin: 20px 0; border-radius: 8px;'>"
            f"{new_password}"
            "</div>"
            "<p>Te recomendamos cambiar esta contraseña la próxima vez que inicies sesión.</p>"
            "<br><p>Atentamente,<br><strong>Equipo de Auto Repair</strong></p>"
            "</div>"
        )
        return self._send_email(to, subject, content)

    def _send_email(self, to: str, subject: str, content: str) -> bool:
        logger.info("Iniciando proceso de envío de email a %s...", to)

        if not self.is_configured:
            logger.warning(
                "SMTP no está configurado. No se puede enviar correo. "
                "Revise las variables SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD en .env"
            )
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self._from
            msg["To"] = to
            msg["Subject"] = subject

            if self._group_copy:
                msg["Bcc"] = self._group_copy

            msg.attach(MIMEText(content, "html", "utf-8"))

            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls()
                server.login(self._username, self._password)
                server.send_message(msg)

            logger.info("Email enviado exitosamente a %s", to)
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "Autenticación SMTP fallida al enviar a %s. "
                "Verifique SMTP_USERNAME/SMTP_PASSWORD.", to
            )
            return False
        except smtplib.SMTPException as e:
            logger.error("Fallo SMTP al enviar email a %s: %s", to, e)
            return False
        except Exception as e:
            logger.error("Error inesperado al enviar email a %s: %s", to, e)
            return False


email_service = EmailService()
