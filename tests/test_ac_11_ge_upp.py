"""AC-11 — Ge upp (UC-11).

Given att ett parti pågår
When spelaren väljer "Ge upp" och bekräftar
Then ska systemet avsluta partiet
And registrera förlust för spelaren
And registrera vinst för motståndaren
And visa resultatet med vinnare och förlorare
And förhindra att fler drag görs
"""

from conftest import new_local_game


def test_ge_upp_avslutar_partiet(client):
    game = new_local_game(client)
    game_id = game["id"]
    client.post(f"/api/games/{game_id}/moves", json={"row": 7, "col": 7})

    response = client.post(f"/api/games/{game_id}/forfeit")
    assert response.status_code == 200
    state = response.json()

    # Then: partiet avslutas
    assert state["status"] == "finished"
    # And: förlust för spelaren (svart) ...
    assert state["outcome"] == "forfeit"
    # And: ...och vinst för motståndaren (vit)
    assert state["winner"] == 2
    # And: resultatet visas (vinnare/förlorare)
    assert state["message"]

    # And: inga fler drag kan göras
    blocked = client.post(f"/api/games/{game_id}/moves", json={"row": 0, "col": 0})
    assert blocked.status_code == 409
