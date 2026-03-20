"""
Email notification service for alerts and daily reports.
"""
import logging
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_email(subject: str, html_body: str) -> bool:
    """Send an email notification."""
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP not configured, skipping email")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_user
    msg["To"] = settings.notification_email or settings.admin_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=True,
            username=settings.smtp_user,
            password=settings.smtp_password,
        )
        logger.info(f"Email sent: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def build_opportunities_html(opportunities: list) -> str:
    """Build HTML email body for daily opportunities report."""
    today = date.today().strftime("%d/%m/%Y")

    rows = ""
    for opp in opportunities:
        color = "#22c55e" if opp["score"] >= 70 else "#eab308" if opp["score"] >= 60 else "#6b7280"
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #333;color:white;font-weight:bold">{opp['ticker']}</td>
            <td style="padding:8px;border-bottom:1px solid #333;color:{color};font-weight:bold;text-align:right">{opp['score']:.1f}</td>
            <td style="padding:8px;border-bottom:1px solid #333;color:#9ca3af;text-align:center">{opp['signal'].upper()}</td>
            <td style="padding:8px;border-bottom:1px solid #333;color:#9ca3af;text-align:right">{opp['confidence']:.0f}%</td>
        </tr>
        """

    return f"""
    <div style="font-family:system-ui;background:#0b0e14;padding:20px;color:#e0e0e0">
        <h2 style="color:white;margin-bottom:4px">MiPortafolio — Oportunidades del Día</h2>
        <p style="color:#6b7280;margin-top:0">{today} — {len(opportunities)} activos con score &ge; umbral</p>

        <table style="width:100%;border-collapse:collapse;background:#111827;border-radius:8px;overflow:hidden">
            <thead>
                <tr style="background:#1f2937">
                    <th style="padding:10px;text-align:left;color:#9ca3af;font-size:12px">Ticker</th>
                    <th style="padding:10px;text-align:right;color:#9ca3af;font-size:12px">Score</th>
                    <th style="padding:10px;text-align:center;color:#9ca3af;font-size:12px">Señal</th>
                    <th style="padding:10px;text-align:right;color:#9ca3af;font-size:12px">Confianza</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>

        <p style="color:#4b5563;font-size:12px;margin-top:16px">
            Generado automáticamente por MiPortafolio — Análisis Cuantitativo
        </p>
    </div>
    """
