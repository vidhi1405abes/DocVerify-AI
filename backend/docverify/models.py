import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


def utcnow():
    return datetime.now(timezone.utc)


def utc_iso(moment):
    """ISO time with an explicit UTC offset. SQLite returns stored times without a time zone,
    and the browser would otherwise read them as local time."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role}


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(255))
    verdict: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[int] = mapped_column(Integer)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def summary(self):
        result = json.loads(self.result_json)
        return {
            "id": self.id,
            "documentType": self.document_type,
            "documentTypeName": result.get("documentTypeName"),
            "filename": self.filename,
            "verdict": self.verdict,
            "verdictLabel": result.get("verdictLabel"),
            "riskScore": self.risk_score,
            "createdAt": utc_iso(self.created_at),
        }


class AuthorizedRecord(Base):
    """A record from an authorized source (e.g. the issuing board) to compare against."""

    __tablename__ = "authorized_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    identifier: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    fields_json: Mapped[str] = mapped_column(Text, default="{}")
    source: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def fields(self):
        return json.loads(self.fields_json or "{}")

    def to_dict(self):
        return {
            "id": self.id,
            "documentType": self.document_type,
            "identifier": self.identifier,
            "name": self.name,
            "fields": self.fields,
            "source": self.source,
            "createdAt": utc_iso(self.created_at),
        }


def make_session_factory(database_url):
    options = {}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            options["poolclass"] = StaticPool
    engine = create_engine(database_url, **options)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
