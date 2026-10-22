"""Databastabeller (SR-02.5: beständig data i relationsdatabas)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    board_size: Mapped[int] = mapped_column(Integer, default=15)
    # mode: "ai" | "local" | "online"
    mode: Mapped[str] = mapped_column(String(16), default="ai")
    # lätt | normal | svår
    difficulty: Mapped[str] = mapped_column(String(16), default="normal")
    # pending | in_progress | finished
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    # black_wins | white_wins | draw | forfeit | aborted | None
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    winner: Mapped[int | None] = mapped_column(Integer, nullable=True)
    human_color: Mapped[int] = mapped_column(Integer, default=1)
    turn: Mapped[int] = mapped_column(Integer, default=1)
    player_black: Mapped[str | None] = mapped_column(String(64), nullable=True)
    player_white: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invite_token: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    saved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    moves: Mapped[list["Move"]] = relationship(
        back_populates="game", cascade="all, delete-orphan", order_by="Move.seq"
    )


class Move(Base):
    __tablename__ = "moves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)  # dragnummer, 1-baserat
    row: Mapped[int] = mapped_column(Integer)
    col: Mapped[int] = mapped_column(Integer)
    player: Mapped[int] = mapped_column(Integer)

    game: Mapped[Game] = relationship(back_populates="moves")
