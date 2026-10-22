"""Ren spellogik för Gomoku — inga beroenden, ingen databas, ingen HTTP.

Hålls medvetet separerad från API:t så att reglerna kan enhetstestas för sig.
"""

from __future__ import annotations

EMPTY = 0
BLACK = 1  # svart börjar alltid
WHITE = 2

DIRS = ((0, 1), (1, 0), (1, 1), (1, -1))


class Board:
    def __init__(self, size: int = 15) -> None:
        self.size = size
        self.cells = [[EMPTY] * size for _ in range(size)]

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def at(self, r: int, c: int) -> int:
        return self.cells[r][c] if self.in_bounds(r, c) else EMPTY

    def place(self, r: int, c: int, player: int) -> bool:
        """Lägg en sten. False om rutan är upptagen eller utanför brädet."""
        if not self.in_bounds(r, c) or self.cells[r][c] != EMPTY:
            return False
        self.cells[r][c] = player
        return True

    def remove(self, r: int, c: int) -> None:
        self.cells[r][c] = EMPTY

    def winning_line(self, r: int, c: int) -> list[tuple[int, int]] | None:
        """Returnerar raden (>= 5 rutor) om stenen i (r, c) ger fem i rad."""
        player = self.at(r, c)
        if player == EMPTY:
            return None
        for dr, dc in DIRS:
            line = [(r, c)]
            for sign in (1, -1):
                rr, cc = r + dr * sign, c + dc * sign
                while self.at(rr, cc) == player:
                    if sign == 1:
                        line.append((rr, cc))
                    else:
                        line.insert(0, (rr, cc))
                    rr += dr * sign
                    cc += dc * sign
            if len(line) >= 5:
                return line
        return None

    def find_winner(self) -> tuple[int, list[tuple[int, int]]] | None:
        for r in range(self.size):
            for c in range(self.size):
                if self.cells[r][c] == EMPTY:
                    continue
                line = self.winning_line(r, c)
                if line:
                    return self.cells[r][c], line
        return None

    def is_full(self) -> bool:
        return all(cell != EMPTY for row in self.cells for cell in row)

    def empty_cells(self) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r in range(self.size)
            for c in range(self.size)
            if self.cells[r][c] == EMPTY
        ]

    @classmethod
    def from_moves(cls, size: int, moves: list[tuple[int, int, int]]) -> "Board":
        board = cls(size)
        for r, c, player in moves:
            board.place(r, c, player)
        return board


def next_player(player: int) -> int:
    return WHITE if player == BLACK else BLACK


def _opponent(player: int) -> int:
    return WHITE if player == BLACK else BLACK


def _find_winning_move(board: Board, player: int) -> tuple[int, int] | None:
    for r, c in board.empty_cells():
        board.place(r, c, player)
        win = board.winning_line(r, c)
        board.remove(r, c)
        if win:
            return r, c
    return None


def _score_cell(board: Board, r: int, c: int, player: int, radius: int = 2) -> float:
    score = 0.0
    opp = _opponent(player)
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            v = board.at(r + dr, c + dc)
            if v == EMPTY:
                continue
            weight = radius + 1 - max(abs(dr), abs(dc))  # 3..1
            score += weight * (1.2 if v == player else 1.0)
    mid = (board.size - 1) / 2
    score -= (abs(r - mid) + abs(c - mid)) * 0.05
    return score


def ai_move(board: Board, player: int, difficulty: str = "normal") -> tuple[int, int] | None:
    """Datorns drag. difficulty: easy | normal | hard."""
    empties = board.empty_cells()
    if not empties:
        return None

    if difficulty == "easy":
        # Determinism i tester: välj första lediga i tur och ordning (samma som slump är opålitligt)
        return empties[len(empties) // 2]

    win = _find_winning_move(board, player)
    if win:
        return win

    block = _find_winning_move(board, _opponent(player))
    if block:
        return block

    best = None
    best_score = float("-inf")
    for r, c in empties:
        score = _score_cell(board, r, c, player)
        if difficulty == "hard":
            board.place(r, c, player)
            if _find_winning_move(board, _opponent(player)):
                score -= 100
            board.remove(r, c)
        if score > best_score:
            best_score = score
            best = (r, c)
    return best
