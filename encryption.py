# app/services/encryption.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, binascii
from app.config import AES_KEY_HEX

def _key_bytes():
    # AES_KEY_HEX is hex string of 16 bytes (32 hex chars)
    k = AES_KEY_HEX
    try:
        b = binascii.unhexlify(k)
    except Exception:
        b = k.encode()[:16]
    return b

def encrypt_bytes(plaintext_bytes: bytes) -> dict:
    key = _key_bytes()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext_bytes, None)
    return {"nonce": binascii.hexlify(nonce).decode(), "ciphertext": binascii.hexlify(ct).decode()}

def decrypt_bytes(nonce_hex: str, ct_hex: str) -> bytes:
    key = _key_bytes()
    aes = AESGCM(key)
    nonce = binascii.unhexlify(nonce_hex)
    ct = binascii.unhexlify(ct_hex)
    pt = aes.decrypt(nonce, ct, None)
    return pt
