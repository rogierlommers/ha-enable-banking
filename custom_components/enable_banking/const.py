"""Constants for the Enable Banking integration."""

from datetime import timedelta

DOMAIN = "enable_banking"
PLATFORMS = ["sensor"]

API_BASE_URL = "https://api.enablebanking.com"
CALLBACK_PATH = "/api/enable_banking/callback"

CONF_APPLICATION_ID = "application_id"
CONF_PRIVATE_KEY = "private_key"
CONF_COUNTRY = "country"
CONF_ASPSP_NAME = "aspsp_name"
CONF_PSU_TYPE = "psu_type"
CONF_CONSENT_DAYS = "consent_days"
CONF_SESSION_ID = "session_id"

DEFAULT_CONSENT_DAYS = 90
DEFAULT_PSU_TYPE = "personal"
SCAN_INTERVAL = timedelta(hours=1)

DATA_PENDING_FLOWS = "pending_flows"
