import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_FIKS = 205403
B_FIKS = 205410

A_URL = f"https://www.fotball.no/fotballdata/turnering/hjem/?fiksId={A_FIKS}&underside=tabellen"
B_URL = f"https://www.fotball.no/fotballdata/turnering/hjem/?fiksId={B_FIKS}&underside=tabellen"

HEADERS = {"User-Agent": "Mozilla/5.0 (FagerborgBK-Tabeller/1.0)"}


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def score_table(table) -> int:
    txt = norm(table.get_text(" ", strip=True)).lower()

    score = 0
    for kw in ["plass", "lag", "poeng", "mål", "kamper", "vunnet", "uavgjort", "tap", "diff"]:
        if kw in txt:
            score += 2

    # straff “kamp-tabeller”
    if "hjemmelag" in txt and "bortelag" in txt:
        score -= 5

    # straff “tom/feil” tabell
    if "unable to retrieve table columns" in txt:
        score -= 10

    return score


def pick_standings_table(soup: BeautifulSoup):
    tables = soup.find_all("table")
    if not tables:
        return None
    best = max(tables, key=score_table)
    return best


def parse_standings(url: str):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    table = pick_standings_table(soup)
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        # skip header
        if tr.find("th"):
            continue

        tds = [norm(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if len(tds) < 6:
            continue

        pos = tds[0]
        team = tds[1] if len(tds) > 1 else ""

        # ofte: pos, lag, K, V, U, T, mål, diff, poeng
        played = tds[2] if len(tds) > 2 else "0"
        wins   = tds[3] if len(tds) > 3 else "0"
        draws  = tds[4] if len(tds) > 4 else "0"
        losses = tds[5] if len(tds) > 5 else "0"

        goals  = tds[6] if len(tds) > 6 else "0-0"
        goals  = re.sub(r"\s*[–—]\s*", "-", goals)

        diff   = tds[7] if len(tds) > 7 else ""
        points = tds[-1] if tds else "0"

        if not re.search(r"\d", pos):
            continue

        if diff == "":
            m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", goals)
            diff = str(int(m.group(1)) - int(m.group(2))) if m else "0"

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
            # form kommer senere (når vi har match-scraping stabilt)
            "form": []
        })

    return rows


def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": {"fiksId": A_FIKS, "rows": parse_standings(A_URL)},
        "b": {"fiksId": B_FIKS, "rows": parse_standings(B_URL)},
    }

    os.makedirs("data", exist_ok=True)
    with open("data/tables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
