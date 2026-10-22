"""AC-05 — Spela mot datorn (UC-05).

Given att spelaren är på startsidan
When spelaren väljer "Spela mot datorn" och en svårighetsgrad
Then startas ett parti mot datorn
And gör datorn sitt drag inom 3 sekunder
And turas spelaren och datorn om att göra drag
And kontrollerar efter varje drag om någon har fem i rad
And avslutas partiet när någon får fem i rad eller brädet blir fullt
And visas resultatet
"""

import time


def test_partiet_startas_mot_datorn(client):
    game = client.post(
        "/api/games",
        json={
            "board_size": 15,
            "mode": "ai",
            "difficulty": "normal",
            "color": "black",
            "player_name": "Simon",
        },
    ).json()
    assert game["mode"] == "ai"
    assert game["status"] == "in_progress"
    assert game["difficulty"] == "normal"


def test_datorn_gor_sitt_drag_inom_tre_sekunder(client):
    # Spelaren väljer vit => datorn (svart) börjar och måste göra första draget
    game = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "difficulty": "normal", "color": "white", "player_name": "Simon"},
    ).json()

    started = time.perf_counter()
    response = client.post(f"/api/games/{game['id']}/ai-move")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    state = response.json()
    assert state["move_count"] == 1
    assert elapsed < 3.0, f"datorn tog {elapsed:.2f}s"


def test_spelare_och_dator_turas_om(client):
    game = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "difficulty": "easy", "color": "black", "player_name": "Simon"},
    ).json()
    game_id = game["id"]

    after_human = client.post(f"/api/games/{game_id}/moves", json={"row": 7, "col": 7}).json()
    assert after_human["turn"] == 2  # nu är det datorns tur

    after_ai = client.post(f"/api/games/{game_id}/ai-move").json()
    assert after_ai["move_count"] == 2
    assert after_ai["turn"] == 1  # tillbaka till spelaren


def test_partiet_avslutas_nar_nagon_far_fem_i_rad_eller_bradet_blir_fullt(client):
    """Litet bräde (5×5) så partiet garanterat tar slut inom rimigt antal drag."""
    game = client.post(
        "/api/games",
        json={"board_size": 5, "mode": "ai", "difficulty": "normal", "color": "black", "player_name": "Simon"},
    ).json()
    game_id = game["id"]
    state = game

    while state["status"] == "in_progress" and state["move_count"] < 25:
        if state["turn"] == 1:
            spot = next(
                (r, c)
                for r in range(5)
                for c in range(5)
                if state["board"][r][c] == 0
            )
            state = client.post(
                f"/api/games/{game_id}/moves", json={"row": spot[0], "col": spot[1]}
            ).json()
        else:
            started = time.perf_counter()
            state = client.post(f"/api/games/{game_id}/ai-move").json()
            assert time.perf_counter() - started < 3.0

    # Then: partiet avslutas med ett resultat
    assert state["status"] == "finished"
    assert state["outcome"] in {"black_wins", "white_wins", "draw"}
    assert state["message"]  # resultatet visas

    # And: inga fler drag kan göras
    response = client.post(f"/api/games/{game_id}/moves", json={"row": 0, "col": 0})
    assert response.status_code == 409


def test_tekniskt_fel_pausar_partiet_och_gar_att_forsoka_igen(client, monkeypatch):
    """AC-05-05 + AC-05-07: tekniskt fel -> felmeddelande, pausat parti, försök igen."""
    from app import service

    game = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "color": "white", "player_name": "Simon"},
    ).json()  # datorn (svart) börjar

    def trasigt_drag(*args, **kwargs):
        raise RuntimeError("simulerat tekniskt fel")

    monkeypatch.setattr(service.domain, "ai_move", trasigt_drag)
    response = client.post(f"/api/games/{game['id']}/ai-move")

    # Then: ett felmeddelande visas och partiet pausas
    assert response.status_code == 503
    assert "pausat" in response.json()["detail"].lower()

    state = client.get(f"/api/games/{game['id']}").json()
    assert state["status"] == "paused"
    # And: partitillståndet bevaras (färger, vems tur, brädet)
    assert state["players"]["white"] == "Simon"
    assert state["turn"] == 1
    assert state["board_size"] == 15

    # And: spelaren kan inte göra drag medan partiet är pausat
    blocked = client.post(f"/api/games/{game['id']}/moves", json={"row": 7, "col": 7})
    assert blocked.status_code == 409

    # And: spelaren kan försöka igen — andra försöket lyckas
    monkeypatch.undo()
    retry = client.post(f"/api/games/{game['id']}/ai-move")
    assert retry.status_code == 200
    assert retry.json()["status"] == "in_progress"
    assert retry.json()["move_count"] == 1


def test_tidsgrans_ger_ett_nytt_forsok(client, monkeypatch):
    """AC-05-06: första försöket tar > 3 s, andra försöket lyckas."""
    from app import service

    game = client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "color": "white", "player_name": "Simon"},
    ).json()

    calls = {"n": 0}

    def langsamt_forsta_drag(board, player, difficulty="normal"):
        calls["n"] += 1
        if calls["n"] == 1:
            time.sleep(3.05)  # över tidsgränsen
        return (7, 7)

    monkeypatch.setattr(service.domain, "ai_move", langsamt_forsta_drag)
    response = client.post(f"/api/games/{game['id']}/ai-move")

    assert response.status_code == 200
    assert calls["n"] == 2  # gjorde ett nytt försök
    assert response.json()["board"][7][7] == 1
    assert response.json()["status"] == "in_progress"
