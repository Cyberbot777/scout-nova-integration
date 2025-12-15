import os
import logging
from .secrets_manager import get_secret

logger = logging.getLogger(__name__)


def validate_api_key(client_api_key: str) -> bool:
    if not client_api_key:
        return False

    try:
        secret_name = os.environ["API_KEY_SECRET"]
        secret = get_secret(secret_name)
        expected_key = secret.get("api-key")
    except Exception as exc:
        logger.error(f"Error fetching API key secret: {exc}")
        return False

    if not expected_key:
        logger.error("Secret missing 'api-key' value")
        return False

    return client_api_key.strip() == expected_key.strip()
