#!/usr/bin/env python3
"""
Email notification system for HAFiscal validation.
Sends alerts when divergence is detected between HARK versions.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import sys
import os

# Add the config directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from email_config import (
    SMTP_SERVER, SMTP_PORT, 
    SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL
)


def send_divergence_notification(
    step: int,
    metrics: dict,
    analysis: str,
    proposed_fixes: list,
    log_file: str = None
):
    """
    Send email notification when divergence is detected.
    
    Args:
        step: Which step (1-5) the divergence occurred at
        metrics: Dict of {metric_name: (value_0141, value_0170, pct_diff)}
        analysis: Text explaining the root cause analysis
        proposed_fixes: List of at least 2 proposed fixes
        log_file: Path to detailed log file
    """
    
    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[HAFiscal] 🛑 Divergence Detected at Step {step}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    
    # Build metrics table
    metrics_text = "METRICS WITH DIVERGENCE:\n"
    metrics_text += "-" * 60 + "\n"
    metrics_text += f"{'Metric':<20} {'0.14.1':>12} {'0.17.0':>12} {'Diff':>10}\n"
    metrics_text += "-" * 60 + "\n"
    for name, (v014, v017, diff) in metrics.items():
        metrics_text += f"{name:<20} {v014:>12.6f} {v017:>12.6f} {diff:>9.2f}%\n"
    
    # Build fixes list
    fixes_text = "PROPOSED FIXES:\n"
    for i, fix in enumerate(proposed_fixes, 1):
        fixes_text += f"\n{i}. {fix}\n"
    
    # Plain text version
    text_content = f"""
================================================================================
HAFiscal Validation - DIVERGENCE DETECTED
================================================================================

TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
STEP: {step}
THRESHOLD: 2% (0.02 log points)

{metrics_text}

================================================================================
ROOT CAUSE ANALYSIS
================================================================================
{analysis}

================================================================================
{fixes_text}
================================================================================

ACTION REQUIRED:
Please review the analysis and proposed fixes, then provide guidance on how
to proceed.

"""
    if log_file:
        text_content += f"\nDETAILED LOG: {log_file}\n"
    
    text_content += """
================================================================================
This is an automated message from the HAFiscal validation system.
================================================================================
"""
    
    # HTML version (nicer formatting)
    html_content = f"""
    <html>
    <body style="font-family: monospace; background-color: #1a1a1a; color: #e0e0e0; padding: 20px;">
        <div style="max-width: 800px; margin: 0 auto;">
            <h1 style="color: #ff6b6b;">🛑 HAFiscal Validation - Divergence Detected</h1>
            
            <table style="background-color: #2d2d2d; padding: 15px; border-radius: 5px; width: 100%;">
                <tr><td><strong>Time:</strong></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                <tr><td><strong>Step:</strong></td><td>{step}</td></tr>
                <tr><td><strong>Threshold:</strong></td><td>2% (0.02 log points)</td></tr>
            </table>
            
            <h2 style="color: #ffd93d;">📊 Metrics with Divergence</h2>
            <table style="background-color: #2d2d2d; padding: 10px; border-radius: 5px; width: 100%;">
                <tr style="background-color: #3d3d3d;">
                    <th style="padding: 8px; text-align: left;">Metric</th>
                    <th style="padding: 8px; text-align: right;">HARK 0.14.1</th>
                    <th style="padding: 8px; text-align: right;">HARK 0.17.0</th>
                    <th style="padding: 8px; text-align: right;">Difference</th>
                </tr>
    """
    
    for name, (v014, v017, diff) in metrics.items():
        color = "#ff6b6b" if diff > 2 else "#ffd93d"
        html_content += f"""
                <tr>
                    <td style="padding: 8px;">{name}</td>
                    <td style="padding: 8px; text-align: right;">{v014:.6f}</td>
                    <td style="padding: 8px; text-align: right;">{v017:.6f}</td>
                    <td style="padding: 8px; text-align: right; color: {color};">{diff:.2f}%</td>
                </tr>
        """
    
    html_content += f"""
            </table>
            
            <h2 style="color: #6bcb77;">🔍 Root Cause Analysis</h2>
            <div style="background-color: #2d2d2d; padding: 15px; border-radius: 5px; white-space: pre-wrap;">
{analysis}
            </div>
            
            <h2 style="color: #4d96ff;">🔧 Proposed Fixes</h2>
            <ol style="background-color: #2d2d2d; padding: 15px 15px 15px 35px; border-radius: 5px;">
    """
    
    for fix in proposed_fixes:
        html_content += f"<li style='margin-bottom: 10px;'>{fix}</li>\n"
    
    html_content += f"""
            </ol>
            
            <div style="background-color: #ff6b6b; color: #1a1a1a; padding: 15px; border-radius: 5px; margin-top: 20px;">
                <strong>⚠️ ACTION REQUIRED:</strong> Please review the analysis and proposed fixes, 
                then provide guidance on how to proceed.
            </div>
            
            {"<p><strong>Detailed log:</strong> " + log_file + "</p>" if log_file else ""}
            
            <hr style="border-color: #3d3d3d; margin-top: 30px;">
            <p style="color: #888; font-size: 12px;">
                This is an automated message from the HAFiscal validation system.
            </p>
        </div>
    </body>
    </html>
    """
    
    # Attach both versions
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")
    msg.attach(part1)
    msg.attach(part2)
    
    # Send email
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print(f"✅ Notification sent to {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        print(f"❌ Failed to send notification: {e}")
        return False


def send_test_notification():
    """Send a test notification to verify email is working."""
    return send_divergence_notification(
        step=0,
        metrics={
            "test_metric": (1.0, 1.05, 5.0),
        },
        analysis="This is a TEST notification to verify the email system is working correctly.\n\nNo actual divergence has been detected.",
        proposed_fixes=[
            "This is test fix #1 - no action needed",
            "This is test fix #2 - no action needed",
        ],
        log_file="/tmp/test_notification.log"
    )


def send_success_notification(step: int, message: str = ""):
    """Send notification that a step completed successfully."""
    msg = MIMEText(f"""
HAFiscal Validation - Step {step} PASSED

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

All metrics within 2% tolerance.

{message}

Proceeding to next step...
""")
    msg["Subject"] = f"[HAFiscal] ✅ Step {step} Passed"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        return True
    except Exception as e:
        print(f"❌ Failed to send success notification: {e}")
        return False


def send_email(subject: str, body: str):
    """
    Send a simple email with subject and body.
    This is a general-purpose wrapper for the notification system.
    """
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print(f"✅ Email sent to {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Sending test notification...")
        send_test_notification()
    else:
        print("Usage: python send_notification.py --test")
        print("       (or import and call functions directly)")
