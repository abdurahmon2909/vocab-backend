# app/core/security.py
import hashlib
import hmac
from urllib.parse import parse_qsl
import json


def validate_telegram(init_data: str, bot_token: str) -> dict:
    """
    Validate Telegram Web App initialization data.
    Returns user data dict if valid, raises exception otherwise.
    """
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_ = data.pop("hash", None)

    if not hash_:
        raise Exception("Missing hash in Telegram data")

    # Sort keys alphabetically and create data check string
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )

    # Generate secret key from bot token
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    # Calculate expected hash
    calc_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if calc_hash != hash_:
        raise Exception("Invalid Telegram data hash")

    # Parse user data
    user_str = data.get("user")
    if not user_str:
        raise Exception("No user data in Telegram init data")

    return json.loads(user_str)


def generate_bot_token_hash(bot_token: str) -> str:
    """Generate hash for bot token (for additional security)"""
    return hashlib.sha256(bot_token.encode()).hexdigest()


def validate_auth_token(token: str, expected_token: str) -> bool:
    """Validate simple auth token"""
    return hmac.compare_digest(token, expected_token)