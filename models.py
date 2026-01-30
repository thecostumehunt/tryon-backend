from sqlalchemy import Column, String, Integer, Boolean, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import uuid


# -------------------------
# DEVICES (users without login)
# -------------------------
class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    credits = Column(Integer, default=0)
    free_used = Column(Boolean, default=False)

    email = Column(Text)
    fingerprint_hash = Column(Text)
    ip_hash = Column(Text)

    created_at = Column(TIMESTAMP)
    last_seen = Column(TIMESTAMP)
    last_try_at = Column(TIMESTAMP)
    total_tries = Column(Integer, default=0)


# -------------------------
# PAYMENTS (all gateways)
# -------------------------
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(UUID(as_uuid=True), nullable=False)

    provider = Column(Text)                       # "lemon", "paypal", "razorpay", "stripe"
    provider_payment_id = Column(Text, unique=True, index=True)

    product_name = Column(Text)
    email = Column(Text)

    amount = Column(Text)                         # "2.00", "5.00", "20.00"
    currency = Column(Text, default="USD")

    credits_added = Column(Integer)
    created_at = Column(TIMESTAMP)


# -------------------------
# USAGE LOGS (AI try-ons)
# -------------------------
class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(UUID(as_uuid=True))

    outfit_url = Column(Text)
    result_url = Column(Text)
    status = Column(Text)

    created_at = Column(TIMESTAMP)
