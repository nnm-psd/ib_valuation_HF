from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config.settings import DB_URL, DB_PATH   # DB_PATH needed for init_db mkdir

Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"
    id      = Column(Integer, primary_key=True)
    name    = Column(String, unique=True, nullable=False)
    ticker  = Column(String, nullable=True)
    country = Column(String, nullable=False)
    sector  = Column(String, nullable=True)
    financial_lines = relationship("FinancialLine", back_populates="company")


class FinancialLine(Base):
    """One row per (company, fiscal_year, canonical_field) — long-form storage."""
    __tablename__ = "financial_lines"
    id          = Column(Integer, primary_key=True)
    company_id  = Column(Integer, ForeignKey("companies.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    statement   = Column(String, nullable=False)
    field_name  = Column(String, nullable=False)
    value       = Column(Float,  nullable=True)
    company     = relationship("Company", back_populates="financial_lines")


class MarketDataPoint(Base):
    __tablename__ = "market_data"
    id                 = Column(Integer, primary_key=True)
    company_id         = Column(Integer, ForeignKey("companies.id"), nullable=False)
    date               = Column(String, nullable=False)
    close_price        = Column(Float,  nullable=True)
    shares_outstanding = Column(Float,  nullable=True)


engine       = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
