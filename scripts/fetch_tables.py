import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

A_FIKS = 205403
B_FIKS = 205410

BASE = "https://www.fotball.no"
STANDINGS_URL = f"{BASE}/fotballdata/turnering/hjem/?fiksId={{}}&underside=tabellen"
MATCHES_URL = f"{BASE}/fotballdata/turnering/hjem/?fiksId={{}}&underside=kamper"

OUT_FILE = Path("data/tables.json")


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
    return (s or "").replace("−", "-").replace("–", "-").strip()


def build_logo_map_from_matches(fiks_id: int) -> dict[str, str]:
    html = get_html(MATCHES_URL.format(fiks_id))
    soup = BeautifulSoup(html, "html.parser")
    logo_map: dict[str, str] = {}

    for a in soup.find_all("a"):
        img = a.find("img")
        if not img:
            continue

        src = abs_url(img.get("src") or "")
        if not src:
            continue

        if "country.svg" in src.lower():
            continue

        team = norm_space(a.get_text(" ", strip=True))
        if not team or len(team) > 120:
            continue

        logo_map.setdefault(team.lower(), src)

    return logo_map


def find_standings_table(soup: BeautifulSoup):
    tables = soup.find_all("table")
    best = None
    best_score = -1.0

    def score_table(t):
        headers = [norm_space(th.get_text(" ", strip=True)).lower() for th in t.find_all("th")]
        h = " ".join(headers)
        score = 0.0

        if "plass" in h:
            score += 3
        if "lag" in h:
            score += 3
        if "poeng" in h or "poengsum" in h:
            score += 3
        if "kamper" in h:
            score += 2
        if "mål" in h:
            score += 1

        score += min(len(t.find_all("tr")), 40) / 10.0
        return score

    for t in tables:
        sc = score_table(t)
        if sc > best_score:
            best_score = sc
            best = t

    return best


def parse_table_html(table, logo_map: dict[str, str]) -> list[dict]:
    """
    Plass | Lag | Kamper | S (Seier) | U (Uavgjort) | T (Tap) | Mål | Diff | Poeng
    Fotball.no kan variere litt, men dette funker for de vanligste tabellene.
    """
    rows = []

    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue

        cells = [norm_space(td.get_text(" ", strip=True)) for td in tds]

        pos = cells[0] if len(cells) > 0 else "0"

        team = ""
        if len(tds) > 1:
            a = tds[1].find("a")
            team = norm_space(a.get_text(" ", strip=True) if a else tds[1].get_text(" ", strip=True))
        if not team:
            continue

        played = cells[2] if len(cells) > 2 else "0"
        wins = cells[3] if len(cells) > 3 else "0"
        draws = cells[4] if len(cells) > 4 else "0"
        losses = cells[5] if len(cells) > 5 else "0"

        # Mål / diff / poeng kan være litt ulikt plassert.
        # Standard: goals=cells[6], diff=cells[7], points=cells[8]
        goals = cells[6] if len(cells) > 6 else "0-0"
        diff = cells[7] if len(cells) > 7 else ""
        points = cells[8] if len(cells) > 8 else (cells[-1] if cells else "0")

        goals = normalize_minus(goals)

        # diff fallback fra goals
        if not re.fullmatch(r"-?\d+", diff or ""):
            m = re.search(r"(\d+)\s*-\s*(\d+)", goals)
            diff = str(int(m.group(1)) - int(m.group(2))) if m else "0"

        logo_url = logo_map.get(team.lower())

        rows.append(
            {
                "pos": pos or "0",
                "team": team,
                "logoUrl": logo_url,
                "played": played if re.fullmatch(r"\d+", played or "") else "0",
                "wins": wins if re.fullmatch(r"\d+", wins or "") else "0",
                "draws": draws if re.fullmatch(r"\d+", draws or "") else "0",
                "losses": losses if re.fullmatch(r"\d+", losses or "") else "0",
                "goals": goals if goals else "0-0",
                "diff": diff,
                "points": points if re.fullmatch(r"\d+", points or "") else "0",
                "form": [],
            }
        )

    return rows


def parse_standings_from_text(html: str, logo_map: dict[str, str]) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [norm_space(l) for l in text.split("\n") if norm_space(l)]

    header_re = re.compile(
        r"\bPlass\b.*\bLag\b.*\bKamper\b.*\bMål\b.*\bDiff\b.*\bPoeng\b", re.IGNORECASE
    )

    start_idx = None
    for i, line in enumerate(lines):
        if header_re.search(line):
            start_idx = i
            break
    if start_idx is None:
        return []

    row_re = re.compile(
        r"^\s*(\d+)\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*-\s*(\d+)\s+([-\d]+)\s+(\d+)\s*$"
    )

    rows = []
    for line in lines[start_idx + 1 :]:
        m = row_re.match(normalize_minus(line))
        if not m:
            continue

        pos = m.group(1)
        team = norm_space(m.group(2))
        played, wins, draws, losses = m.group(3), m.group(4), m.group(5), m.group(6)
        mf, mm = m.group(7), m.group(8)
        diff = m.group(9)
        points = m.group(10)

        logo_url = logo_map.get(team.lower())

        rows.append(
            {
                "pos": pos,
                "team": team,
                "logoUrl": logo_url,
                "played": played,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "goals": f"{mf}-{mm}",
                "diff": diff,
                "points": points,
                "form": [],
            }
        )

    return rows


def fetch_one(fiks_id: int) -> dict:
    logo_map = build_logo_map_from_matches(fiks_id)
    html = get_html(STANDINGS_URL.format(fiks_id))
    soup = BeautifulSoup(html, "html.parser")

    table = find_standings_table(soup)
    rows = []
    if table is not None:
        rows = parse_table_html(table, logo_map)

    if not rows:
        rows = parse_standings_from_text(html, logo_map)

    return {"fiksId": fiks_id, "rows": rows}


def read_previous_rows() -> tuple[list[dict], list[dict]]:
    if not OUT_FILE.exists():
        return ([], [])
    try:
        prev = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        a_rows = prev.get("a", {}).get("rows", []) if isinstance(prev, dict) else []
        b_rows = prev.get("b", {}).get("rows", []) if isinstance(prev, dict) else []
        return (a_rows if isinstance(a_rows, list) else [], b_rows if isinstance(b_rows, list) else [])
    except Exception:
        return ([], [])


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    prev_a, prev_b = read_previous_rows()

    a = fetch_one(A_FIKS)
    b = fetch_one(B_FIKS)

    # Failsafe: ikke overskriv eksisterende data med tomt
    if (not a["rows"] and prev_a) or (not b["rows"] and prev_b):
        print("ERROR: Tomme rows, men forrige tables.json hadde data. Skriver ikke over.")
        print(f"  A new={len(a['rows'])} prev={len(prev_a)}")
        print(f"  B new={len(b['rows'])} prev={len(prev_b)}")
        sys.exit(1)

    if not a["rows"] and not b["rows"]:
        print("ERROR: Både A og B er tomme. Skriver ikke tables.json.")
        sys.exit(1)

    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": a,
        "b": b,
    }

    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_FILE} with {len(a['rows'])} A-rows and {len(b['rows'])} B-rows")


if __name__ == "__main__":
    main()
