from __future__ import annotations
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_report_email(
    to_email: str,
    subject: str,
    body: str,
    pdf_path: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
):
    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    pdf_bytes = Path(pdf_path).read_bytes()
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=Path(pdf_path).name,
    )

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
