# -*- coding: utf-8 -*-
"""產生「廣告腳本框架」— 不寫死內容、不呼叫任何 API。
針對 imitate_score 最高、且非個股/明牌的貼文，給出：
  - 建議鉤子類別 + 模板（不同支盡量換類別、避開最近 7 天用過的）
  - 建議對應懶人包
  - 三條鐵則的空白逐字稿框架，留 ＿＿ 給人工填
"""
from hooks import pick_diverse, HOOK_RULES

CTA = "點擊下方按鈕，填寫表單，免費領取懶人包。"

# 個股/明牌味道重的，不拿來當腳本來源（即使讚數高）
_STOCK_HINT = ["漲停", "目標價", "喊到", "戰績", "嘎空", "借券", "做多", "做空", "當沖賺"]


def suggest_pack(text, pack_hints, packs):
    for kw, pack in pack_hints.items():
        if kw in (text or ""):
            return pack
    return packs[0] if packs else ""


def _too_stocky(c):
    t = c.get("hook", "") + c.get("summary", "")
    return sum(1 for k in _STOCK_HINT if k in t) >= 1 and c.get("imitate_score", 0) < 4


def build_frameworks(candidates, cfg, recent_used_ids=None, recent_categories=None):
    """回傳 list[script-framework dict]，schema 與儀表板 SCRIPTS 相容。"""
    recent_used = set(recent_used_ids or [])
    n = cfg.get("script_count", 4)
    pack_hints = cfg.get("pack_hints", {})
    packs = cfg.get("packs", [])

    # 來源池：先排除明牌味，再依「是否 7 天內用過」分層 — 優先用新鮮來源，
    # 但若新鮮的不夠 n 支，才回頭補用過的（避免某天只生得出 1 支）。
    usable = [c for c in candidates if not _too_stocky(c)]
    key = lambda c: (c.get("imitate_score", 0), c["likes"] is not None, c["likes"] or 0)
    fresh = sorted([c for c in usable if c["id"] not in recent_used], key=key, reverse=True)
    stale = sorted([c for c in usable if c["id"] in recent_used], key=key, reverse=True)
    chosen = (fresh + stale)[:n]   # 新鮮優先，不足才補

    hooks = pick_diverse(len(chosen), used_categories=recent_categories)
    out = []
    for i, c in enumerate(chosen):
        cat, tmpl = hooks[i]
        pack = suggest_pack(c.get("hook", "") + c.get("summary", ""), pack_hints, packs)
        likes_disp = "-" if c["likes"] is None else f"{c['likes']:,}"
        framework = (
            "【口白逐字稿｜框架，請人工填 ＿＿】\n\n"
            f"〔開頭鉤子，≤15 字，類別：{cat}〕\n"
            f"範本：{tmpl}\n"
            "→ 你的鉤子：＿＿＿＿＿＿\n\n"
            f"〔第 1–2 句帶出懶人包好處〕\n"
            f"我整理了一份「{pack}」免費懶人包，想分享給你。\n"
            "（接一句呼應貼文痛點：我看到＿＿，想到你可能也＿＿）\n\n"
            "〔中段：用貼文的故事 / 數字鋪陳，3–4 句〕\n"
            "＿＿＿＿＿＿\n\n"
            "〔收尾固定 CTA〕\n"
            f"{CTA}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "【鉤子原則提醒】" + "／".join(HOOK_RULES) + "\n"
            "【三條鐵則】1) 開頭用模板改寫(≤15字)　2) 前2句帶懶人包好處　3) 結尾固定 CTA\n"
            "⚠️ 不要寫保證獲利／收益承諾／個股買賣建議。"
        )
        out.append({
            "n": i + 1,
            "author": c["author"],
            "likes": likes_disp,
            "url": ("https://www.threads.com" + c["url"]) if c["url"].startswith("/") else c["url"],
            "reason": (c.get("hook") or "")[:40],
            "pack": pack,
            "duration": "30 秒",
            "hookType": cat,
            "hookFormula": tmpl,
            "script": framework,
        })
    return out
