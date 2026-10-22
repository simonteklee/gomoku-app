"""AC-16 — Vin (UC-16).

Given att ett parti pågår
And det är spelarens tur
And spelaren har fyra stenar i rad
When spelaren gör ett giltigt drag och får fem i rad
Then ska systemet avsluta partiet
And registrera vinst för spelaren
And markera den vinnande raden
And visa ett meddelande om att spelaren har vunnit
And förhindra att fler drag görs
"""

from conftest import new_local_game, play


def test_spelaren_far_fem_i_rad_ger_vinst(client):
    game = new_local_game(client)
    game_id = game["id"]

    moves = [
        (7, 3), (0, 0),
        (7, 4), (0, 1),
        (7, 5), (0, 2),
        (7, 6), (0, 3),  # svart har fyra i rad
        (7, 7),          # svart får fem i rad
    ]
    state = play(client, game_id, moves)

    # Then: systemet avslutar partiet
    assert state["status"] == "finished"
    # And: vinst registreras för spelaren (svart)
    assert state["winner"] == 1
    assert state["outcome"] == "black_wins"
    # And: den vinnande raden markeras
    assert state["winning_line"] is not None
    line = {tuple(cell) for cell in state["winning_line"]}
    assert {(7, 3), (7, 4), (7, 5), (7, 6), (7, 7)} <= line
    # And: ett meddelande visas
    assert "Svart" in state["message"]

    # And: inga fler drag kan göras
    blocked = client.post(f"/api/games/{game_id}/moves", json={"row": 12, "col": 12})
    assert blocked.status_code == 409


def test_vinst_aven_diagonalt(client):
    game = new_local_game(client)
    game_id = game["id"]

    moves = [
        (0, 0), (1, 0),
        (1, 1), (2, 0),
        (2, 2), (3, 0),
        (3, 3), (4, 0),
        (4, 4),  # diagonalen (0,0)-(4,4) ger fem i rad
    ]
    state = play(client, game_id, moves)
    assert state["status"] == "finished"
    assert state["winner"] == 1
