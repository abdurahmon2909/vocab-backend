import hashlib
import hmac
from urllib.parse import parse_qsl
import json


def validate_telegram(init_data: str, bot_token: str) -> dict:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_ = data.pop("hash", None)

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    calc_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if calc_hash != hash_:
        raise Exception("Invalid Telegram data")

    return json.loads(data["user"])