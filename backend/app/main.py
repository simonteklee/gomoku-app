"""Gomoku API — REST (SR-02.3) + WebSocket för realtid (SR-02.4) + statisk frontend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import service
from .db import get_session, init_db
from .schemas import AcceptInviteRequest, GameState, InviteRequest, MoveRequest, NewGameRequest

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


class Rooms:
    """Enkel rumshantering för WebSocket-anslutningar."""

    def __init__(self) -> None:
        self.rooms: dict[str, list[WebSocket]] = {}

    async def join(self, game_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(game_id, []).append(websocket)

    def leave(self, game_id: str, websocket: WebSocket) -> None:
        if game_id in self.rooms and websocket in self.rooms[game_id]:
            self.rooms[game_id].remove(websocket)

    async def broadcast(self, game_id: str, payload: dict) -> None:
        for websocket in list(self.rooms.get(game_id, [])):
            try:
                await websocket.send_json(payload)
            except Exception:  # klienten kan ha försvunnit
                self.leave(game_id, websocket)


rooms = Rooms()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Gomoku API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _handle(error: service.GameError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/startpage")
def startpage() -> dict:
    """AC-06: de val som ska visas på startsidan."""
    return {"options": service.START_PAGE_OPTIONS}


@app.post("/api/games", response_model=GameState)
def new_game(request: NewGameRequest, session: Session = Depends(get_session)) -> dict:
    """AC-01: skapa parti med status pågående, färger enligt val, tomt bräde."""
    game = service.create_game(
        session,
        board_size=request.board_size,
        mode=request.mode,
        difficulty=request.difficulty,
        color=request.color,
        player_name=request.player_name,
    )
    return service.state_of(game)


@app.get("/api/games/{game_id}", response_model=GameState)
def get_game(game_id: str, session: Session = Depends(get_session)) -> dict:
    game = service.get_game(session, game_id)
    return service.state_of(game)


@app.post("/api/games/{game_id}/moves", response_model=GameState)
async def make_move(game_id: str, request: MoveRequest, session: Session = Depends(get_session)) -> dict:
    """AC-02-1 / AC-16 / AC-15 / AC-14: spelarens drag."""
    try:
        game = service.get_game(session, game_id)
        game = service.human_move(session, game, request.row, request.col)
    except service.GameError as error:
        raise _handle(error) from error
    state = service.state_of(game)
    await rooms.broadcast(game_id, {"type": "move", "state": state})
    return state


@app.post("/api/games/{game_id}/ai-move", response_model=GameState)
async def ai_move(game_id: str, session: Session = Depends(get_session)) -> dict:
    """AC-05: datorns drag beräknas på servern."""
    try:
        game = service.get_game(session, game_id)
        game = service.ai_turn(session, game)
    except service.GameError as error:
        raise _handle(error) from error
    state = service.state_of(game)
    await rooms.broadcast(game_id, {"type": "move", "state": state})
    return state


@app.post("/api/games/{game_id}/undo", response_model=GameState)
async def undo(game_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        game = service.get_game(session, game_id)
        game = service.undo(session, game)
    except service.GameError as error:
        raise _handle(error) from error
    state = service.state_of(game)
    await rooms.broadcast(game_id, {"type": "move", "state": state})
    return state


@app.post("/api/games/{game_id}/forfeit", response_model=GameState)
async def forfeit(game_id: str, session: Session = Depends(get_session)) -> dict:
    """AC-11: ge upp."""
    try:
        game = service.get_game(session, game_id)
        game = service.forfeit(session, game, game.human_color)
    except service.GameError as error:
        raise _handle(error) from error
    state = service.state_of(game)
    await rooms.broadcast(game_id, {"type": "finished", "state": state})
    return state


@app.post("/api/games/{game_id}/abort", response_model=GameState)
async def abort(game_id: str, session: Session = Depends(get_session)) -> dict:
    """AC-12: avsluta partiet och spara aktuell status."""
    try:
        game = service.get_game(session, game_id)
        game = service.abort(session, game)
    except service.GameError as error:
        raise _handle(error) from error
    state = service.state_of(game)
    await rooms.broadcast(game_id, {"type": "aborted", "state": state})
    return state


@app.post("/api/games/{game_id}/rematch", response_model=GameState)
def rematch(game_id: str, session: Session = Depends(get_session)) -> dict:
    """AC-13: spela igen med samma inställningar."""
    try:
        game = service.get_game(session, game_id)
        new_game = service.rematch(session, game)
    except service.GameError as error:
        raise _handle(error) from error
    return service.state_of(new_game)


@app.post("/api/invites")
def create_invite(request: InviteRequest, session: Session = Depends(get_session)) -> dict:
    """AC-03: skapa inbjudningslänk."""
    game = service.create_invite(
        session,
        board_size=request.board_size,
        color=request.color,
        player_name=request.player_name,
    )
    return service.invite_state(game, base_url="/")


@app.get("/api/invites/{token}")
def get_invite(token: str, session: Session = Depends(get_session)) -> dict:
    from sqlalchemy import select

    from .models import Game

    game = session.scalar(select(Game).where(Game.invite_token == token))
    if game is None:
        raise HTTPException(status_code=404, detail="Inbjudan är ogiltig")
    return service.invite_state(game, base_url="/")


@app.post("/api/invites/{token}/accept", response_model=GameState)
async def accept_invite(
    token: str, request: AcceptInviteRequest, session: Session = Depends(get_session)
) -> dict:
    """AC-03: vännen ansluter och partiet startar."""
    try:
        game = service.accept_invite(session, token, request.player_name)
    except service.GameError as error:
        raise _handle(error) from error
    state = service.state_of(game)
    await rooms.broadcast(game.id, {"type": "started", "state": state})
    return state


@app.post("/api/invites/{token}/cancel")
def cancel_invite(token: str, session: Session = Depends(get_session)) -> dict:
    """AC-03-04: inbjudaren avbryter inbjudan."""
    try:
        game = service.cancel_invite(session, token)
    except service.GameError as error:
        raise _handle(error) from error
    return {"game_id": game.id, "status": game.status, "cancelled": True}


@app.get("/api/history")
def get_history(player: str = Query(min_length=1), session: Session = Depends(get_session)) -> dict:
    """AC-17: spelhistorik för en lokal profil."""
    return {"player": player, "games": service.history(session, player)}


@app.websocket("/ws/games/{game_id}")
async def game_socket(websocket: WebSocket, game_id: str) -> None:
    await rooms.join(game_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # håll anslutningen öppen
    except WebSocketDisconnect:
        rooms.leave(game_id, websocket)


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
