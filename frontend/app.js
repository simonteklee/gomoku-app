// app.js — frontend-SPA som pratar med backend-API:t (REST + WebSocket).
// Ingen spellogik i klienten: allt (inkl. datorns drag) beräknas på servern.

const el = (id) => document.getElementById(id);
const screens = ["start", "config", "invite", "join", "game", "result", "rules"];

const state = {
  mode: "ai", // ai | online
  myName: "Spelare",
  color: "black",
  game: null,
  socket: null,
  inviteToken: null,
};

function show(name) {
  for (const s of screens) el(`screen-${s}`).classList.toggle("hidden", s !== name);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Fel ${response.status}`);
  return body;
}

function myColor(game) {
  if (!game) return 1;
  if (game.players.black === state.myName) return 1;
  if (game.players.white === state.myName) return 2;
  return state.color === "white" ? 2 : 1;
}

/* ---------- Startsidan (AC-06) ---------- */
function loadStartPage() {
  show("start");
}

/* ---------- Konfiguration (AC-01, AC-04) ---------- */
function openConfig(mode) {
  state.mode = mode;
  el("cfgDifficultyRow").classList.toggle("hidden", mode !== "ai");
  show("config");
}

async function startGame() {
  state.myName = el("cfgName").value.trim() || "Spelare";
  state.color = el("cfgColor").value;
  const payload = {
    board_size: Number(el("cfgSize").value),
    color: state.color,
    player_name: state.myName,
  };

  if (state.mode === "ai") {
    const game = await api("/api/games", {
      method: "POST",
      body: JSON.stringify({ ...payload, mode: "ai", difficulty: el("cfgDifficulty").value }),
    });
    await openGame(game);
    await maybeAiMove();
    return;
  }

  const invite = await api("/api/invites", { method: "POST", body: JSON.stringify(payload) });
  state.inviteToken = invite.token;
  el("inviteUrl").value = location.origin + invite.url;
  el("inviteWaiting").textContent = "Väntar på motståndaren …";
  show("invite");
  watchInvite();
}

function watchInvite() {
  const timer = setInterval(async () => {
    const info = await api(`/api/invites/${state.inviteToken}`);
    if (info.status === "in_progress") {
      clearInterval(timer);
      const game = await api(`/api/games/${info.game_id}`);
      await openGame(game);
    }
  }, 1000);
  el("inviteCancel").onclick = () => {
    clearInterval(timer);
    loadStartPage();
  };
  el("copyInvite").onclick = async () => {
    await navigator.clipboard.writeText(el("inviteUrl").value);
    el("inviteWaiting").textContent = "Länken är kopierad!";
  };
}

/* ---------- Anslut via inbjudningslänk (AC-03) ---------- */
async function joinInvite(token) {
  el("joinAccept").onclick = async () => {
    state.myName = el("joinName").value.trim() || "Spelare";
    const game = await api(`/api/invites/${token}/accept`, {
      method: "POST",
      body: JSON.stringify({ player_name: state.myName }),
    });
    await openGame(game);
  };
  show("join");
}

/* ---------- Spelplanen (AC-02, AC-05, AC-09) ---------- */
async function openGame(game) {
  state.game = game;
  show("game");
  renderBoard();
  renderStatus();
  connectSocket(game.id);
}

function connectSocket(gameId) {
  if (state.socket) state.socket.close();
  const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/games/${gameId}`;
  const socket = new WebSocket(url);
  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.state) applyState(payload.state);
  };
  state.socket = socket;
}

function applyState(game) {
  state.game = game;
  renderBoard();
  renderStatus();
}

function renderBoard() {
  const game = state.game;
  const board = el("board");
  board.style.gridTemplateColumns = `repeat(${game.board_size}, auto)`;
  board.innerHTML = "";
  for (let r = 0; r < game.board_size; r++) {
    for (let c = 0; c < game.board_size; c++) {
      const cell = document.createElement("button");
      cell.className = "cell";
      const value = game.board[r][c];
      if (value !== 0) {
        const stone = document.createElement("div");
        stone.className = "stone " + (value === 1 ? "black" : "white");
        cell.appendChild(stone);
        cell.classList.add("taken");
      }
      if (game.winning_line?.some(([wr, wc]) => wr === r && wc === c)) cell.classList.add("win");
      cell.onclick = () => playAt(r, c);
      board.appendChild(cell);
    }
  }
}

function renderStatus() {
  const game = state.game;
  el("gameInfo").textContent =
    `${game.players.black ?? "Svart"} (svart) mot ${game.players.white ?? "Vit"} (vit) — ` +
    `${game.move_count} drag`;
  const mine = myColor(game);
  const isMyTurn = game.turn === mine || game.mode === "local";
  el("gameTurn").innerHTML = game.status === "finished"
    ? "Partiet är avslutat"
    : `<b>${game.turn === 1 ? "Svart" : "Vit"}</b> tur${isMyTurn ? " (du)" : ""}`;
  el("btnUndo").disabled = game.move_count === 0;
}

async function playAt(row, col) {
  const game = state.game;
  if (!game || game.status !== "in_progress") return;
  if (game.mode === "ai" && game.turn !== myColor(game)) return;
  try {
    const updated = await api(`/api/games/${game.id}/moves`, {
      method: "POST",
      body: JSON.stringify({ row, col }),
    });
    applyState(updated);
    await maybeAiMove();
  } catch (error) {
    el("gameTurn").textContent = error.message;
  }
}

async function maybeAiMove() {
  const game = state.game;
  if (!game || game.mode !== "ai" || game.status !== "in_progress") return;
  if (game.turn === myColor(game)) return;
  const updated = await api(`/api/games/${game.id}/ai-move`, { method: "POST" });
  applyState(updated);
}

function showResult() {
  const game = state.game;
  const iWon = game.winner && game.winner === myColor(game);
  el("resultTitle").textContent = game.outcome === "draw"
    ? "Oavgjort"
    : iWon ? "Du vann!" : "Du förlorade";
  el("resultText").textContent = game.message || "";
  show("result");
}

/* ---------- Knappar ---------- */
el("optAi").onclick = () => openConfig("ai");
el("optFriend").onclick = () => openConfig("online");
el("optRules").onclick = () => show("rules");
el("cfgStart").onclick = () => startGame().catch((e) => (el("cfgHint").textContent = e.message));
el("cfgCancel").onclick = () => loadStartPage();
el("rulesBack").onclick = () => loadStartPage();
el("btnRematch").onclick = async () => {
  const game = await api(`/api/games/${state.game.id}/rematch`, { method: "POST" });
  await openGame(game);
  await maybeAiMove();
};
el("btnMenu").onclick = () => loadStartPage();
el("btnUndo").onclick = async () => {
  applyState(await api(`/api/games/${state.game.id}/undo`, { method: "POST" }));
};
el("btnForfeit").onclick = async () => {
  applyState(await api(`/api/games/${state.game.id}/forfeit`, { method: "POST" }));
  showResult();
};
el("btnAbort").onclick = async () => {
  await api(`/api/games/${state.game.id}/abort`, { method: "POST" });
  loadStartPage();
};

// resultatskärmen dyker upp automatiskt när partiet är avgjort
const originalApply = applyState;
applyState = function (game) {
  originalApply(game);
  if (game.status === "finished") showResult();
};

/* ---------- Start ---------- */
const params = new URLSearchParams(location.search);
if (params.get("invite")) joinInvite(params.get("invite"));
else loadStartPage();
