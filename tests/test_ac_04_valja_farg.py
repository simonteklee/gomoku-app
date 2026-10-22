"""AC-04 — Välja färg (UC-04).

Given att spelaren är i konfigurationssidan och partiet inte har startat
When spelaren väljer svart eller vit
Then tilldelas spelaren den valda färgen
And tilldelas motståndaren den andra färgen
And visas båda spelarnas färger i konfigurationssidan
And framgår det att svart gör första draget
And låses färgvalet när partiet startar
And går att skilja pjäser åt på enbart färg
"""


def test_vald_farg_tilldelas_spelaren(client):
    response = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "color": "white", "player_name": "Simon"},
    )
    game = response.json()

    # Then: spelaren får den valda färgen ...
    assert game["players"]["white"] == "Simon"
    # And: motståndaren får den andra färgen
    assert game["players"]["black"] == "Datorn"
    # And: båda färgerna syns i partiet (konfigurationen)
    assert set(game["players"].keys()) == {"black", "white"}
    # And: svart gör första draget
    assert game["turn"] == 1


def test_svart_borjar_aven_nar_spelaren_valt_svart(client):
    game = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "color": "black", "player_name": "Simon"},
    ).json()
    assert game["players"]["black"] == "Simon"
    assert game["players"]["white"] == "Datorn"
    assert game["turn"] == 1


def test_fargvalet_ar_last_nar_partiet_startat(client):
    game = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "color": "black", "player_name": "Simon"},
    ).json()

    # Det finns inget API for att andra ett startat partis färger
    assert client.put(f"/api/games/{game['id']}", json={"color": "white"}).status_code == 405
    assert client.patch(f"/api/games/{game['id']}", json={"color": "white"}).status_code == 405
    assert client.delete(f"/api/games/{game['id']}").status_code == 405

    # ...och partiet är oförändrat
    unchanged = client.get(f"/api/games/{game['id']}").json()
    assert unchanged["players"]["black"] == "Simon"
    assert unchanged["turn"] == 1


def test_ingen_farg_vald_tilldelas_slumpmassigt(client):
    """AC-04-02: väljer spelaren ingen färg slumpas den."""
    seen = set()
    for _ in range(20):
        game = client.post(
            "/api/games", json={"board_size": 15, "mode": "ai", "player_name": "Simon"}
        ).json()
        if game["players"]["black"] == "Simon":
            seen.add("black")
        else:
            seen.add("white")
        # motståndaren får alltid den andra färgen
        assert "Datorn" in (game["players"]["black"], game["players"]["white"])
    assert seen == {"black", "white"}


def test_pjaser_gar_att_skilja_pa_farg(client):
    """Brädet använder två olika värden för svart och vit — enbart färg skiljer."""
    game = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "local", "color": "black", "player_name": "Simon"},
    ).json()
    client.post(f"/api/games/{game['id']}/moves", json={"row": 7, "col": 7})  # svart = 1
    state = client.post(f"/api/games/{game['id']}/moves", json={"row": 7, "col": 8}).json()  # vit = 2

    assert state["board"][7][7] == 1
    assert state["board"][7][8] == 2
