#!/usr/bin/env python3
"""Fetch fresh data from all sources and save to data/ folder.

Required env vars:
  FUNNEL_URL, FUNNEL_USER, FUNNEL_PASS  - Alisa's Funnel Dashboard API
  GOOGLE_SA_KEY_PATH or GOOGLE_SA_KEY_JSON  - Google Sheets service account
"""
import json, os, sys, base64, urllib.request

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def fetch_funnel_api():
    base = os.environ["FUNNEL_URL"]
    user = os.environ["FUNNEL_USER"]
    pw = os.environ["FUNNEL_PASS"]
    auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}

    endpoints = {
        "overview": "/api/overview",
        "funnel": "/api/funnel",
        "pace": "/api/pace",
        "hypotheses": "/api/hypotheses",
        "source_analytics": "/api/source_analytics",
        "bases": "/api/bases",
        "source_collected": "/api/source_collected",
        "daily": "/api/daily",
    }

    for name, path in endpoints.items():
        try:
            req = urllib.request.Request(f"{base}{path}", headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            with open(os.path.join(DATA_DIR, f"{name}.json"), "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"OK: {name}")
        except Exception as e:
            print(f"ERR: {name} - {e}", file=sys.stderr)

    # Build all-time overview by summing across all available months
    try:
        req = urllib.request.Request(f"{base}/api/source_analytics", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            sa = json.loads(resp.read())
        months = sa.get("months", [])

        alltime_tg = {"sent": 0, "replied": 0, "mql": 0, "qual": 0, "zvonok": 0, "kp": 0, "dogovor": 0, "sdelka": 0}
        alltime_apollo = {"sent": 0, "replied": 0}
        for month in months:
            req = urllib.request.Request(f"{base}/api/overview?month={month}", headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                ov = json.loads(resp.read())
            for k in alltime_tg:
                alltime_tg[k] += ov.get("tg", {}).get(k, 0) or 0
            for k in alltime_apollo:
                alltime_apollo[k] += ov.get("apollo", {}).get(k, 0) or 0

        alltime = {"tg": alltime_tg, "apollo": alltime_apollo, "months": months}
        with open(os.path.join(DATA_DIR, "overview_alltime.json"), "w") as f:
            json.dump(alltime, f, ensure_ascii=False, indent=2)
        print(f"OK: overview_alltime ({len(months)} months)")
    except Exception as e:
        print(f"ERR: overview_alltime - {e}", file=sys.stderr)


def normalize_title(t):
    if not t:
        return None
    tl = t.lower().strip()
    if any(kw in tl for kw in ['ceo', 'founder', 'co-founder', 'cofounder', 'основатель',
            'владелец', 'собственник', 'owner', 'генеральный директор', 'ген. директор',
            'general director', 'managing director', 'управляющий директор', 'president',
            'президент', 'chairman', 'председатель', 'multifounder']):
        return 'CEO/Founder'
    if any(kw in tl for kw in ['cto', 'vp engineering', 'chief technology',
            'технический директор', 'tech lead', 'technical director', 'head of engineering']):
        return 'CTO/Tech'
    if any(kw in tl for kw in ['cio', 'chief information', 'директор по ит',
            'ит-директор', 'it director', 'директор по информационн',
            'руководитель ит', 'head of it']):
        return 'CIO/IT'
    if any(kw in tl for kw in ['cfo', 'chief financial', 'финансовый директор',
            'finance director', 'главный бухгалтер', 'главбух']):
        return 'CFO/Finance'
    if any(kw in tl for kw in ['hrd', 'hr director', 'chief people', 'chro',
            'hr-директор', 'директор по персоналу', 'head of hr', 'head of people',
            'hr manager', 'recruiter', 'рекрутер', 'head of talent']):
        return 'HRD/HR'
    if any(kw in tl for kw in ['coo', 'chief operating', 'операционный директор']):
        return 'COO/Ops'
    if any(kw in tl for kw in ['director', 'директор', 'руководитель', 'head of',
            'vp', 'vice president', 'заместитель']):
        return 'Director/Other'
    if any(kw in tl for kw in ['manager', 'менеджер', 'lead', 'team lead']):
        return 'Manager'
    return 'Other'


def fetch_hyp_titles(svc, hyp_sid):
    from collections import Counter
    TABS = [
        ("Сергей - рост штата 24/25", 4, 3, "sergey"),
        ("rusprofile", 4, 3, "rusprofile"),
        ("Сергей Ручной Рисерч✅", 2, 3, "sergey_manual"),
        ("TT - Digital/IT", 6, 3, "tt_digital"),
        ("TT - Бизнес РФ", 6, 3, "tt_bizrf"),
        ("TT - За рубежом", 6, 3, "tt_abroad"),
        ("TT - Стартапы", 6, 3, "tt_startups"),
        ("технопарки", 2, 3, "technoparks"),
        ("покупная база IT❌", 3, 3, "pokupnaya"),
        ("технопарки 2", 2, 3, "technoparks2"),
        ("Рекрутерские TG чаты", 6, 3, "recruiter_chats"),
        ("Агентства (researchops)", 6, 3, "agencies"),
        ("LeadGet тест", None, 3, "leadget"),
        ("4cio", 2, 3, "4cio"),
        ("AI интеграторы (партнёрка)", 4, 3, "ai_integrators"),
        ("LinkedIn рекомендации", 2, 3, "linkedin_recs"),
        ("RUSSOFT", 2, 3, "russoft"),
        ("АРПП", 2, 3, "arpp"),
        ("Рейтинг Рунета", 2, 3, "rating_runeta"),
        ("РАЭК", 2, 3, "raek"),
        ("Data Insight Top", 2, 3, "data_insight"),
        ("LinkedIn из TG-чатов", 2, 2, "linkedin_tg"),
    ]
    all_data = {}
    for tab_name, title_col, start_row, key in TABS:
        try:
            max_col = chr(65 + max(title_col or 0, 6) + 1)
            r = svc.values().get(
                spreadsheetId=hyp_sid,
                range=f"'{tab_name}'!A{start_row}:{max_col}5000"
            ).execute()
            rows = r.get("values", [])
            total = with_title = 0
            buckets = Counter()
            for row in rows:
                if not row or not any(c.strip() for c in row if c):
                    continue
                total += 1
                if title_col is not None and len(row) > title_col:
                    title = row[title_col].strip()
                    if title:
                        with_title += 1
                        b = normalize_title(title)
                        if b:
                            buckets[b] += 1
            all_data[key] = {
                "tab": tab_name, "total": total, "with_title": with_title,
                "title_pct": round(100 * with_title / total, 1) if total else 0,
                "buckets": dict(buckets.most_common()),
            }
        except Exception as e:
            all_data[key] = {"tab": tab_name, "total": 0, "error": str(e)}
    with open(os.path.join(DATA_DIR, "hyp_titles.json"), "w") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"OK: hyp_titles ({len(all_data)} tabs)")


def parse_int(s):
    if not s:
        return 0
    s = str(s).strip().replace('\xa0', '').replace(' ', '').replace(',', '')
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def fetch_event_funnel(svc, es_sid):
    REPORT_TABS = [
        ("Отчет ТП", "TP"),
        ("Отчёт ПО", "JF"),
    ]
    meta = svc.get(spreadsheetId=es_sid, fields="sheets(properties(title))").execute()
    tab_names = [s["properties"]["title"] for s in meta["sheets"]]

    all_rows = []
    for report_name, product in REPORT_TABS:
        tab = next((t for t in tab_names if report_name.lower() in t.lower()), None)
        if not tab:
            continue
        try:
            hdr_r = svc.values().get(spreadsheetId=es_sid, range=f"'{tab}'!A1:Z1").execute()
            headers = [h.strip().lower() for h in hdr_r.get("values", [[]])[0]]

            result = svc.values().get(spreadsheetId=es_sid, range=f"'{tab}'!A2:Z").execute()
            rows = result.get("values", [])

            def col(name):
                for i, h in enumerate(headers):
                    if name in h:
                        return i
                return None

            ci = {
                "name": col("ивент") or col("мероприят") or 0,
                "tag": col("тег") or col("tag"),
                "date": col("дата"),
                "format": col("формат"),
                "who": col("кто") or col("ездил"),
                "parsing": col("парсинг") or col("способ"),
                "cost": col("затрат") or col("стоимость"),
                "contacts": col("спарсили") or col("контакт"),
                "mql": col("mql") or col("передали"),
                "qual": col("квалов") or col("квал"),
                "kp": col("кп"),
                "contract": col("договор"),
                "deal": col("сделка") or col("сделок"),
                "verdict": col("вердикт"),
            }

            for row in rows:
                row += [""] * (26 - len(row))
                name = row[ci["name"]] if ci["name"] is not None else ""
                if not name.strip():
                    continue

                is_month = name.startswith("🟦") or name.startswith("🟧")
                is_total = "итого" in name.lower()

                mql = parse_int(row[ci["mql"]]) if ci["mql"] is not None else 0
                qual = parse_int(row[ci["qual"]]) if ci["qual"] is not None else 0
                kp = parse_int(row[ci["kp"]]) if ci["kp"] is not None else 0
                contract = parse_int(row[ci["contract"]]) if ci["contract"] is not None else 0
                deal = parse_int(row[ci["deal"]]) if ci["deal"] is not None else 0
                contacts = parse_int(row[ci["contacts"]]) if ci["contacts"] is not None else 0
                cost = parse_int(row[ci["cost"]]) if ci["cost"] is not None else 0

                r = {
                    "name": name.strip(),
                    "tag": (row[ci["tag"]] if ci["tag"] is not None else "").strip(),
                    "date": (row[ci["date"]] if ci["date"] is not None else "").strip(),
                    "format": (row[ci["format"]] if ci["format"] is not None else "").strip(),
                    "who": (row[ci["who"]] if ci["who"] is not None else "").strip(),
                    "product": product,
                    "parsing": (row[ci["parsing"]] if ci["parsing"] is not None else "").strip(),
                    "cost": cost,
                    "contacts": contacts,
                    "mql": mql,
                    "qual": qual,
                    "kp": kp,
                    "contract": contract,
                    "deal": deal,
                    "verdict": (row[ci["verdict"]] if ci["verdict"] is not None else "").strip(),
                    "cost_per_mql": int(cost / mql) if mql > 0 and cost > 0 else 0,
                    "cost_per_kp": int(cost / kp) if kp > 0 and cost > 0 else 0,
                }
                all_rows.append(r)
        except Exception as e:
            print(f"ERR: event_funnel/{report_name} - {e}", file=sys.stderr)

    with open(os.path.join(DATA_DIR, "event_funnel.json"), "w") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    print(f"OK: event_funnel ({len(all_rows)} rows)")


def fetch_sheets():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("SKIP: google-api-python-client not installed", file=sys.stderr)
        return

    key_path = os.environ.get("GOOGLE_SA_KEY_PATH")
    if not key_path:
        key_json = os.environ.get("GOOGLE_SA_KEY_JSON")
        if not key_json:
            print("SKIP: no service account key configured", file=sys.stderr)
            return
        key_path = "/tmp/sa_key.json"
        with open(key_path, "w") as f:
            f.write(key_json)

    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()

    ES_SID = "15CAqCmVkXNCuqmQ2ifLud931ukVCF0TUnz0OVDBUQrM"
    HYP_SID = "1NKM9sXp6eTCttKEVS49LWKZHKHS6mvqkWhdLJW3mx0Q"

    def save(name, sid, range_):
        try:
            result = svc.values().get(spreadsheetId=sid, range=range_).execute()
            rows = result.get("values", [])
            with open(os.path.join(DATA_DIR, f"{name}.json"), "w") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            print(f"OK: {name} ({len(rows)} rows)")
        except Exception as e:
            print(f"ERR: {name} - {e}", file=sys.stderr)

    meta = svc.get(spreadsheetId=ES_SID, fields="sheets(properties(title))").execute()
    tabs = [s["properties"]["title"] for s in meta["sheets"]]

    events_tab = next((t for t in tabs if "ивент" in t.lower()), None)
    edem_tab = next((t for t in tabs if "едем" in t.lower()), None)

    if events_tab:
        result = svc.values().get(spreadsheetId=ES_SID, range=f"'{events_tab}'!A2:T").execute()
        rows = result.get("values", [])[1:]
        events = []
        for row in rows:
            row += [""] * (20 - len(row))
            events.append({
                "new": row[0], "date": row[1], "month": row[2], "name": row[3],
                "ok_andrey": row[4], "timing": row[5], "geo": row[6], "format": row[7],
                "networking": row[8], "site": row[9], "focus": row[10], "who": row[11],
                "mode": row[12], "cost": row[13], "deadline": row[14], "channel": row[15],
                "decision": row[16], "note": row[17], "partnership": row[18], "event_key": row[19],
            })
        with open(os.path.join(DATA_DIR, "events.json"), "w") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"OK: events ({len(events)} rows)")

    if edem_tab:
        result = svc.values().get(spreadsheetId=ES_SID, range=f"'{edem_tab}'!A3:I").execute()
        rows = result.get("values", [])[1:]
        edem = []
        for row in rows:
            row += [""] * (9 - len(row))
            if row[0] and not any(row[0].startswith(p) for p in ["✅", "⏳", "Σ"]):
                edem.append({
                    "name": row[0], "date": row[1], "geo": row[2], "product": row[3],
                    "sales": row[4], "ticket": row[5], "cost": row[6],
                    "network": row[7], "note": row[8],
                })
        with open(os.path.join(DATA_DIR, "edem.json"), "w") as f:
            json.dump(edem, f, ensure_ascii=False, indent=2)
        print(f"OK: edem ({len(edem)} rows)")

    hyp_meta = svc.get(spreadsheetId=HYP_SID, fields="sheets(properties(title))").execute()
    hyp_tabs = [s["properties"]["title"] for s in hyp_meta["sheets"]]

    dash_tab = next((t for t in hyp_tabs if "дашборд" in t.lower()), None)
    if dash_tab:
        save("hyp_dashboard", HYP_SID, f"'{dash_tab}'!A:Z")

    fetch_hyp_titles(svc, HYP_SID)
    fetch_event_funnel(svc, ES_SID)

    li_tab = next((t for t in hyp_tabs if "linkedin из" in t.lower()), None)
    if li_tab:
        try:
            import re
            result = svc.values().get(
                spreadsheetId=HYP_SID, range=f"'{li_tab}'!A:L",
                valueRenderOption="FORMULA"
            ).execute()
            rows = result.get("values", [])
            hl_re = re.compile(r'=HYPERLINK\("([^"]+)"\s*,\s*"([^"]*)"\)')
            def parse_cell(c):
                if not isinstance(c, str):
                    return c
                m = hl_re.match(c)
                if m:
                    return {"url": m.group(1), "text": m.group(2)}
                return c
            parsed = [[parse_cell(c) for c in row] for row in rows]
            with open(os.path.join(DATA_DIR, "linkedin_contacts.json"), "w") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)
            print(f"OK: linkedin_contacts ({len(rows)} rows)")
        except Exception as e:
            print(f"ERR: linkedin_contacts - {e}", file=sys.stderr)


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    print("=== Fetching Funnel API ===")
    fetch_funnel_api()
    print("\n=== Fetching Google Sheets ===")
    fetch_sheets()
    print("\nDone!")
