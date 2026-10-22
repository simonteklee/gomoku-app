# Gomoku — app (frontend + backend)

Ett fullstack-exempel på hur krav och acceptanskriterier kan omsättas i kod och automatiska tester.
Byggt som kursprojekt i **Krav och användningsfall** (yrkeshögskola): kravspecifikation → acceptanskriterier
→ ett test per kriterium.

All speltlogik och datorns drag körs på servern, så att klienten bara ritar det API:t returnerar.

```
backend/app/domain.py     regler + AI (ren logik, inga beroenden)
backend/app/service.py    användningsfall: skapa parti, drag, ge upp, spara, bjud in
backend/app/main.py       REST-API (SR-02.3) + WebSocket (SR-02.4) + statisk frontend
backend/app/models.py     databastabeller (SR-02.5)
frontend/                 SPA som anropar API:t — ingen spellogik i klienten
tests/                    acceptanstester, ett test per AC
docker-compose.yml        backend + PostgreSQL (SR-02.6)
```

**Arkitekturgränsen:** all speltlogik och datorns drag körs i backend (`SR-04.4`).
Klienten skickar bara `POST /api/games/{id}/moves` och ritar svaret.

## Kör testerna (34 st, inga externa tjänster behövs)

```bash
.venv/bin/pytest
# 34 passed (kräver ingen databas – SQLite används i testerna)
```

Databasen pekas automatiskt om till en temporär SQLite-fil i `tests/conftest.py`.

## Kör appen lokalt

```bash
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload
# öppna http://127.0.0.1:8000
```

## Kör med Docker (PostgreSQL enligt SR-02.5/SR-02.6)

```bash
docker compose up --build
# http://localhost:8000
```

## AC → test

Byggt mot **origin/main** (AC-dokumenten har uppdaterats med delkriterier AC-xx-yy).

| AC | Fil | Testar |
|----|-----|--------|
| AC-01 Starta nytt parti | `tests/test_ac_01_starta_nytt_parti.py` | status pågående, färger, tomt bräde < 3 s, svart börjar |
| AC-02-1 Placera sten | `tests/test_ac_02_1_placera_sten.py` | sten placeras, registreras med position/färg/nummer, < 0,33 s, upptagen ruta nekas |
| AC-03-01…04 Bjud in en vän | `tests/test_ac_03_bjud_in_en_van.py` | länk < 1 s, väntläge, båda namn, drag < 0,5 s (WebSocket), **förfallen länk (410)**, **ogiltig länk (404)**, **avbruten inbjudan** |
| AC-04-01…04 Välja färg | `tests/test_ac_04_valja_farg.py` | vald färg, motståndaren den andra, svart börjar, **slumpad färg om ingen valts**, ändring förhindras efter start |
| AC-05-01…07 Spela mot datorn | `tests/test_ac_05_spela_mot_datorn.py` | datorns drag < 3 s, turas om, partiet avgörs, **tekniskt fel pausar partiet + nytt försök**, **tidsgräns ger nytt försök** |
| AC-06 Starta spelet | `tests/test_ac_06_starta_spelet.py` | startsidan < 2 s, de tre valen, valen fungerar |
| AC-11-01…03 Ge upp | `tests/test_ac_11_ge_upp.py` | förlust/vinst registreras, resultat visas, avslutat parti kan inte ge upp |
| AC-12 Avsluta ett parti | `tests/test_ac_12_avsluta_ett_parti.py` | status sparas, partiet avslutas, motståndaren aviseras |
| AC-13 Starta nytt parti | `tests/test_ac_13_starta_ett_nytt_parti.py` | nytt parti, tomt bräde, samma inställningar, vem som börjar |
| AC-14 Oavgjort | `tests/test_ac_14_oavgjort.py` | sista draget utan fem i rad → oavgjort, inga fler drag |
| AC-15 Förlust | `tests/test_ac_15_forlust.py` | motståndaren får fem i rad, vinnande rad markeras |
| AC-16 Vin | `tests/test_ac_16_vin.py` | spelaren får fem i rad (även diagonalt), vinnande rad markeras |
| AC-17 Spelhistorik | `tests/test_ac_17_spelhistorik.py` | avslutade partier med datum, motståndare, storlek, resultat |

**Inte testat:** AC-07 (spelarnamn), AC-08 (svårighetsgrad — finns i API:t), AC-09/AC-10 (kontrolleras indirekt via AC-05/AC-03), AC-25 (inloggning), AC-28/AC-29.

## Vad som inte är byggt

- Konton, inloggning, cookiesamtycke (UC-21–UC-25, UC-NFR-01) — kräver mer backend
- HTTPS/TLS 1.2+ (SR-02.3, NFR-07.1) — lokala körningar går över http
- Starkare AI (minimax) — nu: vinst/block/poängsättning
