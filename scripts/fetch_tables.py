import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_FIKS = 205403
B_FIKS = 205410

BASE = "https://www.fotball.no"
TOURNAMENT_URL = f"{BASE}/fotballdata/turnering/hjem/?fiksId={{}}"
MATCHES_URL = f"{BASE}/fotballdata/turnering/hjem/?fiksId={{}}&underside=kamper"

OUT_FILE = "data/tables.json"


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def abs_url(src: str) -> str | None:
    if not src:
        return None
    src = src.strip()
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return BASE + src
    return src


def get_html(url: str) -> str:
    r = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Fagerborg-BK-Tabeller/1.0)"},
    )
    r.raise_for_status()
    return r.text


def normalize_minus(s: str) -> str:
    # fotball.no kan bruke unicode minus
    return (s or "").replace("−", "-").strip()


def build_logo_map_from_matches(fiks_id: int) -> dict[str, str]:
    """
    Henter logoer fra kampsiden.
    Robust: finner <a> som inneholder både lagnavn og <img>.
    Returnerer map: lowercase(team_name) -> absolute_logo_url
    """
    html = get_html(MATCHES_URL.format(fiks_id))
    soup = BeautifulSoup(html, "html.parser")

    logo_map: dict[str, str] = {}

    # Mange kamplister har lagnavn som <a>.. <img ...> Lagnavn ..</a>
    for a in soup.find_all("a"):
        img = a.find("img")
        if not img:
            continue

        src = abs_url(img.get("src") or "")
        if not src:
            continue

        # filter ut generiske ikoner (kan utvides ved behov)
        if "country.svg" in src.lower():
            continue

        team = norm_space(a.get_text(" ", strip=True))
        if not team:
            continue

        # noen elementer kan inneholde masse annet – men vi tillater litt mer enn før
        if len(team) > 80:
            continue

        logo_map.setdefault(team.lower(), src)

    return logo_map


def parse_standings_from_text(html: str, logo_map: dict[str, str], want_form: bool = False) -> list[dict]:
    """
    Parser tabellen direkte fra tekst på siden.
    Fungerer selv når fotball.no ikke bruker <table>.

    Forventer rader som omtrent:
    "1 Lagnavn 0 0 0 0 0 - 0 0 0"
      pos team   K V U T GF- GA Diff P
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    lines = [norm_space(l) for l in text.split("\n") if norm_space(l)]

    # Finn headerlinjen for tabellen
    # Tabellheaderen på fotball.no inneholder typisk: Plass, Lag, Kamper, (V/U/T), Mål, Diff, Poeng
    header_re = re.compile(r"\bPlass\b.*\bLag\b.*\bKamper\b.*\bMål\b.*\bDiff\b.*\bPoeng\b", re.IGNORECASE)

    start_idx = None
    for i, line in enumerate(lines):
        if header_re.search(line):
            start_idx = i
            break

    if start_idx is None:
        return []

    # Regex for en rad:
    # pos + team + played wins draws losses + gf - ga + diff + points
    row_re = re.compile(
        r"^\s*(\d+)\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*-\s*(\d+)\s+([-\d]+)\s+(\d+)\s*$"
    )

    rows: list[dict] = []

    for line in lines[start_idx + 1 :]:
        # stopp når vi åpenbart har gått ut av tabellen
        low = line.lower()
        if header_re.search(line):
            break
        if low.startswith(("opprykk", "nedrykk", "statistikk", "kontakt", "kamper", "tabell", "regel")):
            # fotball.no varierer – dette er “best effort”
            # vi stopper hvis vi møter tydelige seksjonsord
            # (men "kamper" kan dukke opp igjen – hvis dette blir et problem, kan vi fjerne "kamper")
            pass

        m = row_re.match(normalize_minus(line))
        if not m:
            continue

        pos = m.group(1)
        team = norm_space(m.group(2))
        played = m.group(3)
        wins = m.group(4)
        draws = m.group(5)
        losses = m.group(6)
        gf = m.group(7)
        ga = m.group(8)
        diff = m.group(9)
        points = m.group(10)

        goals = f"{gf}-{ga}"
        logo_url = logo_map.get(team.lower())

        rows.append(
            {
                "pos": pos,
                "team": team,
                "logoUrl": logo_url,  # kan være None
                "played": played,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "goals": goals,
                "diff": diff,
                "points": points,
                "form": [],  # fylles senere hvis dere får data
            }
        )

    return rows


def fetch_one(fiks_id: int) -> dict:
    # 1) logoer fra kamper
    logo_map = build_logo_map_from_matches(fiks_id)

    # 2) standings
    html = get_html(TOURNAMENT_URL.format(fiks_id))
    rows = parse_standings_from_text(html, logo_map)

    return {"fiksId": fiks_id, "rows": rows}


def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": fetch_one(A_FIKS),
        "b": fetch_one(B_FIKS),
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(
        f"Wrote {OUT_FILE} with {len(data['a']['rows'])} A-rows and {len(data['b']['rows'])} B-rows"
    )


if __name__ == "__main__":
    main()
