"""Constants for the Enable Banking integration."""

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
CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_TRANSACTION_COUNT = "transaction_count"
CONF_TRANSACTION_LOOKBACK_DAYS = "transaction_lookback_days"

DEFAULT_CONSENT_DAYS = 90
DEFAULT_PSU_TYPE = "personal"
DEFAULT_REFRESH_INTERVAL = 60
DEFAULT_TRANSACTION_COUNT = 0
DEFAULT_TRANSACTION_LOOKBACK_DAYS = 90
MIN_REFRESH_INTERVAL = 15
MAX_REFRESH_INTERVAL = 1440
MAX_TRANSACTION_COUNT = 20
MAX_TRANSACTION_PAGES = 5
TRANSACTION_LOOKBACK_OPTIONS = (7, 30, 90, 365)

DATA_PENDING_FLOWS = "pending_flows"
DATA_CALLBACK_REGISTERED = "callback_registered"
DATA_REAUTH_REASONS = "reauth_reasons"
REAUTH_REASON_APPLICATION = "application_credentials"
