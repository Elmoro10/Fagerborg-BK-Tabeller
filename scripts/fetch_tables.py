import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


A_FIKSID = 205403
B_FIKSID = 205410

BASE = "https://www.fotball.no/fotballdata/turnering/hjem/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ---------- helpers ----------

def get_html(fiks_id: int) -> str:
    # “Tabellen” ligger ofte på underside=kamper på fotball.no (som i linken du sendte)
    url = f"{BASE}?fiksId={fiks_id}&underside=kamper"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def parse_score(s: str):
    """
    Returnerer (home_goals, away_goals) eller None hvis ikke spilt.
    Godtar "2 - 1", "2–1", "2-1"
    """
    s = norm_space(s)
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", s)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def outcome_for_team(team: str, home: str, away: str, score):
    hg, ag = score
    if team == home:
        if hg > ag: return "W"
        if hg < ag: return "L"
        return "D"
    if team == away:
        if ag > hg: return "W"
        if ag < hg: return "L"
        return "D"
    return None


# ---------- standings/table scraping ----------

def find_standings_table(soup: BeautifulSoup):
    """
    Prøver å finne tabellen som faktisk er tabellen (ikke kampoppsett).
    Vi ser etter tabell som har overskrifter ala 'Lag', 'K', 'V', 'U', 'T' etc.
    """
    candidates = soup.find_all("table")
    wanted = {"lag", "k", "v", "u", "t", "mål", "p", "poeng", "diff"}
    best = None
    best_score = 0

    for t in candidates:
        ths = [norm_space(th.get_text()).lower() for th in t.find_all("th")]
        if not ths:
            continue
        score = sum(1 for h in ths if h in wanted)
        # standings-tabellen har ofte flere av disse samtidig
        if score > best_score:
            best_score = score
            best = t

    return best


def parse_standings_rows(table):
    """
    Returnerer rows med keys:
    pos, team, played, wins, draws, losses, goals, diff, points
    """
    rows = []
    trs = table.find_all("tr")
    for tr in trs:
        tds = tr.find_all(["td"])
        if len(tds) < 5:
            continue

        cells = [norm_space(td.get_text(" ", strip=True)) for td in tds]

        # Heuristikk: første kolonne er ofte posisjon (tall),
        # en av kolonnene er lagnavn (tekst),
        # og poeng pleier å være siste eller nest siste.
        # Vi tar “best effort” map:
        pos = cells[0]
        team = cells[1]

        # Prøv å plukke ut tallkolonner
        nums = [c for c in cells if re.fullmatch(r"\d+", c)]
        # Hvis den fant masse tall (inkl. pos), typisk:
        # pos, K, V, U, T, P (poeng) ...
        # Vi fallback’er til indexer som pleier å stemme:
        # [pos, team, K, V, U, T, mål, poeng]
        played = cells[2] if len(cells) > 2 else "0"
        wins   = cells[3] if len(cells) > 3 else "0"
        draws  = cells[4] if len(cells) > 4 else "0"
        losses = cells[5] if len(cells) > 5 else "0"

        goals  = cells[6] if len(cells) > 6 else "0-0"
        points = cells[-1] if len(cells) > 0 else "0"

        # diff kan noen ganger være egen kolonne, ellers regn ut fra mål
        diff = ""
        if len(cells) >= 9:
            # ofte … mål, diff, poeng
            diff = cells[-2]
        if not re.fullmatch(r"-?\d+", diff or ""):
            sc = parse_score(goals)
            if sc:
                diff = str(sc[0] - sc[1])
            else:
                diff = "0"

        # sanity: team skal ikke være tomt
        if not team:
            continue

        rows.append({
            "pos": pos if pos else "0",
            "team": team,
            "played": played if re.fullmatch(r"\d+", played or "") else "0",
            "wins": wins if re.fullmatch(r"\d+", wins or "") else "0",
            "draws": draws if re.fullmatch(r"\d+", draws or "") else "0",
            "losses": losses if re.fullmatch(r"\d+", losses or "") else "0",
            "goals": goals if goals else "0-0",
            "diff": diff,
            "points": points if re.fullmatch(r"\d+", points or "") else "0",
            "form": []  # fylles senere
        })

    return rows


# ---------- matches -> form ----------

def find_all_matches_table(soup: BeautifulSoup):
    """
    Finner en tabell som ser ut som “Alle kamper”:
    den har ofte kolonner som Hjemmelag / Bortelag / Resultat.
    """
    candidates = soup.find_all("table")
    best = None
    best_score = 0
    for t in candidates:
        ths = [norm_space(th.get_text()).lower() for th in t.find_all("th")]
        if not ths:
            continue
        keys = {"hjemmelag", "bortelag", "resultat", "dato", "tid"}
        score = sum(1 for h in ths if h in keys)
        if score > best_score:
            best_score = score
            best = t
    return best


def build_form(standings_rows, matches_table, max_n=5):
    if not standings_rows or not matches_table:
        return

    teams = [r["team"] for r in standings_rows]
    form_map = {t: [] for t in teams}

    # prøv å parse kamp-rader
    trs = matches_table.find_all("tr")
    parsed = []

    for tr in trs:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        cells = [norm_space(td.get_text(" ", strip=True)) for td in tds]

        # typisk: Runde, Dato, Tid, Hjemmelag, Resultat, Bortelag, ...
        # men varierer – vi prøver å finne home/away/result ved heuristikk
        joined = " | ".join(cells)

        # Finn resultat
        score = None
        for c in cells:
            s = parse_score(c)
            if s:
                score = s
                break
        if not score:
            continue

        # Finn “to lagnavn”: velg de to lengste tekst-cellene som ikke er dato/tid/tall
        text_cells = [c for c in cells if not re.fullmatch(r"\d+", c or "")]
        text_cells = [c for c in text_cells if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", c)]
        text_cells = [c for c in text_cells if not re.fullmatch(r"\d{2}:\d{2}", c)]
        # ofte ligger home/away i nærheten av score
        # fallback: ta celler rundt den som matchet score
        score_idx = next((i for i,c in enumerate(cells) if parse_score(c)), None)
        home = away = None
        if score_idx is not None:
            if score_idx - 1 >= 0:
                home = cells[score_idx - 1]
            if score_idx + 1 < len(cells):
                away = cells[score_idx + 1]

        if not home or not away:
            # fallback: ta to første “team-like” strings
            team_like = [c for c in text_cells if len(c) >= 3 and c.lower() not in {"=", "-"}]
            if len(team_like) >= 2:
                home, away = team_like[0], team_like[1]
            else:
                continue

        parsed.append((home, away, score))

    # parsed er “best effort” i rekkefølge på siden (ofte sortert nyeste øverst eller nederst)
    # vi bare går gjennom og fyller form_map til vi har 5
    for home, away, score in parsed:
        for team in teams:
            if len(form_map[team]) >= max_n:
                continue
            out = outcome_for_team(team, home, away, score)
            if out:
                form_map[team].append(out)

    # legg inn i rows
    for r in standings_rows:
        r["form"] = form_map.get(r["team"], [])


def scrape_one(fiks_id: int):
    html = get_html(fiks_id)
    soup = BeautifulSoup(html, "html.parser")

    standings_table = find_standings_table(soup)
    rows = parse_standings_rows(standings_table) if standings_table else []

    matches_table = find_all_matches_table(soup)
    build_form(rows, matches_table, max_n=5)

    return {"fiksId": fiks_id, "rows": rows}


def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": scrape_one(A_FIKSID),
        "b": scrape_one(B_FIKSID),
    }

    os.makedirs("data", exist_ok=True)
    with open("data/tables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
