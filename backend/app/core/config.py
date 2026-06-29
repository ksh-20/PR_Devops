import json
import os
from models.handle_logging import get_logging_conf
logging = get_logging_conf()

logger = logging.getLogger(__name__)

# Resolve absolute config.json path relative to this file
_config_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config.json"))

try:
    with open(_config_path, "r") as f:
        content = f.read().strip()
        config = json.loads(content) if content else {}
except Exception as e:
    logger.error("JSON file not found at %s: %s", _config_path, e)
    config = {}

base_url = config.get("azure_devops_url", "")
collection = config.get("azure_collection_name", "")
pat = config.get("azure_pat", "")

username = config.get("username", "")
password = config.get("password", "")

secret = config.get("JWT_SECRET_KEY", "fallback-secret-for-dev")
algorithm = config.get("JWT_ALGORITHM", "HS256")
# Handle expiry dynamically, checking if it is an int/string or defaulting to 60
try:
    expiry = int(config.get("JWT_EXPIRATION_MINUTES", 60))
except (ValueError, TypeError):
    expiry = 60

doc_flow_tenant_id = config.get("DOC_FLOW_TENANT_ID", "")
doc_flow_client_id = config.get("DOC_FLOW_CLIENT_ID", "")
doc_flow_client_secret = config.get("DOC_FLOW_CLIENT_SECRET", "")

time_flow_tenant_id = config.get("TIME_FLOW_TENANT_ID", "")
time_flow_client_id = config.get("TIME_FLOW_CLIENT_ID", "")
time_flow_client_secret = config.get("TIME_FLOW_CLIENT_SECRET", "")

integrelity_tenant_id = config.get("INTEGRELITY_TENANT_ID", "")
integrelity_client_id = config.get("INTEGRELITY_CLIENT_ID", "")
integrelity_client_secret = config.get("INTEGRELITY_CLIENT_SECRET", "")

azure_cost_base_url = config.get("azure_cost_base_url", "")
azure_management_base_url = config.get("azure_management_base_url", "")

MODEL = config["MODEL"]
SUBSCRIPTION_KEY = config["SUBSCRIPTION_KEY"]
MODEL_ENDPOINT = config["MODEL_ENDPOINT"]

AZURE_PAT = config["AZURE_PAT"]
AZURE_COLLECTION = config["AZURE_COLLECTION"]
AZURE_BASE_URL = config["AZURE_BASE_URL"]
AZURE_PROJECT = config["AZURE_PROJECT"]