"""AC-03 — Bjud in en vän (UC-03).

Given att spelaren är på startsidan och har ett synligt spelarnamn
When spelaren väljer Spela mot vän
Then skapas en inbjudningslänk inom 1 sekund
And visas länken med möjlighet att kopiera eller dela den
And visas ett väntläge för spelaren
And när motståndaren öppnar länken startar partiet med båda spelarna anslutna
And visas båda spelarnas namn för varandra
And syns ett drag hos motståndaren inom 0,5 sekunder
"""

import time

from conftest import expire_invite


def test_skapa_inbjudan(client):
    started = time.perf_counter()
    response = client.post(
        "/api/invites",
        json={"board_size": 15, "color": "black", "player_name": "Simon"},
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    invite = response.json()

    # Then: en inbjudningslänk skapas inom 1 sekund
    assert invite["url"] and invite["token"]
    assert elapsed < 1.0, f"länken tog {elapsed:.2f}s"

    # And: länken kan delas (går att slå upp igen = delbar/kopierbar)
    again = client.get(f"/api/invites/{invite['token']}")
    assert again.status_code == 200
    assert again.json()["url"] == invite["url"]

    # And: ett väntläge visas för inbjudaren
    assert invite["waiting"] is True
    assert invite["status"] == "pending"
    assert invite["host_name"] == "Simon"


def test_motstandaren_ansluter_och_partiet_startar(client):
    invite = client.post(
        "/api/invites", json={"board_size": 15, "color": "black", "player_name": "Simon"}
    ).json()

    response = client.post(
        f"/api/invites/{invite['token']}/accept", json={"player_name": "Fanny"}
    )
    assert response.status_code == 200
    game = response.json()

    # Then: partiet startar med båda spelarna anslutna
    assert game["status"] == "in_progress"
    # And: båda spelarnas namn visas för varandra
    assert game["players"]["black"] == "Simon"
    assert game["players"]["white"] == "Fanny"


def test_drag_syns_direkt_for_motstandaren(client):
    invite = client.post(
        "/api/invites", json={"board_size": 15, "color": "black", "player_name": "Simon"}
    ).json()
    game = client.post(
        f"/api/invites/{invite['token']}/accept", json={"player_name": "Fanny"}
    ).json()

    # Motståndaren (vit) lyssnar på partiet över WebSocket
    with client.websocket_connect(f"/ws/games/{game['id']}") as socket:
        started = time.perf_counter()
        client.post(f"/api/games/{game['id']}/moves", json={"row": 7, "col": 7})
        message = socket.receive_json()
        elapsed = time.perf_counter() - started

    assert message["type"] == "move"
    assert message["state"]["board"][7][7] == 1
    assert elapsed < 0.5, f"draget syntes efter {elapsed:.3f}s"


def test_ogiltig_inbjudningslank_avvisas(client):
    """AC-03-03: en länk som inte är giltig."""
    response = client.post("/api/invites/finnsinte123/accept", json={"player_name": "Fanny"})
    assert response.status_code == 404
    assert "ogiltig" in response.json()["detail"].lower()


def test_inbjudningslank_forfaller_efter_15_minuter(client):
    """AC-03-02: länken förfaller."""
    invite = client.post(
        "/api/invites", json={"board_size": 15, "color": "black", "player_name": "Simon"}
    ).json()
    expire_invite(invite["game_id"])

    response = client.post(
        f"/api/invites/{invite['token']}/accept", json={"player_name": "Fanny"}
    )

    # Then: anslutningsförsöket avvisas och personen informeras
    assert response.status_code == 410
    assert "förfallit" in response.json()["detail"].lower()
    # And: inget parti startas
    game = client.get(f"/api/games/{invite['game_id']}").json()
    assert game["status"] == "expired"
    assert game["move_count"] == 0


def test_inbjudaren_kan_avbryta_inbjudan(client):
    """AC-03-04: inbjudaren avbryter."""
    invite = client.post(
        "/api/invites", json={"board_size": 15, "color": "black", "player_name": "Simon"}
    ).json()

    response = client.post(f"/api/invites/{invite['token']}/cancel")
    assert response.status_code == 200
    assert response.json()["cancelled"] is True

    # And: ingen kan ansluta med den avbrutna länken
    blocked = client.post(f"/api/invites/{invite['token']}/accept", json={"player_name": "Fanny"})
    assert blocked.status_code in (404, 410)
    # And: inget parti startas
    assert client.get(f"/api/games/{invite['game_id']}").json()["status"] == "cancelled"
