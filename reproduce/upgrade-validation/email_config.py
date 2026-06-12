# Email configuration for HAFiscal validation notifications
#
# SECURITY (2026-06-11): this file previously contained a plaintext Gmail app
# password, git-tracked since 2026-02. That credential must be treated as
# compromised: REVOKED by the owner + scheduled history purge — see
# plans/20260611_security-purge-email-credential.md. NEVER commit a credential
# here; provide it via the environment instead.

import os

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "carrollcdc@gmail.com"
# Set HAFISCAL_SMTP_APP_PASSWORD in the environment (e.g. ~/.profile, never the repo).
SENDER_PASSWORD = os.environ.get("HAFISCAL_SMTP_APP_PASSWORD", "")
RECIPIENT_EMAIL = "carrollcdc@gmail.com"
