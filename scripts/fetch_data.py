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

    li_tab = next((t for t in hyp_tabs if "linkedin" in t.lower()), None)
    if li_tab:
        save("linkedin_contacts", HYP_SID, f"'{li_tab}'!A:J")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    print("=== Fetching Funnel API ===")
    fetch_funnel_api()
    print("\n=== Fetching Google Sheets ===")
    fetch_sheets()
    print("\nDone!")
