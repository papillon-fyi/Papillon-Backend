import os
import logging
from dotenv import load_dotenv
from server.logger import logger

# Load environment variables from .env
load_dotenv()

# Server / Host configuration
HOSTNAME = os.environ.get("HOSTNAME")
if not HOSTNAME:
    raise RuntimeError('You must set "HOSTNAME" in your .env file.')

# DID for this service; defaults to did:web if not provided
SERVICE_DID = f"did:web:{HOSTNAME}"

# Optional global flags
def _get_bool_env_var(value: str) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "t", "yes", "y"}

IGNORE_ARCHIVED_POSTS = _get_bool_env_var(os.environ.get("IGNORE_ARCHIVED_POSTS"))
IGNORE_REPLY_POSTS = _get_bool_env_var(os.environ.get("IGNORE_REPLY_POSTS"))

# Logging configuration
SHOW_DEBUG_LOGS = _get_bool_env_var(os.environ.get("SHOW_DEBUG_LOGS"))
if SHOW_DEBUG_LOGS:
    logger.setLevel(logging.DEBUG)
