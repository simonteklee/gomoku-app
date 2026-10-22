"""AC-01 — Starta nytt parti (UC-01).

Given att spelaren är på startsidan, har valt Starta nytt parti och ser konfigurationsvyn
When spelaren bekräftar inställningarna med Starta
Then skapas ett parti med status pågående
And tilldelas färgerna enligt spelarens val
And skapas ett tomt bräde av vald storlek inom 3 sekunder
And framgår det att svart gör första draget
"""

import time


def test_starta_nytt_parti(client):
    started = time.perf_counter()
    response = client.post(
        "/api/games",
        json={
            "board_size": 19,
            "mode": "ai",
            "difficulty": "normal",
            "color": "white",
            "player_name": "Simon",
        },
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    game = response.json()

    # Then: partiet skapas med status pågående
    assert game["status"] == "in_progress"

    # And: färgerna tilldelas enligt spelarens val (vit) och motståndaren får svart
    assert game["players"]["white"] == "Simon"
    assert game["players"]["black"] == "Datorn"

    # And: ett tomt bräde av vald storlek, inom 3 sekunder
    assert game["board_size"] == 19
    assert len(game["board"]) == 19
    assert all(cell == 0 for row in game["board"] for cell in row)
    assert game["move_count"] == 0
    assert elapsed < 3.0, f"brädet tog {elapsed:.2f}s"

    # And: det framgår att svart gör första draget
    assert game["turn"] == 1
