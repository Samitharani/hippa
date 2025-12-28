# app/models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db import Base  # ✅ ONLY Base (single source)


# -----------------------------
# USER TABLE
# -----------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="doctor")  # doctor | nurse | admin
    created_at = Column(DateTime, default=datetime.utcnow)


# -----------------------------
# PATIENT TABLE
# -----------------------------
class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    data = Column(Text)        # raw patient record
    cleaned = Column(Text)     # cleaned / processed text
    created_at = Column(DateTime, default=datetime.utcnow)

    vectors = relationship("VectorRecord", back_populates="patient")


# -----------------------------
# VECTOR TABLE (ONLY ONE!)
# -----------------------------
class VectorRecord(Base):
    __tablename__ = "vectors"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), index=True)

    vector_id = Column(String, unique=True, index=True)
    meta_data = Column(Text)          # JSON metadata
    encrypted_blob = Column(Text)     # encrypted vector (base64/hex)

    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="vectors")


# -----------------------------
# AUDIT LOG TABLE
# -----------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user = Column(String)
    action = Column(String)
    details = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
