"""
Phase 4: Email Delivery
- Reads the latest pulse .md and .txt files
- Builds a multipart email (plain + HTML)
- Dry-run: saves .eml to data/reports/
- Send mode (--send): delivers via Gmail SMTP
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)


def run_phase4(
    pulse_md_path: Path = None,
    recipient: str = None,
    recipient_name: str = None,
    send: bool = False,
    report_date: str = None,
) -> Path:
    """
    Build and optionally send the weekly pulse email.

    Args:
        pulse_md_path: Path to the pulse .md file. Uses latest if None.
        recipient: Email address to send to. Falls back to config.
        recipient_name: First name for personalised greeting.
        send: If True, actually send via SMTP. Otherwise write .eml only.
        report_date: Date string for subject line. Defaults to today.

    Returns:
        Path to the .eml file.
    """
    from groww_pulse.config import (
        EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT,
        SMTP_HOST, SMTP_PORT, APP_NAME, REPORTS_DIR
    )

    report_date = report_date or datetime.now(timezone.utc).date().isoformat()
    recipient = recipient or EMAIL_RECIPIENT or EMAIL_SENDER

    # ── Load pulse content ─────────────────────────────────────────────────
    if pulse_md_path is None:
        md_files = sorted(REPORTS_DIR.glob("pulse-*.md"), reverse=True)
        if not md_files:
            raise FileNotFoundError("No pulse MD file found. Run Phase 3 first.")
        pulse_md_path = md_files[0]

    txt_path = pulse_md_path.with_suffix(".txt")

    md_content = pulse_md_path.read_text(encoding="utf-8")
    txt_content = txt_path.read_text(encoding="utf-8") if txt_path.exists() else md_content

    # ── Build greeting ─────────────────────────────────────────────────────
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"

    # ── Build email ────────────────────────────────────────────────────────
    subject = f"{APP_NAME} Weekly Review Pulse — Week of {report_date}"

    html_body = _md_to_html(md_content, greeting, APP_NAME, report_date)
    plain_body = f"{greeting}\n\n{txt_content}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER or "noreply@growwpulse.app"
    msg["To"] = recipient
    msg["X-Mailer"] = "Groww Pulse Engine"

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # ── Save .eml ──────────────────────────────────────────────────────────
    eml_path = REPORTS_DIR / f"pulse-{report_date}.eml"
    eml_path.write_bytes(msg.as_bytes())
    logger.info(f"Phase 4: email saved → {eml_path}")

    # ── Send via SMTP ──────────────────────────────────────────────────────
    if send:
        if not EMAIL_SENDER or not EMAIL_PASSWORD:
            logger.error("EMAIL_SENDER or EMAIL_PASSWORD not configured. Cannot send.")
        else:
            _send_smtp(msg, EMAIL_SENDER, EMAIL_PASSWORD, SMTP_HOST, SMTP_PORT, recipient)

    return eml_path


def _send_smtp(msg, sender: str, password: str, host: str, port: int, recipient: str):
    """Send email via Gmail SMTP with TLS."""
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_bytes())
        logger.info(f"Email sent successfully to {recipient}")
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Check EMAIL_SENDER and EMAIL_PASSWORD.")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
    except Exception as e:
        logger.error(f"Email send failed: {e}")


def _md_to_html(md_content: str, greeting: str, app_name: str, date: str) -> str:
    """Convert markdown pulse to styled HTML email."""
    try:
        import markdown as md_lib
        body_html = md_lib.markdown(md_content, extensions=["extra"])
    except ImportError:
        # Fallback: basic conversion
        body_html = md_content.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{app_name} Weekly Pulse</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#00d09c 0%,#00b386 100%);padding:28px 36px;">
            <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">
              📊 {app_name} Weekly Review Pulse
            </h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">Week of {date}</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 36px;color:#1a1a2e;line-height:1.7;font-size:15px;">
            <p style="margin:0 0 24px;font-size:16px;">{greeting}</p>
            <div style="
              font-size:15px;
              color:#2d3748;
              line-height:1.8;
            ">
{_style_html_content(body_html)}
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;padding:20px 36px;border-top:1px solid #e8ecf0;">
            <p style="margin:0;font-size:12px;color:#9aa5b4;text-align:center;">
              This pulse was automatically generated from Play Store reviews.<br>
              No personally identifiable information is included.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _style_html_content(html: str) -> str:
    """Apply inline styles to the rendered HTML for email clients."""
    import re
    html = re.sub(r"<h3>", '<h3 style="color:#00b386;font-size:16px;margin:28px 0 12px;border-bottom:2px solid #e8f5f0;padding-bottom:8px;">', html)
    html = re.sub(r"<h2>", '<h2 style="color:#1a1a2e;font-size:18px;margin:0 0 20px;">', html)
    html = re.sub(r"<blockquote>", '<blockquote style="border-left:4px solid #00d09c;margin:16px 0;padding:12px 16px;background:#f0fdf9;border-radius:0 8px 8px 0;font-style:italic;color:#374151;">', html)
    html = re.sub(r"<strong>", '<strong style="color:#1a1a2e;">', html)
    html = re.sub(r"<ol>", '<ol style="padding-left:20px;margin:12px 0;">', html)
    html = re.sub(r"<ul>", '<ul style="padding-left:20px;margin:12px 0;">', html)
    html = re.sub(r"<li>", '<li style="margin:8px 0;">', html)
    html = re.sub(r"<p>", '<p style="margin:12px 0;">', html)
    html = re.sub(r"<hr\s*/?>", '<hr style="border:none;border-top:1px solid #e8ecf0;margin:28px 0;">', html)
    return html
