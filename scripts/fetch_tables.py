import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205403&underside=tabellen"
B_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205410&underside=tabellen"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (GitHub Actions)"
}

def extract_fiks_id(url: str) -> int:
    m = re.search(r"fiksId=(\d+)", url)
    return int(m.group(1)) if m else 0

def normalize(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())

def is_match_table(headers: list[str]) -> bool:
    # Kampoppsett-tabell har typ disse
    bad = {"hjemmelag", "bortelag", "kampnr.", "kampnr", "bane", "resultat", "tid", "dato", "runde"}
    return any(h in bad for h in headers)

def is_standings_table(headers: list[str]) -> bool:
    # Serietabell har typ disse (varierer litt)
    # Vi krever "lag" + ("poeng" eller "p") + noe som ligner kamper/seire/tap
    has_team = any(h == "lag" or "lag" in h for h in headers)
    has_points = any(h == "poeng" or h == "p" or "poeng" in h for h in headers)
    has_played = any(h == "k" or "kamper" in h or "spilt" in h for h in headers)
    has_results = any(h in {"v", "u", "t"} or "vunnet" in h or "uavgjort" in h or "tapt" in h for h in headers)
    return has_team and has_points and (has_played or has_results)

def pick_standings_table(soup: BeautifulSoup):
    best = None
    best_score = -1

    for t in soup.find_all("table"):
        ths = [normalize(th.get_text(" ", strip=True)) for th in t.find_all("th")]
        if not ths:
            continue

        # IKKE velg kamp-tabeller
        if is_match_table(ths):
            continue

        # må se ut som serietabell
        if not is_standings_table(ths):
            continue

        # score: flere "riktige" headers + flere rader
        score = 0
        score += 10 if any(h == "lag" or "lag" in h for h in ths) else 0
        score += 10 if any(h == "poeng" or h == "p" or "poeng" in h for h in ths) else 0
        score += 5 if any(h == "k" or "kamper" in h or "spilt" in h for h in ths) else 0
        score += 3 if any(h in {"v","u","t"} or "vunnet" in h or "uavgjort" in h or "tapt" in h for h in ths) else 0
        score += min(len(t.find_all("tr")), 50)  # litt bonus for rader

        if score > best_score:
            best_score = score
            best = t

    return best

def idx(headers: list[str], *needles: str):
    for i, h in enumerate(headers):
        if any(n in h for n in needles):
            return i
    return None

def parse(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = pick_standings_table(soup)
    if table is None:
        return {"fiksId": extract_fiks_id(url), "rows": []}

    headers = [normalize(th.get_text(" ", strip=True)) for th in table.find_all("th")]

    i_team   = idx(headers, "lag")
    i_played = idx(headers, "kamper", "spilt", "k")
    i_wins   = idx(headers, "vunnet", "v")
    i_draws  = idx(headers, "uavgjort", "u")
    i_losses = idx(headers, "tapt", "t")
    i_goals  = idx(headers, "mål")
    i_pts    = idx(headers, "poeng", "p")

    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) < 4:
            continue

        # pos er nesten alltid første celle og et tall
        pos = tds[0].strip()
        if not pos.isdigit():
            continue

        def safe(i, fallback=""):
            return tds[i].strip() if i is not None and i < len(tds) else fallback

        team = safe(i_team, fallback=(tds[1].strip() if len(tds) > 1 else ""))
        if not team:
            continue

        rows.append({
            "pos": pos,
            "team": team,
            "played": safe(i_played, "0"),
            "wins": safe(i_wins, "0"),
            "draws": safe(i_draws, "0"),
            "losses": safe(i_losses, "0"),
            "goals": safe(i_goals, "0–0"),
            "points": safe(i_pts, "0"),
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
