# -*- coding: utf-8 -*-
"""跨天狀態：記住看過的貼文（算 is_new / 熱度上升）與最近用過的腳本來源（7 天輪替）。"""
import json
import os
from datetime import datetime, timedelta

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "state.json")


def load():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"seen": {}, "script_history": []}   # seen: id->{likes,first_date}; script_history: [{date, ids, categories}]


def save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def recent_script_ids(state, days=7, today=None):
    today = today or datetime.utcnow()
    cutoff = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    ids, cats = [], []
    for h in state.get("script_history", []):
        if h.get("date", "") >= cutoff:
            ids += h.get("ids", [])
            cats += h.get("categories", [])
    return set(ids), cats


def mark(state, candidates, today_str):
    """標記 is_new（首次出現）與更新 seen；回傳 (new_cnt, rising_list)。"""
    seen = state.setdefault("seen", {})
    new_cnt = 0
    rising = []
    for c in candidates:
        prev = seen.get(c["id"])
        if prev is None:
            c["is_new"] = True
            new_cnt += 1
        else:
            c["is_new"] = False
            if c.get("likes") and prev.get("likes") and c["likes"] > prev["likes"]:
                rising.append((c["author"], prev["likes"], c["likes"]))
        seen[c["id"]] = {"likes": c.get("likes"), "first_date": (prev or {}).get("first_date", today_str)}
    return new_cnt, rising


def record_scripts(state, scripts, today_str):
    state.setdefault("script_history", []).append({
        "date": today_str,
        "ids": [s["url"].rstrip("/").split("/")[-1] for s in scripts],
        "categories": [s.get("hookType") for s in scripts],
    })
    # 只留最近 30 筆
    state["script_history"] = state["script_history"][-30:]
