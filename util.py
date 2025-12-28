import uuid
import secrets
from datetime import datetime

# Generate unique vector IDs or patient IDs
def gen_id(prefix: str = ""):
    return prefix + uuid.uuid4().hex

# Generate secure random keys (optional)
def gen_secure_token(n: int = 32):
    return secrets.token_hex(n)

# Timestamp helper
def now_iso():
    return datetime.utcnow().isoformat() + "Z"
