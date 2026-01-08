import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205403&underside=tabellen"
B_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205410&underside=tabellen"

UA = "Mozilla/5.0 (GitHubActions; +https://github.com/elmoro10/Fagerborg-BK-Tabeller)"

def extract_fiks_id(url: str) -> int:
    m = re.search(r"fiksId=(\d+)", url)
    return int(m.group(1)) if m else 0

def find_standings_table(soup: BeautifulSoup):
    # Finn første tabell som ser ut som en tabell (har th og mange rader)
    tables = soup.find_all("table")
    best = None
    best_score = 0
    for t in tables:
        ths = [th.get_text(" ", strip=True).lower() for th in t.find_all("th")]
        if not ths:
            continue
        # Scoring basert på typiske kolonner
        score = 0
        for key in ["lag", "poeng", "mål", "kamper", "k", "p"]:
            if any(key == h or key in h for h in ths):
                score += 1
        rows = t.find_all("tr")
        score += min(len(rows), 30) / 10  # litt bonus for mange rader
        if score > best_score:
            best = t
            best_score = score
    return best

def parse_table(url: str):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = find_standings_table(soup)
    if table is None:
        return {
            "fiksId": extract_fiks_id(url),
            "rows": [],
        }

    # Les header for å vite kolonneposisjoner
    header_cells = [th.get_text(" ", strip=True) for th in table.find_all("th")]
    header_lower = [h.lower() for h in header_cells]

    def idx_contains(*needles):
        for i, h in enumerate(header_lower):
            if any(n in h for n in needles):
                return i
        return None

    idx_pos = 0  # ofte første
    idx_team = idx_contains("lag", "team") or 1
    idx_played = idx_contains("kamper", "spilt", "k")
    idx_w = idx_contains("vunnet", "v")
    idx_d = idx_contains("uavgjort", "u")
    idx_l = idx_contains("tapt", "t")
    idx_goals = idx_contains("mål")
    idx_diff = idx_contains("diff")
    idx_pts = idx_contains("poeng", "p")

    rows_out = []
    body_rows = table.find_all("tr")
    for tr in body_rows[1:]:
        tds = tr.find_all(["td", "th"])
        if len(tds) < 5:
            continue
        cells = [td.get_text(" ", strip=True) for td in tds]

        def safe(i):
            return cells[i] if i is not None and i < len(cells) else ""

        row = {
            "pos": safe(idx_pos),
            "team": safe(idx_team),
            "played": safe(idx_played),
            "wins": safe(idx_w),
            "draws": safe(idx_d),
            "losses": safe(idx_l),
            "goals": safe(idx_goals),
            "diff": safe(idx_diff),
            "points": safe(idx_pts),
        }

        # Filtrer ut tomme/ugyldige rader
        if row["team"] and row["pos"] and row["pos"].strip().isdigit():
            rows_out.append(row)

    return {
        "fiksId": extract_fiks_id(url),
        "rows": rows_out,
    }

def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": parse_table(A_URL),
        "b": parse_table(B_URL),
    }

    os.makedirs("data", exist_ok=True)
    with open("data/tables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
