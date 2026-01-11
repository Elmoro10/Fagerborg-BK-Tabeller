import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

A_FIKS = 205403
B_FIKS = 205410

BASE = "https://www.fotball.no"
TOURNAMENT_URL = f"{BASE}/fotballdata/turnering/hjem/?fiksId={{}}&underside=tabellen"
MATCHES_URL = f"{BASE}/fotballdata/turnering/hjem/?fiksId={{}}&underside=kamper"

OUT_FILE = "data/tables.json"
LOGO_DIR = "data/logos"  # lagres i repoet og serveres fra GitHub Pages


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


def find_standings_table(soup: BeautifulSoup):
    """
    Velger tabellen som mest sannsynlig er "tabellen" basert på headers.
    """
    tables = soup.find_all("table")
    best = None
    best_score = -1.0

    def score_table(t):
        headers = [norm_space(th.get_text(" ", strip=True)).lower() for th in t.find_all("th")]
        h = " ".join(headers)

        score = 0
        if "plass" in h or "pos" in h:
            score += 3
        if "lag" in h or "club" in h:
            score += 3
        if "poeng" in h or "p" in headers:
            score += 2
        if "kamper" in h or "k" in headers:
            score += 2

        body_rows = t.find_all("tr")
        score += min(len(body_rows), 30) / 10.0
        return score

    for t in tables:
        sc = score_table(t)
        if sc > best_score:
            best_score = sc
            best = t

    return best


def parse_score(goals: str):
    s = norm_space(goals).replace("−", "-").replace("–", "-")
    m = re.search(r"(\d+)\s*-\s*(\d+)", s)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def extract_logo_id(url: str) -> str | None:
    """
    Tar ut et stabilt id fra URL, f.eks:
    https://images.fotball.no/clublogos/171.png  -> "171"
    """
    if not url:
        return None
    try:
        path = urlparse(url).path
        m = re.search(r"/clublogos/(\d+)\.(png|svg)$", path, flags=re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def download_logo(logo_url: str, logo_id: str) -> str | None:
    """
    Laster ned logo til data/logos/<id>.png
    Returnerer lokal path (for GitHub Pages): "data/logos/<id>.png"
    """
    if not logo_url or not logo_id:
        return None

    os.makedirs(LOGO_DIR, exist_ok=True)

    out_path = os.path.join(LOGO_DIR, f"{logo_id}.png")
    rel_path = f"data/logos/{logo_id}.png"

    # Hvis finnes fra før, ikke last ned hver gang (sparer commits)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return rel_path

    r = requests.get(
        logo_url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Fagerborg-BK-Tabeller/1.0)"},
    )
    r.raise_for_status()

    with open(out_path, "wb") as f:
        f.write(r.content)

    return rel_path


def build_logo_map_from_matches(fiks_id: int) -> dict:
    """
    Henter logoer fra kampsiden.
    Returnerer map: lowercase(team_name) -> absolute_logo_url
    """
    html = get_html(MATCHES_URL.format(fiks_id))
    soup = BeautifulSoup(html, "html.parser")

    logo_map = {}

    # Robust: alle img som peker på clublogos
    for img in soup.find_all("img"):
        src = abs_url(img.get("src") or "")
        if not src:
            continue
        if "/clublogos/" not in src.lower():
            continue

        parent = img.find_parent(["a", "td", "div", "span"])
        if not parent:
            continue

        txt = norm_space(parent.get_text(" ", strip=True))
        if not txt or len(txt) > 60:
            continue

        logo_map.setdefault(txt.lower(), src)

    return logo_map


def parse_standings_rows(table, logo_map: dict):
    rows = []
    trs = table.find_all("tr")

    for tr in trs:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        cells = [norm_space(td.get_text(" ", strip=True)) for td in tds]

        pos = cells[0] if len(cells) > 0 else "0"

        team_td = tds[1] if len(tds) > 1 else None
        team = ""
        if team_td:
            a = team_td.find("a")
            team = norm_space(a.get_text(" ", strip=True) if a else team_td.get_text(" ", strip=True))

        if not team:
            continue

        # Fotball.no kan variere, men ofte:
        # pos | lag | kamper | seier | uavgjort | tap | mål | diff | poeng
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

        # logo url fra kampsiden
        remote_logo = logo_map.get(team.lower())
        logo_id = extract_logo_id(remote_logo) if remote_logo else None
        local_logo = download_logo(remote_logo, logo_id) if (remote_logo and logo_id) else None

        rows.append({
            "pos": pos if pos else "0",
            "team": team,
            "logoUrl": local_logo,  # <-- LOKAL PATH i repoet (løser hotlink/CORS)
            "played": played if re.fullmatch(r"\d+", played or "") else "0",
            "wins": wins if re.fullmatch(r"\d+", wins or "") else "0",
            "draws": draws if re.fullmatch(r"\d+", draws or "") else "0",
            "losses": losses if re.fullmatch(r"\d+", losses or "") else "0",
            "goals": goals if goals else "0-0",
            "diff": diff,
            "points": points if re.fullmatch(r"\d+", points or "") else "0",
            "form": []
        })

    return rows


def fetch_one(fiks_id: int):
    logo_map = build_logo_map_from_matches(fiks_id)

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

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_FILE} with {len(data['a']['rows'])} A-rows and {len(data['b']['rows'])} B-rows")


if __name__ == "__main__":
    main()
