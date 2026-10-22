"""AC-02-1 — Placera en sten på ledig punkt (UC-02).

Given att ett parti pågår, det är spelarens tur och brädet visar det
When en spelare väljer en ledig punkt
Then placeras spelarens sten på punkten
And den senast placerade stenen markeras
And draget registreras med position, färg och nummer
And totala dragen ökas med ett
And återkopplingen sker inom 0,33 sekunder
"""

import time

from conftest import new_local_game


def test_placera_sten_pa_ledig_punkt(client):
    game = new_local_game(client)
    game_id = game["id"]

    started = time.perf_counter()
    response = client.post(f"/api/games/{game_id}/moves", json={"row": 7, "col": 7})
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    state = response.json()

    # Then: stenen placeras på punkten
    assert state["board"][7][7] == 1

    # And: draget registreras med position, färg och nummer
    assert state["moves"] == [{"seq": 1, "row": 7, "col": 7, "player": 1}]
    # ...den senast placerade stenen är den sista i listan (det UI:t markerar)
    assert state["moves"][-1]["row"] == 7 and state["moves"][-1]["col"] == 7

    # And: totala dragen ökas med ett
    assert state["move_count"] == 1

    # And: återkopplingen sker inom 0,33 sekunder
    assert elapsed < 0.33, f"svaret tog {elapsed:.3f}s"


def test_upptagen_punkt_nekas(client):
    game = new_local_game(client)
    game_id = game["id"]
    client.post(f"/api/games/{game_id}/moves", json={"row": 7, "col": 7})  # svart
    client.post(f"/api/games/{game_id}/moves", json={"row": 8, "col": 8})  # vit

    response = client.post(f"/api/games/{game_id}/moves", json={"row": 7, "col": 7})
    assert response.status_code == 409
    assert "upptagen" in response.json()["detail"].lower()


def test_punkt_utanfor_bradet_nekas(client):
    game = new_local_game(client)
    response = client.post(f"/api/games/{game['id']}/moves", json={"row": 15, "col": 0})
    assert response.status_code == 400
