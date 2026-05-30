from __future__ import annotations

import smtplib
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import Optional


class EmailNotifier:
    def __init__(
        self,
        recipient: str | None = None,
        smtp_server: str | None = None,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        smtp_sender: str | None = None,
    ):
        self.recipient = recipient
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.smtp_sender = smtp_sender

    def is_configured(self) -> bool:
        return bool(self.recipient and self.smtp_server and self.smtp_sender and self.smtp_port)

    def _build_message(
        self,
        subject: str,
        body: str,
        attachment_path: Path | None = None,
    ) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.smtp_sender or ""
        message["To"] = self.recipient or ""
        message.set_content(body)

        if attachment_path is not None and attachment_path.exists():
            attachment_data = attachment_path.read_bytes()
            message.add_attachment(
                attachment_data,
                maintype="text",
                subtype="plain",
                filename=attachment_path.name,
            )

        return message

    def send(
        self,
        subject: str,
        body: str,
        attachment_path: Path | None = None,
    ) -> None:
        if not self.is_configured():
            raise ValueError("SMTP configuration is incomplete")

        message = self._build_message(subject, body, attachment_path)

        if self.smtp_port == 465:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                if self.smtp_port != 25:
                    server.starttls()
                    server.ehlo()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)

    def send_completion(
        self,
        file_name: str,
        bank_name: str,
        finding_count: int,
        output_dat: str,
        output_csv: str,
        report_txt: str,
        report_html: str,
        report_pdf: str,
    ) -> None:
        subject = f"Dispute Processing Complete - {file_name}"
        body = (
            f"Dispute processing completed for: {file_name}\n"
            f"Bank name: {bank_name}\n"
            f"Disputes found: {finding_count}\n\n"
            f"Output Metro 2: {output_dat}\n"
            f"Output CSV: {output_csv}\n"
            f"Report TXT: {report_txt}\n"
            f"Report HTML: {report_html}\n"
            f"Report PDF: {report_pdf}\n"
        )

        self.send(subject, body, Path(report_txt))

    def send_failure(
        self,
        file_name: str,
        bank_name: str,
        error_excerpt: str,
    ) -> None:
        subject = f"Dispute Processing Failed - {file_name}"
        body = (
            f"Dispute processing failed for: {file_name}\n"
            f"Bank name: {bank_name}\n\n"
            f"Error summary:\n{error_excerpt}\n"
        )

        self.send(subject, body)
