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


# 開頭分類標籤行常見字（用「包含」判斷，可命中「台股投資」「台股 台積電 股市」等）
_HEADER_TAG_SUBSTR = [
    "投資理財", "高股息", "台積電", "台股", "美股", "理財", "股市", "ETF",
    "存股", "選股", "財經", "當沖", "基金", "期貨", "股票", "投資",
]
_PUNCT_RE = re.compile(r"[。！？，、,.!?：；…]")
_TIME_RE = re.compile(r"^\d+\s*(秒|分|分鐘|小時|時|天|週|周|月|年)前?$")
_NUM_RE = re.compile(r"^[\d.,]+\s*[萬kK]?$")


def clean_content(text, author):
    """去掉貼文開頭的『作者／分類標籤／時間』header，以及結尾的互動數字行，
    回傳乾淨的內容行（list）。用於產生卡片標題與摘要。"""
    lines = [l.strip() for l in (text or "").split("\n")]
    lines = [l for l in lines if l]
    out = []
    started = False
    for l in lines:
        if not started:
            if l == author:
                continue
            if _TIME_RE.match(l):
                continue
            if l == "翻譯":
                continue
            if _NUM_RE.match(l):
                continue
            # 開頭分類標籤行（如「台股投資」「台股 台積電 股市」）：短、無句子標點、且含已知標籤字才跳過
            if len(l) <= 10 and not _PUNCT_RE.search(l) and any(s in l for s in _HEADER_TAG_SUBSTR):
                continue
            started = True
        if l == "翻譯":
            continue
        out.append(l)
    # 去掉結尾連續的純數字行（讚/留言/轉/分享）
    while out and _NUM_RE.match(out[-1]):
        out.pop()
    return out


def score_post(likes, gid):
    """自動模仿分數（1–5）：依讚數量級為主，群組微調。
    讚數未知（未登入）時給保守的 3，再依群組微調。"""
    # 超高聲量（破 8000 讚）不論群組都值得關注，直接給 5。
    if likes is not None and likes >= 8000:
        return 5
    if likes is not None:
        if likes >= 5000:
            base = 5
        elif likes >= 2500:
            base = 4
        elif likes >= 1000:
            base = 3
        else:
            base = 2
    else:
        base = 3
    # 觀念/教學/勵志/ETF/新手/節目/AI：改編潛力高
    if gid in {"G2", "G3", "G4", "G5", "G6", "G7", "G8"}:
        base += 1
    elif gid == "G1":                            # 盤後/個股：較不適合直接改編
        base -= 1
    # 高聲量保底：破 5000 讚至少 4 分，不因群組被壓太低。
    if likes is not None and likes >= 5000:
        base = max(base, 4)
    return max(1, min(5, base))


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
        content = clean_content(text, it["author"])
        hook = (content[0] if content else text.split("\n")[0])[:60]
        summary = "\n".join(content)[:140] if content else text[:140]
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
            "imitate_score": score_post(likes, gid),
            "imitate_note": "（自動評分，請人工覆核改編潛力）",
            "keyword": it.get("keyword"),
        })
    # 依讚數排序（未知排後面）
    out.sort(key=lambda c: (c["likes"] is not None, c["likes"] or 0), reverse=True)
    return out
