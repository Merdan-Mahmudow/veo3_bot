import hmac
import json
import base64
import hashlib
from datetime import datetime, timedelta
import random
import string
from typing import Literal
from config import Settings

class ReferralService:
    def __init__(self):
        self.settings = Settings()
        # It's crucial that this secret key is the same one used for the bot's API token
        # or another securely stored secret. Using bot_api_token for this example.
        self.secret_key = self.settings.env.bot_api_token.encode('utf-8')

    def _sign_payload(self, payload_str: str) -> str:
        """Creates an HMAC-SHA256 signature for the payload."""
        return hmac.new(self.secret_key, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()

    def generate_referral_link(self, bot_username: str, user_id: str, link_id: str, link_type: str, percent: int = 0, expires_in_days: int = None) -> str:
        """
        Generates a signed deep-link for referrals.
        """
        payload = {
            "t": link_type,    # 'user' or 'partner'
            "rid": user_id,    # referrer_id (owner of the link)
            "lid": link_id,    # link_id
        }
        if link_type == 'partner':
            payload["p"] = percent

        if expires_in_days:
            payload["exp"] = int((datetime.utcnow() + timedelta(days=expires_in_days)).timestamp())

        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        signature = self._sign_payload(payload_str)

        # Combine payload and signature into a single token
        token_data = {
            "p": payload,
            "s": signature
        }

        token_str = json.dumps(token_data)
        encoded_token = base64.urlsafe_b64encode(token_str.encode('utf-8')).decode('utf-8')

        return f"https://t.me/{bot_username}?start={encoded_token}"

    def decode_and_validate_token(self, encoded_token: str) -> dict | None:
        """
        Decodes the token, validates the signature, and checks for expiration.
        Returns the payload if valid, otherwise None.
        """
        try:
            decoded_str = base64.urlsafe_b64decode(encoded_token).decode('utf-8')
            token_data = json.loads(decoded_str)

            payload = token_data.get("p")
            signature = token_data.get("s")

            if not payload or not signature:
                return None

            payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            expected_signature = self._sign_payload(payload_str)

            if not hmac.compare_digest(expected_signature, signature):
                return None  # Signature mismatch

            # Check for expiration
            if "exp" in payload and datetime.utcnow().timestamp() > payload["exp"]:
                return None  # Token expired

            return payload

        except (json.JSONDecodeError, base64.binascii.Error, UnicodeDecodeError):
            return None # Invalid token format
        

    