import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205403&underside=tabellen"
B_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205410&underside=tabellen"

HEADERS = {"User-Agent": "Mozilla/5.0 (GitHub Actions)"}

def extract_fiks_id(url: str) -> int:
    m = re.search(r"fiksId=(\d+)", url)
    return int(m.group(1)) if m else 0

def pick_standings_table(soup: BeautifulSoup):
    # Velg tabellen som SER UT som en serietabell (har header med Lag/Poeng osv)
    best = None
    best_score = -1
    for t in soup.find_all("table"):
        ths = [th.get_text(" ", strip=True).lower() for th in t.find_all("th")]
        if not ths:
            continue
        score = 0
        if any("lag" in h for h in ths): score += 5
        if any("poeng" in h or h == "p" for h in ths): score += 5
        if any("mål" in h for h in ths): score += 3
        score += len(t.find_all("tr"))  # flere rader = sannsynlig tabell
        if score > best_score:
            best_score = score
            best = t
    return best

def parse(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = pick_standings_table(soup)
    if table is None:
        return {"fiksId": extract_fiks_id(url), "rows": []}

    # header til indekser
    header = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]

    def find_idx(*needles):
        for i, h in enumerate(header):
            if any(n in h for n in needles):
                return i
        return None

    i_team = find_idx("lag")  # "Lag"
    i_played = find_idx("kamper", "spilt", "k")
    i_wins = find_idx("vunnet", "v")
    i_draws = find_idx("uavgjort", "u")
    i_losses = find_idx("tapt", "t")
    i_goals = find_idx("mål")
    i_points = find_idx("poeng", "p")

    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) < 5:
            continue

        # Finn plass: første celle i raden som er et heltall >= 1
        pos = ""
        for cell in tds[:3]:
            if cell.isdigit() and int(cell) >= 1:
                pos = cell
                break
        if not pos:
            continue

        def safe(i):
            return tds[i] if i is not None and i < len(tds) else ""

        team = safe(i_team) if i_team is not None else (tds[1] if len(tds) > 1 else "")
        if not team:
            continue

        rows.append({
            "pos": pos,
            "team": team,
            "played": safe(i_played),
            "wins": safe(i_wins),
            "draws": safe(i_draws),
            "losses": safe(i_losses),
            "goals": safe(i_goals),
            "points": safe(i_points),
        })

    return {"fiksId": extract_fiks_id(url), "rows": rows}

def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": parse(A_URL),
        "b": parse(B_URL),
    }

    import os
    os.makedirs("data", exist_ok=True)

    with open("data/tables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
