"""AC-13 — Starta ett nytt parti (UC-13).

Given att ett parti har avslutats och resultatvyn visas
When spelaren väljer "Spela igen"
Then ska systemet skapa ett nytt parti
And visa ett tomt bräde
And behålla samma spelinställningar
And visa vem som börjar
"""


def test_spela_igen_skapar_nytt_parti_med_samma_installningar(client):
    game = client.post(
        "/api/games",
        json={
            "board_size": 19,
            "mode": "ai",
            "difficulty": "hard",
            "color": "black",
            "player_name": "Simon",
        },
    ).json()
    client.post(f"/api/games/{game['id']}/moves", json={"row": 7, "col": 7})
    finished = client.post(f"/api/games/{game['id']}/forfeit").json()
    assert finished["status"] == "finished"

    response = client.post(f"/api/games/{game['id']}/rematch")
    assert response.status_code == 200
    new_game = response.json()

    # Then: ett nytt parti skapas
    assert new_game["id"] != game["id"]
    assert new_game["status"] == "in_progress"

    # And: ett tomt bräde visas
    assert new_game["move_count"] == 0
    assert all(cell == 0 for row in new_game["board"] for cell in row)

    # And: samma spelinställningar behålls
    assert new_game["board_size"] == 19
    assert new_game["mode"] == "ai"
    assert new_game["difficulty"] == "hard"
    assert new_game["players"]["black"] == "Simon"

    # And: det visas vem som börjar (svart)
    assert new_game["turn"] == 1
