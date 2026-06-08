import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def _is_configured() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASS and config.ALERT_EMAIL_TO)


def send_alert_email(
    alert_type: str,
    message: str,
    hostname: str,
    private_ip: str,
    severity: str,
):
    if not _is_configured():
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    severity_upper = severity.upper()
    subject = f"[Polaris] [{severity_upper}] {alert_type} — {hostname}"

    color_map = {"critical": "#e53e3e", "warning": "#dd6b20", "info": "#3182ce"}
    color = color_map.get(severity.lower(), "#718096")

    body_html = f"""
<html><body style="font-family:sans-serif;background:#f7fafc;padding:20px;">
  <div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;
              border-top:4px solid {color};padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.1)">
    <h2 style="margin:0 0 4px;color:{color};">{severity_upper}: {alert_type}</h2>
    <p style="color:#718096;margin:0 0 20px;font-size:13px;">{ts}</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:6px 12px;background:#f7fafc;font-weight:600;width:120px;">Node</td>
          <td style="padding:6px 12px;">{hostname}</td></tr>
      <tr><td style="padding:6px 12px;background:#f7fafc;font-weight:600;">IP</td>
          <td style="padding:6px 12px;">{private_ip}</td></tr>
      <tr><td style="padding:6px 12px;background:#f7fafc;font-weight:600;">Alert</td>
          <td style="padding:6px 12px;">{alert_type}</td></tr>
      <tr><td style="padding:6px 12px;background:#f7fafc;font-weight:600;">Message</td>
          <td style="padding:6px 12px;">{message}</td></tr>
    </table>
    <p style="margin:20px 0 0;font-size:12px;color:#a0aec0;">Polaris Monitor</p>
  </div>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Polaris Monitor <{config.SMTP_USER}>"
    msg["To"] = config.ALERT_EMAIL_TO
    msg.attach(MIMEText(f"{severity_upper}: {alert_type}\nNode: {hostname} ({private_ip})\n{message}\n{ts}", "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.sendmail(config.SMTP_USER, config.ALERT_EMAIL_TO, msg.as_string())
        print(f"[email] Alert sent: {subject}")
    except Exception as e:
        print(f"[email] Failed to send alert email: {e}")
