#!/usr/bin/env python3
"""Fetch event outreach data from Martina API, aggregate across months."""
import json, os, math, requests

CREDS_FILE = "/Users/cleocourbois/сlaude/martina_creds.txt"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Events we actually attended (from EDEM) -> list of Martina source names
EVENT_SOURCES = {
    "Startup Village 2026": [
        "@StartupSchool_Sk.",
        "Правила проекта Сколково (участники)",
    ],
    "ИИ КОНФА 2026": ["AI Конфа"],
    "DATA DAY 2026": ["Data Day"],
    "ТОК 2026 (Точка Банк)": ["Нетворк — сообщество от Точка Банк"],
    "C-level Days 2026": [
        "C-Level Days",
        "C-Level Days VIP + C-Level Days",
        "C-Level Days VIP",
    ],
    "ProIT Fest Лето 2026": [
        "proit_dinner",
        "@proitfest_chat (ProIT Fest, СПб)",
    ],
    "heg.ai x Captain Builders Meetup": [
        "heg.ai митап 27.08.2026",
        "heg.ai офлайн-митап Москва",
    ],
    "Conversations 2026 SPb": ["Conversations"],
    "GLOBAL TECH FORUM 2026": ["Global tech forum"],
    "TECH WEEK 2026": ["Tech Week Moscow 2026 (приложение)"],
    "Project Management Forum": ["PROJECT MANAGEMENT FORUM"],
    "PeopleSense'26": ["PeopleSense 2026 (приложение)"],
}

# Reverse lookup: source name -> event name
SOURCE_TO_EVENT = {}
for event, sources in EVENT_SOURCES.items():
    for src in sources:
        SOURCE_TO_EVENT[src] = event


def main():
    creds = open(CREDS_FILE).read().strip().split("|")
    base_url, user, pw = creds[0], creds[1], creds[2]
    auth = (user, pw)

    # Get available months
    resp = requests.get(f"{base_url}/api/source_analytics", auth=auth)
    resp.raise_for_status()
    months = resp.json().get("months", [])
    print(f"Available months: {months}")

    # Aggregate across all months
    events = {}
    for month in months:
        resp = requests.get(f"{base_url}/api/source_analytics?month={month}", auth=auth)
        resp.raise_for_status()
        rows = resp.json().get("rows", [])
        
        for row in rows:
            src = row["source"]
            event = SOURCE_TO_EVENT.get(src)
            if not event:
                continue
            
            if event not in events:
                events[event] = {"sent": 0, "replied": 0, "kp": 0, "sources": {}}
            
            sent = row.get("sent", 0) or 0
            reply_pct = row.get("reply_pct", 0) or 0
            replied = round(sent * reply_pct / 100)
            kp = row.get("kp", 0) or 0
            
            events[event]["sent"] += sent
            events[event]["replied"] += replied
            events[event]["kp"] += kp
            
            if src not in events[event]["sources"]:
                events[event]["sources"][src] = {"sent": 0, "replied": 0, "kp": 0}
            events[event]["sources"][src]["sent"] += sent
            events[event]["sources"][src]["replied"] += replied
            events[event]["sources"][src]["kp"] += kp

    # Build output
    result = []
    for event, d in sorted(events.items(), key=lambda x: -x[1]["sent"]):
        if d["sent"] == 0:
            continue
        sources = [{"name": k, **v} for k, v in d["sources"].items() if v["sent"] > 0]
        result.append({
            "event": event,
            "sent": d["sent"],
            "replied": d["replied"],
            "reply_rate": round(d["replied"] / d["sent"] * 100, 1) if d["sent"] > 0 else 0,
            "kp": d["kp"],
            "sources": sources,
        })

    out_path = os.path.join(DATA_DIR, "event_outreach.json")
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    total_sent = sum(e["sent"] for e in result)
    total_kp = sum(e["kp"] for e in result)
    print(f"Saved {len(result)} events: {total_sent} sent, {total_kp} KP -> {out_path}")


if __name__ == "__main__":
    main()
