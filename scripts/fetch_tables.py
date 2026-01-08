import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

A_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205403&underside=tabellen"
B_URL = "https://www.fotball.no/fotballdata/turnering/hjem/?fiksId=205410&underside=tabellen"

HEADERS = {"User-Agent": "Mozilla/5.0 (GitHub Actions)"}

def parse(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) < 7:
            continue
        rows.append({
            "pos": tds[0],
            "team": tds[1],
            "played": tds[2],
            "wins": tds[3],
            "draws": tds[4],
            "losses": tds[5],
            "goals": tds[6],
            "points": tds[-1],
        })
    return rows

def main():
    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "a": {"fiksId": 205403, "rows": parse(A_URL)},
        "b": {"fiksId": 205410, "rows": parse(B_URL)},
    }

    import os
    os.makedirs("data", exist_ok=True)

    with open("data/tables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
