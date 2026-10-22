"""Pydantic-modeller för API:t (request/response)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    board_size: int = Field(default=15, ge=5, le=25)
    mode: str = Field(default="ai", pattern="^(ai|local)$")
    difficulty: str = Field(default="normal", pattern="^(easy|normal|hard)$")
    color: str | None = Field(default=None, pattern="^(black|white)$")
    player_name: str | None = Field(default=None, max_length=64)


class MoveRequest(BaseModel):
    row: int
    col: int


class InviteRequest(BaseModel):
    board_size: int = Field(default=15, ge=5, le=25)
    color: str | None = Field(default=None, pattern="^(black|white)$")
    player_name: str = Field(min_length=1, max_length=64)


class AcceptInviteRequest(BaseModel):
    player_name: str = Field(min_length=1, max_length=64)


class MoveState(BaseModel):
    seq: int
    row: int
    col: int
    player: int


class GameState(BaseModel):
    id: str
    board_size: int
    mode: str
    difficulty: str
    status: str
    outcome: str | None = None
    winner: int | None = None
    turn: int
    board: list[list[int]]
    move_count: int
    players: dict[str, str | None]
    winning_line: list[list[int]] | None = None
    moves: list[MoveState] = []
    message: str | None = None
