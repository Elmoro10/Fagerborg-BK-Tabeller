<!doctype html>
<html lang="no">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tabeller – Fagerborg BK</title>

  <style>
    :root{
      --bg:#f3f5f7;
      --card:#ffffff;
      --text:#111827;
      --muted:#6b7280;
      --line:#e5e7eb;
      --head:#f7f7f7;

      --win:#7ad65a;
      --draw:#c8cdd4;
      --loss:#d14b4b;

      --stripeA:#1d4ed8; /* blå stripe (juster om du vil) */
      --stripeB:#b91c1c; /* rød stripe */
    }

    *{ box-sizing:border-box; }
    body{
      margin:0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      background: var(--bg);
      color: var(--text);
    }

    .wrap{ max-width: 1200px; margin: 0 auto; padding: 26px 16px 40px; }

    header{
      display:flex;
      justify-content:space-between;
      align-items:flex-end;
      gap:12px;
      flex-wrap:wrap;
      margin-bottom:18px;
    }

    h1{ margin:0; font-size:42px; letter-spacing:-0.02em; }
    .sub{ margin-top:4px; color:var(--muted); font-size:15px; }

    .btn{
      border:1px solid var(--line);
      background: #fff;
      padding:10px 16px;
      border-radius:999px;
      font-weight:700;
      cursor:pointer;
      display:flex;
      align-items:center;
      gap:8px;
    }

    .grid{ display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
    @media(max-width: 920px){ .grid{ grid-template-columns: 1fr; } }

    .card{
      background: var(--card);
      border:1px solid var(--line);
      border-radius: 14px;
      overflow:hidden;
      box-shadow: 0 8px 30px rgba(0,0,0,.06);
    }

    .card-head{
      padding:14px 16px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      border-bottom:1px solid var(--line);
      background: var(--head);
    }

    .title{ font-size:22px; font-weight:900; }
    .badge{
      font-size:13px;
      border:1px solid var(--line);
      padding:6px 12px;
      border-radius:999px;
      background:#fff;
      color:#374151;
      font-weight:700;
    }

    .content{ padding:0; }

    table{
      width:100%;
      border-collapse:separate;
      border-spacing:0;
      font-size:14px;
    }

    thead th{
      background:#fff;
      color:#9aa3af;
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:.06em;
      padding:14px 14px 10px;
      border-bottom:1px solid var(--line);
      text-align:left;
      white-space:nowrap;
    }

    tbody td{
      padding:16px 14px;
      border-bottom:1px solid var(--line);
      vertical-align:middle;
    }

    tbody tr{
      background:#fff;
      position:relative;
    }

    /* “PL stripe” venstre */
    tbody tr::before{
      content:"";
      position:absolute;
      left:0; top:0; bottom:0;
      width:4px;
      background:transparent;
    }

    tbody tr.stripeA::before{ background: var(--stripeA); }
    tbody tr.stripeB::before{ background: var(--stripeB); }

    tbody tr:hover{ background:#fafafa; }

    .pos{ width:52px; font-weight:800; color:#111827; }
    .team{ font-weight:900; }
    .num{ text-align:center; width:56px; font-variant-numeric: tabular-nums; }
    .goals{ text-align:center; width:72px; font-variant-numeric: tabular-nums; }
    .diff{ text-align:center; width:60px; font-variant-numeric: tabular-nums; }
    .pts{ text-align:center; width:60px; font-weight:900; }

    /* Form dots */
    .form{ width:160px; text-align:right; }
    .dots{
      display:inline-flex;
      gap:8px;
      align-items:center;
      justify-content:flex-end;
    }
    .dot{
      width:10px; height:10px; border-radius:999px;
      background: var(--draw);
      box-shadow: inset 0 0 0 1px rgba(0,0,0,.08);
    }
    .dot.w{ background: var(--win); }
    .dot.d{ background: var(--draw); }
    .dot.l{ background: var(--loss); }

    .pill{
      margin:12px 14px 14px;
      display:inline-block;
      font-size:12px;
      border:1px solid var(--line);
      border-radius:999px;
      padding:6px 10px;
      color:#4b5563;
      background:#fff;
    }

    .loading{
      padding:18px 14px;
      color:#6b7280;
    }
    .error{
      padding:18px 14px;
      color:#991b1b;
      background:#fee2e2;
      border-top:1px solid #fecaca;
    }

    .note{
      margin-top:14px;
      background:#fff;
      border:1px solid var(--line);
      padding:10px 12px;
      border-radius: 12px;
      color:#374151;
      font-size:13px;
      box-shadow: 0 8px 30px rgba(0,0,0,.04);
    }
  </style>
</head>

<body>
  <div class="wrap">
    <header>
      <div>
        <h1>Tabeller</h1>
        <div class="sub">Seriestilling for Fagerborgs lag (2026) – med Form (siste 5)</div>
      </div>

      <button class="btn" onclick="location.reload()">⟳ Oppdater</button>
    </header>

    <section class="grid">
      <div class="card">
        <div class="card-head">
          <div class="title">A-Lag</div>
          <div class="badge">5. divisjon (2026)</div>
        </div>
        <div class="content">
          <div id="a" class="loading">Laster…</div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div class="title">B-Lag</div>
          <div class="badge">7. divisjon (2026)</div>
        </div>
        <div class="content">
          <div id="b" class="loading">Laster…</div>
        </div>
      </div>
    </section>

    <div class="note" id="meta">—</div>
  </div>

  <script>
    const esc = s => String(s ?? "").replace(/[&<>"']/g, m => (
      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])
    ));

    const n0 = v => (v === undefined || v === null || v === "" ? "0" : String(v));

    const calcDiff = goals => {
      const m = String(goals || "").match(/(\d+)\s*[-–]\s*(\d+)/);
      if(!m) return "0";
      return String(parseInt(m[1],10) - parseInt(m[2],10));
    };

    const dotsHtml = (formArr) => {
      const f = Array.isArray(formArr) ? formArr.slice(-5) : [];
      // fyll opp med tomme draw (grå) hvis færre enn 5
      const padded = [...Array(Math.max(0, 5 - f.length)).fill("D"), ...f];
      return `<span class="dots">${
        padded.map(x => {
          const c = (x === "W") ? "w" : (x === "L") ? "l" : "d";
          return `<span class="dot ${c}" title="${x}"></span>`;
        }).join("")
      }</span>`;
    };

    function render(targetId, json, stripeClass){
      const el = document.getElementById(targetId);
      if(!json?.rows?.length){
        el.className = "error";
        el.textContent = "Fant ingen data.";
        return;
      }

      el.className = "";
      el.innerHTML = `
        <table>
          <thead>
            <tr>
              <th class="pos">Pos</th>
              <th>Club</th>
              <th class="num">P</th>
              <th class="num">W</th>
              <th class="num">D</th>
              <th class="num">L</th>
              <th class="goals">GF-GA</th>
              <th class="diff">Diff</th>
              <th class="pts">Pts</th>
              <th class="form">Form</th>
            </tr>
          </thead>
          <tbody>
            ${json.rows.map((r, i) => {
              const team = String(r.team || "");
              const gfga = String(r.goals || "0-0").replace("–","-");
              const diff = r.diff ? String(r.diff) : calcDiff(gfga);
              const isFagerborg = team.toLowerCase().includes("fagerborg");
              // Stripe på topp 6-ish (PL-ish). Juster hvis du vil.
              const stripe = (i < 6) ? stripeClass : "";
              return `
                <tr class="${stripe} ${isFagerborg ? "stripeA" : ""}">
                  <td class="pos">${esc(r.pos)}</td>
                  <td class="team">${esc(team)}</td>
                  <td class="num">${esc(n0(r.played))}</td>
                  <td class="num">${esc(n0(r.wins))}</td>
                  <td class="num">${esc(n0(r.draws))}</td>
                  <td class="num">${esc(n0(r.losses))}</td>
                  <td class="goals">${esc(gfga)}</td>
                  <td class="diff">${esc(diff)}</td>
                  <td class="pts">${esc(n0(r.points))}</td>
                  <td class="form">${dotsHtml(r.form)}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
        <div class="pill">Kilde: fotball.no (fiksId=${esc(json.fiksId)})</div>
      `;
    }

    async function boot(){
      try{
        const res = await fetch("https://elmoro10.github.io/Fagerborg-BK-Tabeller/data/tables.json?ts=" + Date.now(), { cache:"no-store" });
        if(!res.ok) throw new Error("HTTP " + res.status);
        const json = await res.json();

        render("a", json.a, "stripeA");
        render("b", json.b, "stripeB");

        // updatedAt er UTC tekst "YYYY-MM-DD HH:MM:SS" → gjør den til ISO
        // så Date klarer det stabilt:
        const utcIso = (json.updatedAt || "").replace(" ", "T") + "Z";
        const d = new Date(utcIso);

        document.getElementById("meta").textContent =
          `🕒 Sist oppdatert: ${isNaN(d.getTime()) ? "ukjent" : d.toLocaleString("no-NO", { dateStyle:"medium", timeStyle:"short" })} · oppdateres hvert 5. minutt`;
      }catch(e){
        document.getElementById("a").className = "error";
        document.getElementById("b").className = "error";
        document.getElementById("a").textContent = "Klarte ikke hente data.";
        document.getElementById("b").textContent = "Klarte ikke hente data.";
        document.getElementById("meta").textContent = "Sjekk at data/tables.json finnes på GitHub Pages.";
      }
    }

    boot();
  </script>
</body>
</html>
