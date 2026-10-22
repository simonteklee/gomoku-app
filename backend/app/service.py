"""Användningsfalls-logik: skapa parti, göra drag, datorns drag, ge upp, spara, bjud in.

AI:n körs här på serversidan (SR-04.4) — klienten skickar bara dragförfrågningar.
"""

from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import domain
from .models import Game, Move

INVITE_TTL_MINUTES = 15

START_PAGE_OPTIONS = ["Spela mot datorn", "Spela mot vän", "Visa spelregler"]

OUTCOME_TEXT = {
    "black_wins": "Svart vann",
    "white_wins": "Vit vann",
    "draw": "Oavgjort",
    "forfeit": "Vinst på walkover",
    "aborted": "Partiet avslutades",
}


class GameError(Exception):
    """Fel som ska bli ett HTTP-svar."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now():
    return datetime.now(timezone.utc)


def color_name(player: int) -> str:
    return "black" if player == domain.BLACK else "white"


def color_value(name: str) -> int:
    return domain.BLACK if name == "black" else domain.WHITE


def board_of(game: Game) -> domain.Board:
    return domain.Board.from_moves(game.board_size, [(m.row, m.col, m.player) for m in game.moves])


def state_of(game: Game) -> dict:
    board = board_of(game)
    win = board.find_winner()
    return {
        "id": game.id,
        "board_size": game.board_size,
        "mode": game.mode,
        "difficulty": game.difficulty,
        "status": game.status,
        "outcome": game.outcome,
        "winner": game.winner,
        "turn": game.turn,
        "board": board.cells,
        "move_count": len(game.moves),
        "players": {"black": game.player_black, "white": game.player_white},
        "winning_line": [list(cell) for cell in win[1]] if win else None,
        "moves": [
            {"seq": m.seq, "row": m.row, "col": m.col, "player": m.player} for m in game.moves
        ],
        "message": OUTCOME_TEXT.get(game.outcome or "", None),
    }


def create_game(
    session: Session,
    *,
    board_size: int = 15,
    mode: str = "ai",
    difficulty: str = "normal",
    color: str | None = "black",
    player_name: str | None = None,
) -> Game:
    # AC-04-02: väljs ingen färg tilldelas spelaren svart eller vit slumpmässigt
    if color not in ("black", "white"):
        color = random.choice(("black", "white"))
    human_color = color_value(color)
    game = Game(
        board_size=board_size,
        mode=mode,
        difficulty=difficulty,
        status="in_progress",
        human_color=human_color,
        turn=domain.BLACK,  # svart börjar alltid
        player_black=player_name if human_color == domain.BLACK else ("Datorn" if mode == "ai" else None),
        player_white=player_name if human_color == domain.WHITE else ("Datorn" if mode == "ai" else None),
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def get_game(session: Session, game_id: str) -> Game:
    game = session.get(Game, game_id)
    if game is None:
        raise GameError("Partiet hittades inte", status_code=404)
    return game


def _finish(game: Game, outcome: str, winner: int | None) -> None:
    game.status = "finished"
    game.outcome = outcome
    game.winner = winner
    game.updated_at = _now()


def _check_after_move(game: Game, board: domain.Board) -> None:
    win = board.find_winner()
    if win:
        player, _line = win
        outcome = "black_wins" if player == domain.BLACK else "white_wins"
        _finish(game, outcome, player)
        return
    if board.is_full():
        _finish(game, "draw", None)


def make_move(session: Session, game: Game, row: int, col: int, as_player: int | None = None) -> Game:
    if game.status == "paused":
        raise GameError("Partiet är pausat", status_code=409)
    if game.status != "in_progress":
        raise GameError("Partiet är inte igång", status_code=409)

    player = game.turn if as_player is None else as_player
    if player != game.turn:
        raise GameError("Det är inte spelarens tur", status_code=409)
    if not (0 <= row < game.board_size and 0 <= col < game.board_size):
        raise GameError("Rutan ligger utanför brädet", status_code=400)

    board = board_of(game)
    if not board.place(row, col, player):
        raise GameError("Rutan är upptagen", status_code=409)

    session.add(Move(game_id=game.id, seq=len(game.moves) + 1, row=row, col=col, player=player))
    _check_after_move(game, board)
    if game.status == "in_progress":
        game.turn = domain.next_player(player)
    game.updated_at = _now()
    session.commit()
    session.refresh(game)
    return game


def human_move(session: Session, game: Game, row: int, col: int) -> Game:
    """Drag från människan. I AI-läge måste det vara människans färg och tur."""
    if game.mode == "ai" and game.turn != game.human_color:
        raise GameError("Det är datorns tur", status_code=409)
    return make_move(session, game, row, col)


def _compute_ai_move(board: domain.Board, player: int, difficulty: str, time_limit: float = 3.0):
    """AC-05-06: försök en gång till om första försöket tar för lång tid."""
    last_error: Exception | None = None
    for _attempt in range(2):
        started = time.perf_counter()
        try:
            move = domain.ai_move(board, player, difficulty)
        except Exception as error:  # tekniskt fel (AC-05-05)
            last_error = error
            continue
        if move is not None and time.perf_counter() - started <= time_limit:
            return move
    if last_error is not None:
        raise last_error
    raise TimeoutError("datorn beräknade inte sitt drag inom tidsgränsen")


def ai_turn(session: Session, game: Game) -> Game:
    """Låt datorn göra sitt drag (serverns AI, SR-04.4)."""
    if game.mode != "ai":
        raise GameError("Partiet spelas inte mot datorn", status_code=409)
    # Ett pausat parti får försöka igen (AC-05-07)
    if game.status not in ("in_progress", "paused"):
        raise GameError("Partiet är inte igång", status_code=409)
    if game.turn == game.human_color:
        raise GameError("Det är spelarens tur", status_code=409)

    board = board_of(game)
    try:
        move = _compute_ai_move(board, game.turn, game.difficulty)
    except Exception as error:
        # AC-05-05/07: visa fel, pausa partiet, bevara partitillståndet
        game.status = "paused"
        game.updated_at = _now()
        session.commit()
        raise GameError(
            "Datorns drag kunde inte beräknas. Partiet är pausat — försök igen eller avsluta.",
            status_code=503,
        ) from error
    if move is None:
        raise GameError("Inga lediga rutor", status_code=409)
    if game.status == "paused":
        game.status = "in_progress"
    return make_move(session, game, move[0], move[1], as_player=game.turn)


def undo(session: Session, game: Game) -> Game:
    if not game.moves:
        raise GameError("Inget drag att ångra", status_code=409)

    steps = 2 if game.mode == "ai" and len(game.moves) > 1 else 1
    for _ in range(steps):
        last = game.moves[-1]
        session.delete(last)
        game.moves.remove(last)
        game.turn = last.player
    game.status = "in_progress"
    game.outcome = None
    game.winner = None
    game.updated_at = _now()
    session.commit()
    session.refresh(game)
    return game


def forfeit(session: Session, game: Game, player: int) -> Game:
    """Ge upp (AC-11): förlust för spelaren, vinst för motståndaren."""
    if game.status != "in_progress":
        raise GameError("Partiet är inte igång", status_code=409)
    _finish(game, "forfeit", domain.next_player(player))
    session.commit()
    session.refresh(game)
    return game


def abort(session: Session, game: Game) -> Game:
    """Avsluta ett parti (AC-12): spara aktuell status och avsluta."""
    if game.status == "finished":
        raise GameError("Partiet är redan avslutat", status_code=409)
    game.saved = True
    _finish(game, "aborted", None)
    session.commit()
    session.refresh(game)
    return game


def rematch(session: Session, game: Game) -> Game:
    """Spela igen (AC-13): nytt parti med samma inställningar."""
    if game.status != "finished":
        raise GameError("Partiet är inte avslutat", status_code=409)
    new_game = create_game(
        session,
        board_size=game.board_size,
        mode=game.mode,
        difficulty=game.difficulty,
        color=color_name(game.human_color),
        player_name=game.player_black if game.human_color == domain.BLACK else game.player_white,
    )
    return new_game


def create_invite(
    session: Session, *, board_size: int = 15, color: str | None = "black", player_name: str
) -> Game:
    """Bjuda in en vän (AC-03-01): parti i väntläge med unik inbjudningslänk som förfaller."""
    if color not in ("black", "white"):
        color = random.choice(("black", "white"))
    human_color = color_value(color)
    now = _now()
    game = Game(
        board_size=board_size,
        mode="online",
        status="pending",
        human_color=human_color,
        turn=domain.BLACK,
        invite_token=uuid.uuid4().hex[:16],
        expires_at=now + timedelta(minutes=INVITE_TTL_MINUTES),
        player_black=player_name if human_color == domain.BLACK else None,
        player_white=player_name if human_color == domain.WHITE else None,
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def invite_state(game: Game, base_url: str = "") -> dict:
    join_suffix = f"/?invite={game.invite_token}"
    return {
        "game_id": game.id,
        "token": game.invite_token,
        "url": f"{base_url}{join_suffix}" if game.invite_token else None,
        "board_size": game.board_size,
        "host_name": game.player_black or game.player_white,
        "status": game.status,
        "waiting": game.status == "pending",
        "expires_at": game.expires_at.isoformat() if game.expires_at else None,
    }


def _expired(game: Game) -> bool:
    if game.expires_at is None:
        return False
    expires = game.expires_at
    if expires.tzinfo is None:  # SQLite tappar tidszonen
        expires = expires.replace(tzinfo=timezone.utc)
    return _now() > expires


def accept_invite(session: Session, token: str, player_name: str) -> Game:
    game = session.scalar(select(Game).where(Game.invite_token == token))
    # AC-03-03: ogiltig länk
    if game is None:
        raise GameError("Inbjudningslänken är ogiltig", status_code=404)
    # AC-03-02: länken har förfallit efter 15 minuter
    if game.status == "pending" and _expired(game):
        game.status = "expired"
        game.invite_token = None
        session.commit()
        raise GameError("Inbjudningslänken har förfallit", status_code=410)
    # AC-03-04: inbjudan är avbruten
    if game.status == "cancelled":
        raise GameError("Inbjudan är avbruten", status_code=410)
    if game.status != "pending":
        raise GameError("Inbjudan har redan använts", status_code=409)

    if game.player_black is None:
        game.player_black = player_name
    else:
        game.player_white = player_name
    game.status = "in_progress"
    game.invite_token = None
    game.updated_at = _now()
    session.commit()
    session.refresh(game)
    return game


def cancel_invite(session: Session, token: str) -> Game:
    """AC-03-04: inbjudaren avbryter — länken blir ogiltig."""
    game = session.scalar(select(Game).where(Game.invite_token == token))
    if game is None:
        raise GameError("Inbjudningslänken är ogiltig", status_code=404)
    game.status = "cancelled"
    game.invite_token = None
    game.updated_at = _now()
    session.commit()
    session.refresh(game)
    return game


def history(session: Session, player_name: str) -> list[dict]:
    """Spelhistorik för en lokal profil (AC-17)."""
    games = session.scalars(
        select(Game)
        .where(Game.status == "finished")
        .where((Game.player_black == player_name) | (Game.player_white == player_name))
        .order_by(Game.created_at.desc())
    ).all()
    rows = []
    for game in games:
        player_is_black = game.player_black == player_name
        opponent = game.player_white if player_is_black else game.player_black
        if game.winner is None:
            result = "oavgjort" if game.outcome == "draw" else game.outcome
        elif player_is_black:
            result = "vinst" if game.winner == domain.BLACK else "förlust"
        else:
            result = "vinst" if game.winner == domain.WHITE else "förlust"
        rows.append(
            {
                "game_id": game.id,
                "date": game.created_at.isoformat() if game.created_at else None,
                "opponent": opponent,
                "board_size": game.board_size,
                "result": result,
                "outcome": game.outcome,
            }
        )
    return rows
