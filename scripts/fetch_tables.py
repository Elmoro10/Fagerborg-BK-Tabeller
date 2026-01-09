import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205403&underside=tabellen"
B_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205410&underside=tabellen"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FagerborgBK-Tabeller/1.0; +https://elmoro10.github.io/Fagerborg-BK-Tabeller/)"
}

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def parse_table(url: str):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        # fallback: prøv å finne første tabell på siden
        tables = soup.find_all("table")
        if not tables:
            raise RuntimeError(f"Fant ingen <table> på {url}")
        table = tables[0]

    rows = []
    for tr in table.select("tbody tr"):
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) < 6:
            continue

        # Fotball.no tabell pleier å være:
        # pos, lag, K, V, U, T, mål, diff, poeng
        # men kan variere litt, så vi tar det robust:
        pos = tds[0]
        team = tds[1]
        played = tds[2] if len(tds) > 2 else "0"
        wins   = tds[3] if len(tds) > 3 else "0"
        draws  = tds[4] if len(tds) > 4 else "0"
        losses = tds[5] if len(tds) > 5 else "0"
        goals  = tds[6] if len(tds) > 6 else "0-0"
        diff   = tds[7] if len(tds) > 7 else ""
        points = tds[-1] if len(tds) >= 1 else "0"

        # normaliser goals "0 – 0" -> "0-0"
        goals = re.sub(r"\s*[–—]\s*", "-", goals)

        # hvis diff mangler, regn ut fra goals hvis mulig
        if diff == "":
            m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", goals)
            if m:
                diff = str(int(m.group(1)) - int(m.group(2)))
            else:
                diff = "0"

        rows.append({
            "pos": pos,
            "team": team,
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals": goals,
            "diff": diff,
            "points": points,
        })

    return rows

def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": {"fiksId": 205403, "rows": parse_table(A_URL)},
        "b": {"fiksId": 205410, "rows": parse_table(B_URL)},
    }

    os.makedirs("data", exist_ok=True)
    with open("data/tables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
