"""AC-15 — Förlust (UC-15).

Given att ett parti pågår
And motståndaren har fyra stenar i rad
When motståndaren gör ett giltigt drag och får fem i rad
Then ska systemet avsluta partiet
And registrera förlust för spelaren
And markera den vinnande raden
And visa ett meddelande om att spelaren har förlorat
And förhindra att fler drag görs
"""

from conftest import new_local_game, play


def test_motstandaren_far_fem_i_rad_ger_forlust(client):
    game = new_local_game(client)
    game_id = game["id"]

    # Spelaren (svart) lägger ofarliga stenar, motståndaren (vit) bygger fem i rad
    moves = [
        (0, 0), (7, 3),  # svart, vit
        (2, 0), (7, 4),
        (4, 0), (7, 5),
        (6, 0), (7, 6),  # vit har nu fyra i rad
        (8, 0), (7, 7),  # vit får fem i rad
    ]
    state = play(client, game_id, moves)

    # Then: systemet avslutar partiet
    assert state["status"] == "finished"
    # And: förlust registreras för spelaren (svart) => vit vinner
    assert state["winner"] == 2
    assert state["outcome"] == "white_wins"
    # And: den vinnande raden markeras
    assert state["winning_line"] is not None
    line = {tuple(cell) for cell in state["winning_line"]}
    assert len(line) >= 5
    assert {(7, 3), (7, 4), (7, 5), (7, 6), (7, 7)} <= line
    # And: ett meddelande visas
    assert "Vit" in state["message"]

    # And: inga fler drag kan göras
    blocked = client.post(f"/api/games/{game_id}/moves", json={"row": 12, "col": 12})
    assert blocked.status_code == 409
