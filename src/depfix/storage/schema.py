"""SQLAlchemy declarative schema.

``tracked_package`` / ``version_event`` (Week 0's single-version-string
model) are gone as of Week 2 — see ``docs/decisions.md``. Everything below is
provider / feed / change-event / breaking-change, keyed off Week 1's
multi-source model.

Migrations are still deferred: :func:`depfix.storage.db.init_schema` calls
``Base.metadata.create_all`` at start-up, which is sufficient for new
tables (``breaking_change``) but *not* for the new ``classified_at`` column
on the pre-existing ``change_event`` table — that needs a manual
``ALTER TABLE ... ADD COLUMN`` (or a drop/recreate in dev). Alembic adoption
is pushed to Week 3, once idempotent-write requirements force a real
migration story instead of one-off ALTERs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    """Common declarative base for all depfix tables."""


# ============================================================================
#  Week 1 — provider / feed / change-event tables
# ============================================================================


class Provider(Base):
    """A vendor we watch. Mirrors one entry in providers.yaml."""

    __tablename__ = "provider"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    api_version_scheme: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    feeds: Mapped[list[FeedState]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )


class FeedState(Base):
    """Last-known position of one feed. The compare-and-store cursor.

    ``last_payload_path`` points at the on-disk cache of the previous OpenAPI
    document. The spec body is not stored here: Stripe's is ~6 MB, we need the
    whole prior document to diff, and it is never queried by column.
    """

    __tablename__ = "feed_state"
    __table_args__ = (
        UniqueConstraint("provider_id", "feed_key", name="uq_feed_state_provider_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("provider.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feed_key: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    last_token: Mapped[str | None] = mapped_column(String(255), default=None)
    last_payload_sha256: Mapped[str | None] = mapped_column(String(64), default=None)
    last_payload_path: Mapped[str | None] = mapped_column(Text, default=None)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    provider: Mapped[Provider] = relationship(back_populates="feeds")

    def __repr__(self) -> str:  # pragma: no cover
        return f"FeedState({self.provider_id}/{self.feed_key} @ {self.last_token})"


class ChangeEventRow(Base):
    """A detected change. Week 2's classifier reads from here.

    ``dedupe_key`` is unique and is the Week 6 idempotency anchor — it is what
    stops us reopening the same PR on every cron tick.
    """

    __tablename__ = "change_event"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_change_event_dedupe"),
        Index("ix_change_event_provider_detected", "provider_id", "detected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("provider.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feed_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, default=None)
    old_token: Mapped[str | None] = mapped_column(String(255), default=None)
    new_token: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    body: Mapped[str | None] = mapped_column(Text, default=None)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    # Set once `depfix classify` has processed this event. Nullable + set
    # post-hoc rather than a status enum: classification can be re-run (e.g.
    # after a prompt change) without needing a "pending" -> "done" state
    # machine — the presence of BreakingChangeRow children is the real state.
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    spec_changes: Mapped[list[SpecChangeRow]] = relationship(
        back_populates="change_event", cascade="all, delete-orphan"
    )
    breaking_changes: Mapped[list[BreakingChangeRow]] = relationship(
        back_populates="change_event", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"ChangeEventRow({self.provider_id} {self.old_token} -> "
            f"{self.new_token} [{self.severity}])"
        )


class SpecChangeRow(Base):
    """One structural delta from an OpenAPI diff.

    Queryable because this is the table that answers the provider-side pitch:
    "which of your changes break the most call sites". Do not collapse it into
    a JSON blob on change_event.
    """

    __tablename__ = "spec_change"
    __table_args__ = (Index("ix_spec_change_kind_severity", "kind", "severity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_event_id: Mapped[int] = mapped_column(
        ForeignKey("change_event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="n/a")
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    pointer: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    before: Mapped[str | None] = mapped_column(Text, default=None)
    after: Mapped[str | None] = mapped_column(Text, default=None)

    change_event: Mapped[ChangeEventRow] = relationship(back_populates="spec_changes")


# ============================================================================
#  Week 2 — classification output
# ============================================================================


class BreakingChangeRow(Base):
    """A classified, actionable breaking change — what ``depfix run`` consumes.

    ``dedupe_key`` (see ``core.models.BreakingChange.dedupe_key``) is unique
    so re-running ``depfix classify`` on the same event is idempotent rather
    than inserting duplicate rows. Indexed on ``(kind, source)`` because that
    is the eval/reporting axis: "how many PARAM_REMOVED changes came from
    spec_diff vs release_notes".
    """

    __tablename__ = "breaking_change"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_breaking_change_dedupe"),
        Index("ix_breaking_change_kind_source", "kind", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_event_id: Mapped[int] = mapped_column(
        ForeignKey("change_event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    package: Mapped[str] = mapped_column(String(214), nullable=False)
    old_version: Mapped[str] = mapped_column(String(128), nullable=False)
    new_version: Mapped[str] = mapped_column(String(128), nullable=False)
    old_api: Mapped[str] = mapped_column(Text, nullable=False)
    new_api: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    migration_guide: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_url: Mapped[str | None] = mapped_column(Text, default=None)
    evidence: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    call_site_hints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    change_event: Mapped[ChangeEventRow] = relationship(back_populates="breaking_changes")

    def __repr__(self) -> str:  # pragma: no cover
        return f"BreakingChangeRow({self.package} {self.kind} {self.old_api!r})"
