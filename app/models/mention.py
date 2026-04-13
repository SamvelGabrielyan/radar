from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, DateTime, ForeignKey, Integer, Enum, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class SentimentEnum(str, enum.Enum):
    positive = "positive"
    neutral  = "neutral"
    negative = "negative"


class Company(Base):
    __tablename__ = "companies"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    name:       Mapped[str]      = mapped_column(String(255), nullable=False)
    keywords:   Mapped[list]     = mapped_column(JSON, default=list)
    is_active:  Mapped[bool]     = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    mentions: Mapped[list["Mention"]] = relationship(back_populates="company")


class Mention(Base):
    __tablename__ = "mentions"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True)
    company_id:      Mapped[int]           = mapped_column(ForeignKey("companies.id"))
    title:           Mapped[str]           = mapped_column(String(500))
    url:             Mapped[str]           = mapped_column(String(1000))
    source:          Mapped[str]           = mapped_column(String(255))
    snippet:         Mapped[str | None]    = mapped_column(Text)
    sentiment:       Mapped[SentimentEnum] = mapped_column(
                         Enum(SentimentEnum, native_enum=False),
                         default=SentimentEnum.neutral
                     )
    sentiment_score: Mapped[float]         = mapped_column(Float, default=0.0)
    published_at:    Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    fetched_at:      Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="mentions")
