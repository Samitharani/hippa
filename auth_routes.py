
from fastapi import APIRouter, HTTPException
from datetime import timedelta
from app.schemas import LoginRequest
from app.db import users_collection
from app.auth import verify_password, create_access_token
from app.utils.activity_logger import log_activity

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login")
def login(data: LoginRequest):
    user = users_collection.find_one({"username": data.username})

    if not user:
        # log failed login (user not found)
        try:
            log_activity(actor=data.username, role=(data.role or "unknown"), action="LOGIN_FAILED", status="Failed")
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="User not found")

    # 🔐 role validation
    if user["role"].lower() != data.role.lower():
        # log failed login (role mismatch)
        try:
            log_activity(actor=data.username, role=data.role or "unknown", action="LOGIN_FAILED", status="Failed")
        except Exception:
            pass
        raise HTTPException(status_code=403, detail="Role mismatch")

    # 🔑 password validation (VERY IMPORTANT)
    try:
        pw_ok = verify_password(data.password, user["password"])
    except Exception:
        # treat verification errors as failed attempts and log
        try:
            log_activity(actor=data.username, role=data.role or "unknown", action="LOGIN_FAILED", status="Failed")
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid password")

    if not pw_ok:
        # log failed login (invalid password)
        try:
            log_activity(actor=data.username, role=data.role or "unknown", action="LOGIN_FAILED", status="Failed")
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=60)
    )

    # log successful login
    try:
        log_activity(actor=user["username"], role=user["role"], action="LOGIN_SUCCESS", status="Success")
    except Exception:
        pass

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"]
    }
