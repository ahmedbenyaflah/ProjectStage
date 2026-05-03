"""SMTP helpers for operator notifications (e.g. DNSBL listings)."""
from __future__ import annotations

import logging
import os
import smtplib
from collections.abc import Iterable
from datetime import datetime
from email.message import EmailMessage

log = logging.getLogger(__name__)


def _normalize_dnsbl_recipient_emails(emails: Iterable[str]) -> list[str]:
    """Dedupe by case-insensitive address; preserve first spelling."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in emails:
        e = str(raw or "").strip()
        if not e:
            continue
        key = e.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _apply_dnsbl_recipients(msg: EmailMessage, recipient_emails: Iterable[str]) -> list[str]:
    """Set To (and Bcc for extras). Returns the normalized list used."""
    rec = _normalize_dnsbl_recipient_emails(recipient_emails)
    if not rec:
        raise ValueError("DNSBL email requires at least one recipient (N3 subscriber).")
    if len(rec) == 1:
        msg["To"] = rec[0]
    else:
        msg["To"] = rec[0]
        msg["Bcc"] = ", ".join(rec[1:])
    return rec


def _unique_ips_from_rows(rows: list[dict]) -> list[str]:
    ips = {str(r.get("ip") or "").strip() for r in rows}
    ips.discard("")
    return sorted(ips)


def blacklist_email_configured() -> bool:
    """True if SMTP can send (DNSBL reports go only to N3 users from the DB, not RECEIVER_EMAIL)."""
    sender = os.getenv("SENDER_EMAIL", "").strip()
    password = os.getenv("EMAIL_PASSWORD", "").replace(" ", "")
    return bool(sender and password)


def send_blacklist_digest_email(
    *,
    listed_rows: list[dict],
    recipient_emails: list[str],
    new_since_previous_scan: bool = False,
) -> None:
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    app_password = os.getenv("EMAIL_PASSWORD", "").replace(" ", "")

    if not sender_email or not app_password:
        raise RuntimeError("Missing email config. Set SENDER_EMAIL, EMAIL_PASSWORD.")

    rows_html = ""
    for r in listed_rows:
        ip = r.get("ip", "")
        bl = r.get("blacklist", "")
        ts = r.get("@timestamp", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
        rows_html += f"""
        <tr>
          <td style="padding:10px;border:1px solid #e5e7eb;">{ip}</td>
          <td style="padding:10px;border:1px solid #e5e7eb;color:#b91c1c;font-weight:600;">{bl}</td>
          <td style="padding:10px;border:1px solid #e5e7eb;color:#374151;">{ts}</td>
        </tr>
        """

    now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    unique_ips = _unique_ips_from_rows(listed_rows)
    ip_summary_html = ""
    if unique_ips:
        ip_list = ", ".join(unique_ips)
        if new_since_previous_scan:
            ip_summary_html = f"""
            <p style="margin:12px 0 0;padding:12px 14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;color:#7f1d1d;">
              <strong>Newly blacklisted IP addresses</strong> (at least one new DNSBL listing this scan):<br/>
              <span style="font-family:ui-monospace,monospace;font-size:14px;">{ip_list}</span>
            </p>
            """
        else:
            ip_summary_html = f"""
            <p style="margin:12px 0 0;padding:12px 14px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;color:#374151;">
              <strong>IP addresses</strong> in this report:<br/>
              <span style="font-family:ui-monospace,monospace;font-size:14px;">{ip_list}</span>
            </p>
            """
    subline = (
        f"These (IP, DNSBL) pairs were not listed on the previous scan. Notification sent at {now_utc} UTC."
        if new_since_previous_scan
        else f"Detected at {now_utc} UTC."
    )
    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f9fafb;padding:16px;">
        <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <div style="padding:16px 18px;background:#fff7ed;border-bottom:1px solid #fed7aa;">
            <h2 style="margin:0;color:#9a3412;">{"New blacklist listings" if new_since_previous_scan else "Blacklisted servers"}</h2>
            <p style="margin:6px 0 0;color:#7c2d12;">{subline}</p>
            {ip_summary_html}
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
    if new_since_previous_scan:
        ip_bits = _unique_ips_from_rows(listed_rows)
        subj_ips = ", ".join(ip_bits[:5]) + (" ..." if len(ip_bits) > 5 else "")
        ip_suffix = f" — IPs: {subj_ips}" if subj_ips else ""
        msg["Subject"] = f"[CG Logs] NEW blacklist listing(s) ({len(listed_rows)}){ip_suffix}"
    else:
        msg["Subject"] = f"[CG Logs] Blacklisted servers detected ({len(listed_rows)})"
    msg["From"] = sender_email
    recs = _apply_dnsbl_recipients(msg, recipient_emails)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)
    log.info(
        "Blacklist %s email sent (%d rows, %d N3 recipient(s)).",
        "new-listing" if new_since_previous_scan else "digest",
        len(listed_rows),
        len(recs),
    )


def send_blacklist_delist_email(*, removed_rows: list[dict], recipient_emails: list[str]) -> None:
    """Notify that (ip, dnsbl) pairs are no longer listed (confirmed CLEAN on latest scan)."""
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    app_password = os.getenv("EMAIL_PASSWORD", "").replace(" ", "")

    if not sender_email or not app_password:
        raise RuntimeError("Missing email config. Set SENDER_EMAIL, EMAIL_PASSWORD.")

    rows_html = ""
    for r in removed_rows:
        ip = r.get("ip", "")
        bl = r.get("blacklist", "")
        ts = r.get("@timestamp", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
        rows_html += f"""
        <tr>
          <td style="padding:10px;border:1px solid #e5e7eb;">{ip}</td>
          <td style="padding:10px;border:1px solid #e5e7eb;color:#047857;font-weight:600;">{bl}</td>
          <td style="padding:10px;border:1px solid #e5e7eb;color:#374151;">{ts}</td>
        </tr>
        """

    now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cleared_ips = _unique_ips_from_rows(removed_rows)
    cleared_ip_box = ""
    if cleared_ips:
        c_list = ", ".join(cleared_ips)
        cleared_ip_box = f"""
            <p style="margin:12px 0 0;padding:12px 14px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;color:#14532d;">
              <strong>IP addresses removed from blacklist</strong> (clean on this scan vs listed last time):<br/>
              <span style="font-family:ui-monospace,monospace;font-size:14px;">{c_list}</span>
            </p>
            """
    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;background:#f9fafb;padding:16px;">
        <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <div style="padding:16px 18px;background:#ecfdf5;border-bottom:1px solid #a7f3d0;">
            <h2 style="margin:0;color:#047857;">Removed from blacklist</h2>
            <p style="margin:6px 0 0;color:#065f46;">These (IP, DNSBL) pairs were listed on the previous scan and are now clean. Notification sent at {now_utc} UTC.</p>
            {cleared_ip_box}
          </div>
          <div style="padding:16px 18px;">
            <table style="width:100%;border-collapse:collapse;">
              <thead>
                <tr style="background:#f3f4f6;">
                  <th style="text-align:left;padding:10px;border:1px solid #e5e7eb;">IP</th>
                  <th style="text-align:left;padding:10px;border:1px solid #e5e7eb;">DNSBL</th>
                  <th style="text-align:left;padding:10px;border:1px solid #e5e7eb;">Detected</th>
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
    ip_bits = _unique_ips_from_rows(removed_rows)
    subj_ips = ", ".join(ip_bits[:5]) + (" ..." if len(ip_bits) > 5 else "")
    ip_suffix = f" — IPs: {subj_ips}" if subj_ips else ""
    msg["Subject"] = f"[CG Logs] Removed from DNSBL blacklist ({len(removed_rows)}){ip_suffix}"
    msg["From"] = sender_email
    recs = _apply_dnsbl_recipients(msg, recipient_emails)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)
    log.info("Blacklist delist email sent (%d rows, %d N3 recipient(s)).", len(removed_rows), len(recs))
