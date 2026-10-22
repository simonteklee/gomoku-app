"""AC-14 — Oavgjort (UC-14).

Given att ett parti pågår och endast en ledig position finns kvar
And ingen spelare har fem i rad
When en spelare gör det sista giltiga draget utan att få fem i rad
Then ska systemet avsluta partiet som oavgjort
And visa ett meddelande om oavgjort
And förhindra att fler drag görs

Brädet är 5×5 och 24 av 25 rutor fylls med en känd ställning som inte har
fem i rad (kontrollerat för alla riktningar). Sista rutan är (0, 0).
"""

from conftest import new_local_game, play

# 0 = ledig (sista draget), 1 = svart, 2 = vit
NEAR_FULL_BOARD = [
    [0, 1, 1, 2, 2],
    [2, 1, 2, 1, 1],
    [1, 1, 2, 2, 1],
    [1, 2, 1, 2, 1],
    [2, 2, 2, 2, 1],
]


def test_sista_draget_utan_fem_i_rad_ger_oavgjort(client):
    game = new_local_game(client, board_size=5)
    game_id = game["id"]

    black = [(r, c) for r in range(5) for c in range(5) if NEAR_FULL_BOARD[r][c] == 1]
    white = [(r, c) for r in range(5) for c in range(5) if NEAR_FULL_BOARD[r][c] == 2]
    assert len(black) == 12 and len(white) == 12
    assert NEAR_FULL_BOARD[0][0] == 0  # enda lediga rutan

    moves = []
    for i in range(12):  # svart börjar, varannan
        moves.append(black[i])
        moves.append(white[i])

    state = play(client, game_id, moves)
    assert state["status"] == "in_progress"
    assert state["move_count"] == 24
    assert state["winning_line"] is None

    # When: det sista giltiga draget görs (svart på (0, 0)) utan fem i rad
    final = client.post(f"/api/games/{game_id}/moves", json={"row": 0, "col": 0}).json()

    # Then: partiet avslutas som oavgjort
    assert final["status"] == "finished"
    assert final["outcome"] == "draw"
    assert final["winner"] is None
    # And: ett meddelande om oavgjort visas
    assert final["message"] == "Oavgjort"

    # And: inga fler drag kan göras
    blocked = client.post(f"/api/games/{game_id}/moves", json={"row": 0, "col": 1})
    assert blocked.status_code == 409
