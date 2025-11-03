from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

from app.config import settings

# Generate encryption key from secret
def _get_encryption_key() -> bytes:
    """Derive encryption key from settings"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'job_crawler_salt',  # In production, use a random salt stored securely
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return key


cipher = Fernet(_get_encryption_key())


def encrypt_password(password: str) -> str:
    """Encrypt a password"""
    return cipher.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt a password"""
    return cipher.decrypt(encrypted.encode()).decode()
