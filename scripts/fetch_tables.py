def parse_standings_rows(table):
    rows = []
    trs = table.find_all("tr")
    for tr in trs:
        tds = tr.find_all(["td"])
        if len(tds) < 5:
            continue

        # pos
        pos = norm_space(tds[0].get_text(" ", strip=True))

        # team + logo: ofte i td[1]
        team_td = tds[1]
        team = norm_space(team_td.get_text(" ", strip=True))

        logo_url = None
        img = team_td.find("img")
        if img and img.get("src"):
            logo_url = img["src"].strip()
            # gjør relative src absolute hvis nødvendig
            if logo_url.startswith("/"):
                logo_url = "https://www.fotball.no" + logo_url

        # tallkolonner (best-effort)
        cells = [norm_space(td.get_text(" ", strip=True)) for td in tds]
        played = cells[2] if len(cells) > 2 else "0"
        wins   = cells[3] if len(cells) > 3 else "0"
        draws  = cells[4] if len(cells) > 4 else "0"
        losses = cells[5] if len(cells) > 5 else "0"
        goals  = cells[6] if len(cells) > 6 else "0-0"
        points = cells[-1] if len(cells) > 0 else "0"

        diff = ""
        if len(cells) >= 9:
            diff = cells[-2]
        if not re.fullmatch(r"-?\d+", diff or ""):
            sc = parse_score(goals)
            diff = str(sc[0] - sc[1]) if sc else "0"

        if not team:
            continue

        rows.append({
            "pos": pos if pos else "0",
            "team": team,
            "logoUrl": logo_url,
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
