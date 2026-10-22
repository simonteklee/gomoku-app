"""AC-17 — Spelhistorik (UC-17).

Given att spelaren har ett konto eller en lokal profil med sparad spelhistorik
When spelaren väljer "Spelhistorik"
Then ska systemet hämta spelarens avslutade partier
And visa datum, motståndare, brädstorlek och resultat för varje parti
And låta spelaren välja ett parti för att se mer information.

OBS: v1 har lokal profil (spelarnamn), inte konton — se SR-04/v1-avgränsning.
Historiken byggs på avslutade partier kopplade till spelarnamnet.
"""


def _finished_game(client, player="Simon", opponent="Fanny"):
    invite = client.post(
        "/api/invites", json={"board_size": 19, "color": "black", "player_name": player}
    ).json()
    game = client.post(
        f"/api/invites/{invite['token']}/accept", json={"player_name": opponent}
    ).json()
    client.post(f"/api/games/{game['id']}/forfeit")
    return game


def test_historik_visar_avslutade_partier(client):
    game = _finished_game(client)

    response = client.get("/api/history", params={"player": "Simon"})
    assert response.status_code == 200
    games = response.json()["games"]

    # Then: spelarens avslutade partier hämtas
    assert len(games) == 1
    entry = games[0]
    assert entry["game_id"] == game["id"]

    # And: datum, motståndare, brädstorlek och resultat visas för varje parti
    assert entry["date"]
    assert entry["opponent"] == "Fanny"
    assert entry["board_size"] == 19
    assert entry["result"] in {"vinst", "förlust", "oavgjort"}

    # And: spelaren kan välja ett parti för att se mer information
    detail = client.get(f"/api/games/{entry['game_id']}")
    assert detail.status_code == 200
    assert detail.json()["move_count"] == 0


def test_pagaeende_partier_ligger_inte_i_historiken(client):
    client.post(
        "/api/games", json={"board_size": 15, "mode": "ai", "color": "black", "player_name": "Simon"}
    )
    games = client.get("/api/history", params={"player": "Simon"}).json()["games"]
    assert games == []
