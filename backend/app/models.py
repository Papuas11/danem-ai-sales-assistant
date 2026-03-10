from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    current_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    deal_probability: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    potential_revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_profit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_timeline: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    notes: Mapped[list["DealNote"]] = relationship("DealNote", back_populates="deal", cascade="all, delete-orphan")


class DealNote(Base):
    __tablename__ = "deal_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    deal: Mapped[Deal] = relationship("Deal", back_populates="notes")


class InstrumentType(Base):
    __tablename__ = "instrument_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    aliases: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False)


class ServiceType(Base):
    __tablename__ = "service_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instrument_type_id: Mapped[int] = mapped_column(ForeignKey("instrument_types.id"), nullable=False)
    service_type_id: Mapped[int] = mapped_column(ForeignKey("service_types.id"), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rush_markup_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    on_site_markup_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_on_site_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    instrument_type: Mapped[InstrumentType] = relationship("InstrumentType")
    service_type: Mapped[ServiceType] = relationship("ServiceType")
