"""Delade fixtures för acceptanstesterna.

Databasen pekas om till en temporär SQLite-fil INNAN appen importeras,
så testerna rör aldrig någon riktig databas.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

_TMP_DB = Path(tempfile.mkdtemp(prefix="gomoku-ac-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """Tom databas före varje test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def new_ai_game(client, **overrides):
    payload = {"board_size": 15, "mode": "ai", "difficulty": "normal", "color": "black", "player_name": "Simon"}
    payload.update(overrides)
    response = client.post("/api/games", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def new_local_game(client, board_size: int = 15, **overrides):
    payload = {"board_size": board_size, "mode": "local", "color": "black", "player_name": "Simon"}
    payload.update(overrides)
    response = client.post("/api/games", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def play(client, game_id: str, moves):
    """Spela en sekvens av (rad, kolumn) och returnera sista svaret."""
    last = None
    for row, col in moves:
        last = client.post(f"/api/games/{game_id}/moves", json={"row": row, "col": col})
        assert last.status_code == 200, last.text
    return last.json() if last else None


def expire_invite(game_id: str, minutes_ago: int = 16) -> None:
    """Flytta en inbjudans giltighetstid bakåt i tiden (AC-03-02)."""
    from datetime import datetime, timedelta, timezone

    from app.db import SessionLocal
    from app.models import Game

    with SessionLocal() as session:
        game = session.get(Game, game_id)
        game.expires_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        session.commit()
