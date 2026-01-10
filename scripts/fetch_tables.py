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


def abs_url(src: str) -> str:
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
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Fagerborg-BK-Tabeller/1.0)"
        },
    )
    r.raise_for_status()
    return r.text


def find_standings_table(soup: BeautifulSoup):
    """
    Fotball.no har ofte flere <table>. Vi velger den som ser ut som tabellen:
    - Har th/overskrifter som inkluderer "Plass" og "Lag" og "Poeng" (eller "P oeng"/varianter).
    """
    tables = soup.find_all("table")
    best = None

    def score_table(t):
        headers = [norm_space(th.get_text(" ", strip=True)).lower() for th in t.find_all("th")]
        h = " ".join(headers)

        score = 0
        if "plass" in h:
            score += 3
        if "lag" in h:
            score += 3
        if "poeng" in h or "p oeng" in h or "poengsum" in h:
            score += 3
        if "kamper" in h or "k amper" in h:
            score += 2
        if "mål" in h or "mf" in h or "for" in h:
            score += 1

        # litt ekstra: tabellen bør ha mange rader
        body_rows = t.find_all("tr")
        score += min(len(body_rows), 30) / 10.0

        return score

    best_score = -1
    for t in tables:
        sc = score_table(t)
        if sc > best_score:
            best_score = sc
            best = t

    return best


def parse_score(goals: str):
    # "0-0", "0 - 0", "0–0", "0-0 (0)"
    s = norm_space(goals)
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", s)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_standings_rows(table, logo_map: dict):
    rows = []
    trs = table.find_all("tr")

    for tr in trs:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        cells = [norm_space(td.get_text(" ", strip=True)) for td in tds]

        # Heuristikk for kolonner:
        # [0]=plass, [1]=lag, [2]=kamper, [3]=V, [4]=U, [5]=T, [6]=mål, [7]=diff, [8]=poeng
        pos = cells[0] if len(cells) > 0 else "0"

        team_td = tds[1] if len(tds) > 1 else None
        team = ""
        if team_td:
            # lag-navn står ofte i <a>
            a = team_td.find("a")
            team = norm_space(a.get_text(" ", strip=True) if a else team_td.get_text(" ", strip=True))

        if not team:
            continue

        played = cells[2] if len(cells) > 2 else "0"
        wins   = cells[3] if len(cells) > 3 else "0"
        draws  = cells[4] if len(cells) > 4 else "0"
        losses = cells[5] if len(cells) > 5 else "0"
        goals  = cells[6] if len(cells) > 6 else "0-0"
        diff   = cells[7] if len(cells) > 7 else ""
        points = cells[8] if len(cells) > 8 else (cells[-1] if cells else "0")

        # diff fallback
        if not re.fullmatch(r"-?\d+", diff or ""):
            sc = parse_score(goals)
            diff = str(sc[0] - sc[1]) if sc else "0"

        # logo fra kamper-siden (standings har ofte ingen)
        logo_url = logo_map.get(team.lower())

        rows.append({
            "pos": pos if pos else "0",
            "team": team,
            "logoUrl": logo_url,  # kan være None
            "played": played if re.fullmatch(r"\d+", played or "") else "0",
            "wins": wins if re.fullmatch(r"\d+", wins or "") else "0",
            "draws": draws if re.fullmatch(r"\d+", draws or "") else "0",
            "losses": losses if re.fullmatch(r"\d+", losses or "") else "0",
            "goals": goals if goals else "0-0",
            "diff": diff,
            "points": points if re.fullmatch(r"\d+", points or "") else "0",
            "form": []  # kan fylles senere
        })

    return rows


def build_logo_map_from_matches(fiks_id: int) -> dict:
    """
    Henter logoer fra kampsiden. Denne pleier å inneholde <img> ved lagnavn (hjemme/borte).
    Returnerer map: lowercase(team_name) -> absolute_logo_url
    """
    html = get_html(MATCHES_URL.format(fiks_id))
    soup = BeautifulSoup(html, "html.parser")

    logo_map = {}

    # Finn alle img i nærheten av lagnavn. Vi tar alle imgs og prøver å finne "nærmeste" tekst for team.
    # Fotball.no HTML varierer, så vi gjør det robust:
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        src = abs_url(src)
        if not src:
            continue

        # filter ut helt generiske ikoner
        if "country.svg" in src.lower():
            continue

        # prøv å finne teamnavn i parent (lenke/td)
        parent = img.find_parent(["a", "td", "div", "span"])
        if not parent:
            continue

        txt = norm_space(parent.get_text(" ", strip=True))
        # txt kan være mye – vi trenger et rent lagnavn:
        # prøv å ta første "ordgruppe" før tall/klokke etc.
        if not txt:
            continue

        # typisk vil parent-teksten inneholde lagnavn alene hvis det er logo ved navnet
        # vi tar hele teksten men kutter ved veldig lange strenger
        if len(txt) > 40:
            continue

        team_key = txt.lower()
        # behold første funn per lag (stabilt nok)
        logo_map.setdefault(team_key, src)

    return logo_map


def fetch_one(fiks_id: int):
    # 1) logoer fra kamper
    logo_map = build_logo_map_from_matches(fiks_id)

    # 2) standings
    html = get_html(TOURNAMENT_URL.format(fiks_id))
    soup = BeautifulSoup(html, "html.parser")
    table = find_standings_table(soup)
    if not table:
        return {"fiksId": fiks_id, "rows": []}

    rows = parse_standings_rows(table, logo_map)
    return {"fiksId": fiks_id, "rows": rows}


def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": fetch_one(A_FIKS),
        "b": fetch_one(B_FIKS),
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_FILE} with {len(data['a']['rows'])} A-rows and {len(data['b']['rows'])} B-rows")


if __name__ == "__main__":
    main()
