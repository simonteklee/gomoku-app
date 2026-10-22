"""AC-12 — Avsluta ett parti (UC-12).

Given att ett parti pågår
When spelaren väljer att avsluta partiet och bekräftar
Then ska systemet spara partiets aktuella status
And avsluta partiet
And återföra spelaren till menyn
And informera motståndaren om att partiet har avslutats
"""

from conftest import new_local_game


def test_avsluta_partiet_sparar_status(client):
    game = new_local_game(client)
    game_id = game["id"]
    before = client.post(f"/api/games/{game_id}/moves", json={"row": 7, "col": 7}).json()
    before = client.post(f"/api/games/{game_id}/moves", json={"row": 8, "col": 8}).json()

    response = client.post(f"/api/games/{game_id}/abort")
    assert response.status_code == 200
    state = response.json()

    # Then: partiets aktuella status sparas (dragen finns kvar)
    assert state["move_count"] == before["move_count"] == 2
    assert state["board"][7][7] == 1
    assert state["board"][8][8] == 2

    # And: partiet avslutas
    assert state["status"] == "finished"
    assert state["outcome"] == "aborted"

    # And: inga fler drag kan göras
    blocked = client.post(f"/api/games/{game_id}/moves", json={"row": 0, "col": 0})
    assert blocked.status_code == 409


def test_motstandaren_informeras_via_websocket(client):
    invite = client.post(
        "/api/invites", json={"board_size": 15, "color": "black", "player_name": "Simon"}
    ).json()
    game = client.post(
        f"/api/invites/{invite['token']}/accept", json={"player_name": "Fanny"}
    ).json()

    with client.websocket_connect(f"/ws/games/{game['id']}") as socket:
        client.post(f"/api/games/{game['id']}/abort")
        message = socket.receive_json()

    assert message["type"] == "aborted"
    assert message["state"]["status"] == "finished"
