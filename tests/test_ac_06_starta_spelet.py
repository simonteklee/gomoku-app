"""AC-06 — Starta spelet (UC-06).

Given att spelaren har en enhet med webbläsare och känner till spelets adress
When spelaren öppnar adressen
Then laddas applikationen
And visas startsidan inom 2 sekunder
And visas valen "Spela mot datorn", "Spela mot vän" och "Visa spelregler"
And spelaren kan välja ett av alternativen
"""

import time


def test_startsidan_laddas_inom_tva_sekunder(client):
    started = time.perf_counter()
    response = client.get("/")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 2.0, f"startsidan tog {elapsed:.2f}s"


def test_startsidan_visar_de_tre_valen(client):
    page = client.get("/").text

    assert "Spela mot datorn" in page
    assert "Spela mot vän" in page
    assert "Visa spelregler" in page


def test_alternativen_gar_att_valja(client):
    """Varje val leder till en fungerande vy (UI) — och motsvarande API finns."""
    options = client.get("/api/startpage").json()["options"]
    assert options == ["Spela mot datorn", "Spela mot vän", "Visa spelregler"]

    # "Spela mot datorn" -> skapa parti
    assert client.post(
        "/api/games",
        json={"board_size": 15, "mode": "ai", "color": "black", "player_name": "Simon"},
    ).status_code == 200

    # "Spela mot vän" -> skapa inbjudan
    assert client.post(
        "/api/invites", json={"board_size": 15, "color": "black", "player_name": "Simon"}
    ).status_code == 200

    # "Visa spelregler" -> reglerna finns i applikationen
    assert "fem stenar i rad" in client.get("/").text
