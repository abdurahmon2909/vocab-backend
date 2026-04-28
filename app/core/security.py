import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


MAX_INIT_DATA_AGE_SECONDS = 86400


def validate_telegram(init_data: str, bot_token: str) -> dict:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_ = data.pop("hash", None)

    if not hash_:
        raise Exception("Missing hash in Telegram data")

    auth_date_raw = data.get("auth_date")
    if not auth_date_raw:
        raise Exception("Missing auth_date in Telegram data")

    try:
        auth_date = int(auth_date_raw)
    except ValueError:
        raise Exception("Invalid auth_date in Telegram data")

    if time.time() - auth_date > MAX_INIT_DATA_AGE_SECONDS:
        raise Exception("Telegram initData expired")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()

    calc_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calc_hash, hash_):
        raise Exception("Invalid Telegram data hash")

    user_str = data.get("user")
    if not user_str:
        raise Exception("No user data in Telegram init data")

    return json.loads(user_str)


def generate_bot_token_hash(bot_token: str) -> str:
    return hashlib.sha256(bot_token.encode()).hexdigest()


def validate_auth_token(token: str, expected_token: str) -> bool:
    return hmac.compare_digest(token, expected_token)