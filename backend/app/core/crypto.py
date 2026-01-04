import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


NONCE_SIZE = 12
KEY_SIZE = 32


def _load_key() -> bytes:
    key = base64.urlsafe_b64decode(settings.MASTER_KEY)
    if len(key) != KEY_SIZE:
        raise ValueError("MASTER_KEY must be 32 bytes base64")
    return key


def encrypt_dict(data: dict[str, Any]) -> bytes:
    key = _load_key()
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_dict(blob: bytes) -> dict[str, Any]:
    key = _load_key()
    nonce = blob[:NONCE_SIZE]
    ciphertext = blob[NONCE_SIZE:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))
