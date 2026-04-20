"""SMTP helpers for operator notifications (e.g. DNSBL listings)."""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

log = logging.getLogger(__name__)


def send_blacklist_digest_email(*, listed_rows: list[dict]) -> None:
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    receiver_email = os.getenv("RECEIVER_EMAIL", "").strip()
    app_password = os.getenv("EMAIL_PASSWORD", "").replace(" ", "")

    if not sender_email or not receiver_email or not app_password:
        raise RuntimeError("Missing email config. Set SENDER_EMAIL, RECEIVER_EMAIL, EMAIL_PASSWORD.")

    rows_html = ""
    for r in listed_rows:
        ip = r.get("ip", "")
        bl = r.get("blacklist", "")
        ts = r.get("@timestamp", "")
        rows_html += f"""
        <tr>
          <td style="padding:10px;border:1px solid #e5e7eb;">{ip}</td>
          <td style="padding:10px;border:1px solid #e5e7eb;color:#b91c1c;font-weight:600;">{bl}</td>
          <td style="padding:10px;border:1px solid #e5e7eb;color:#374151;">{ts}</td>
        </tr>
        """

    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f9fafb;padding:16px;">
        <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <div style="padding:16px 18px;background:#fff7ed;border-bottom:1px solid #fed7aa;">
            <h2 style="margin:0;color:#9a3412;">Blacklisted servers</h2>
            <p style="margin:6px 0 0;color:#7c2d12;">Detected at {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC</p>
          </div>
          <div style="padding:16px 18px;">
            <table style="width:100%;border-collapse:collapse;">
              <thead>
                <tr style="background:#f3f4f6;">
                  <th style="text-align:left;padding:10px;border:1px solid #e5e7eb;">IP</th>
                  <th style="text-align:left;padding:10px;border:1px solid #e5e7eb;">DNSBL</th>
                  <th style="text-align:left;padding:10px;border:1px solid #e5e7eb;">Timestamp</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """
    msg = EmailMessage()
    msg["Subject"] = f"[CG Logs] Blacklisted servers detected ({len(listed_rows)})"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)
    log.info("Blacklist digest email sent (%d rows).", len(listed_rows))
