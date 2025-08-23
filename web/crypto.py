from __future__ import annotations

"""Utilities for encrypting Telegram StringSession values."""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import settings

# Derive key bytes for version 1 from environment variable
_KEY_V1 = hashlib.sha256(settings.session_key_1.encode()).digest()


def encrypt_string_session(session: str) -> tuple[str, int]:
    """Encrypt a StringSession using AES-GCM.

    Returns a tuple of the base64 encoded ciphertext (nonce + data) and
    the key version used for encryption.
    """

    aes = AESGCM(_KEY_V1)
    nonce = os.urandom(12)
    cipher = aes.encrypt(nonce, session.encode(), None)
    return base64.b64encode(nonce + cipher).decode(), 1


def decrypt_string_session(cipher_b64: str, kver: int) -> str:
    """Decrypt a previously encrypted StringSession."""
    if kver != 1:
        raise ValueError("unsupported key version")
    data = base64.b64decode(cipher_b64)
    nonce, cipher = data[:12], data[12:]
    aes = AESGCM(_KEY_V1)
    return aes.decrypt(nonce, cipher, None).decode()
