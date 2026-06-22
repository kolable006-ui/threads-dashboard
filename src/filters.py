# -*- coding: utf-8 -*-
"""篩選與分群。"""
import re
from datetime import datetime, timedelta, timezone

CJK = re.compile(r"[一-鿿]")


def has_zh(text):
    return bool(CJK.search(text or ""))


def parse_date(raw, today):
    """把 Threads 的時間字串轉成 YYYY-MM-DD。抓不到就回 today。"""
    if not raw:
        return today.strftime("%Y-%m-%d")
    raw = raw.strip()
    # ISO datetime
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # 中文「YYYY年M月D日」
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # 相對時間「N小時前 / N天前 / N分鐘前」
    m = re.search(r"(\d+)\s*天", raw)
    if m:
        return (today - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    if re.search(r"小時|分鐘|分|秒|剛剛", raw):
        return today.strftime("%Y-%m-%d")
    return today.strftime("%Y-%m-%d")


def is_excluded(text, patterns):
    t = (text or "")
    low = t.lower()
    for p in patterns:
        if p.lower() in low:
            return p
    return None


def classify_group(text, groups_cfg):
    """回傳 (group_id, group_name)。groups_cfg 為 dict 保序。"""
    t = text or ""
    default = None
    for gid, g in groups_cfg.items():
        kws = g.get("keywords") or []
        if not kws:
            default = (gid, g.get("name", gid))
            continue
        if any(str(k) in t for k in kws):
            return gid, g.get("name", gid)
    return default or ("G1", "盤後評論")


def apply_filters(raw_items, cfg, today):
    """套用 zh / 讚數 / 日期 / 排除規則 + 分群。回傳乾淨 candidate list。"""
    out = []
    win_start = today - timedelta(days=cfg["days_window"])
    for it in raw_items:
        text = it.get("text", "")
        if cfg.get("require_zh", True) and not has_zh(text):
            continue
        hit = is_excluded(text, cfg.get("exclude_patterns", []))
        if hit:
            continue
        date = parse_date(it.get("date_raw"), today)
        try:
            d = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            d = today
        if d < win_start:
            continue
        likes = it.get("likes")
        # 讚數門檻：抓得到才比；抓不到（未登入隱藏）的標記為未驗證、仍保留供觀察
        likes_verified = likes is not None
        if likes_verified and likes < cfg["min_likes"]:
            continue
        gid, gname = classify_group(text, cfg["groups"])
        hook = text.split("\n")[0][:60]
        summary = text[:140]
        out.append({
            "id": it["id"],
            "author": it["author"],
            "verified": False,
            "date": date,
            "url": it["url"],
            "likes": likes,
            "likes_verified": likes_verified,
            "comments": it.get("comments"),
            "shares": it.get("shares"),
            "has_video": bool(it.get("has_video")),
            "hook": hook,
            "summary": summary + ("" if likes_verified else "（讚數未登入無法驗證，僅供觀察）"),
            "group": gid,
            "group_name": gname,
            "hook_type": "自動擷取",
            "imitate_score": 3,
            "imitate_note": "（自動擷取，請人工覆核改編潛力）",
            "keyword": it.get("keyword"),
        })
    # 依讚數排序（未知排後面）
    out.sort(key=lambda c: (c["likes"] is not None, c["likes"] or 0), reverse=True)
    return out
