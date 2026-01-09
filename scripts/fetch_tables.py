import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205403&underside=tabellen"
B_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205410&underside=tabellen"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FagerborgBK-Tabeller/1.0)"
}

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def pick_standings_table(soup: BeautifulSoup):
    """
    Fotball.no kan ha flere tabeller på samme side.
    Vi velger den som ser ut som tabellen (Plass/Lag/Poeng).
    """
    candidates = soup.find_all("table")
    if not candidates:
        raise RuntimeError("Fant ingen <table> i HTML.")

    best = None
    best_score = -1

    for t in candidates:
        text = normalize_spaces(t.get_text(" ", strip=True)).lower()

        # Score-tabell: gi poeng for typiske nøkkelord
        score = 0
        for kw in ["plass", "lag", "poeng", "mål", "vunnet", "uavgjort", "tap"]:
            if kw in text:
                score += 1

        # Straff tabeller som er kamp-lister eller "Unable to retrieve table columns"
        if "unable to retrieve table columns" in text:
            score -= 5
        if "hjemmelag" in text and "bortelag" in text:
            score -= 3

        if score > best_score:
            best_score = score
            best = t

    return best

def parse_standings(url: str):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    table = pick_standings_table(soup)

    rows = []
    for tr in table.find_all("tr"):
        # hopp over header-rader
        if tr.find("th"):
            continue

        tds = [normalize_spaces(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if len(tds) < 6:
            continue

        # Typisk rekkefølge:
        # pos, lag, kamper, vunnet, uavgjort, tap, mål, diff, poeng
        # men vi gjør det robust:
        pos = tds[0]
        team = tds[1] if len(tds) > 1 else ""

        # Finn tallkolonner ved posisjoner (fallback til 0)
        played = tds[2] if len(tds) > 2 else "0"
        wins   = tds[3] if len(tds) > 3 else "0"
        draws  = tds[4] if len(tds) > 4 else "0"
        losses = tds[5] if len(tds) > 5 else "0"

        goals  = tds[6] if len(tds) > 6 else "0-0"
        goals  = re.sub(r"\s*[–—]\s*", "-", goals)  # normaliser dash

        diff = tds[7] if len(tds) > 7 else ""
        points = tds[-1]  # siste kolonne pleier å være poeng

        if diff == "":
            m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", goals)
            if m:
                diff = str(int(m.group(1)) - int(m.group(2)))
            else:
                diff = "0"

        # hvis pos ikke er et tall (noen ganger kan det være tomt), hopp
        if not re.search(r"\d", pos):
            continue

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
        "a": {"fiksId": 205403, "rows": parse_standings(A_URL)},
        "b": {"fiksId": 205410, "rows": parse_standings(B_URL)},
    }

    os.makedirs("data", exist_ok=True)
    with open("data/tables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
