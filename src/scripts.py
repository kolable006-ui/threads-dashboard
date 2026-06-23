# -*- coding: utf-8 -*-
"""產生「廣告腳本框架」— 不寫死內容、不呼叫任何 API。
針對 imitate_score 最高、且非個股/明牌的貼文，給出：
  - 建議鉤子類別 + 模板（不同支盡量換類別、避開最近 7 天用過的）
  - 建議對應懶人包
  - 三條鐵則的空白逐字稿框架，留 ＿＿ 給人工填
"""
import hashlib
import re

from hooks import pick_diverse, HOOK_RULES

CTA = "點擊下方按鈕，填寫表單，免費領取懶人包。"

# 個股/明牌味道重的，不拿來當腳本來源（即使讚數高）
_STOCK_HINT = ["漲停", "目標價", "喊到", "戰績", "嘎空", "借券", "做多", "做空", "當沖賺"]

# 每份懶人包 → (主題詞, 好處詞)，用來把鉤子模板的空格自動填成草稿第一句。
# 都是中性敘述，不含保證獲利／收益承諾／個股買賣建議。
_PACK_TOPICS = {
    "巴菲特給孩子的 5 個 ETF 投資策略": ("這 5 個 ETF 策略", "少走十年冤枉路"),
    "5 種台股賺錢策略": ("這 5 種台股策略", "看懂台股的節奏"),
    "小資翻倍存錢法（自動分帳法、逆向扣款存錢法、高效利率槓桿法）": ("這套存錢法", "第一桶金存得更快"),
    "高級當沖策略（怎麼挑標的、實際操作的邏輯）": ("怎麼挑當沖標的", "不再瞎進瞎出"),
    "100 個財經專有名詞": ("這些財經名詞", "看財經新聞不再霧煞煞"),
    "新手投資入門手冊（選券商、開戶、認識成本、買第一張股票）": ("開戶和買第一張股票", "新手少踩很多雷"),
    "新手最常忽略的 ETF 代號（6 碼新制、用最後一碼辨識類型與風險）": ("ETF 代號的規則", "一眼看出風險高低"),
    "散戶最常踩的 6 個紀律破口（情緒進出、沒規則就進場、賺小賠大、部位忽大忽小、沒紀錄、重押單一標的）": ("這 6 個紀律破口", "不再賺小賠大"),
}
_BLANK_RE = re.compile(r"＿+")


def suggest_pack(text, pack_hints, packs):
    for kw, pack in pack_hints.items():
        if kw in (text or ""):
            return pack
    return packs[0] if packs else ""


def draft_first_line(tmpl, pack):
    """把鉤子模板的空格填成一句可用的草稿第一句（供人工微調）。
    無空格的模板（如『姐妹們聽我一句勸』）直接原樣回傳。"""
    topic, benefit = _PACK_TOPICS.get(pack, ("這份懶人包", "更有方向"))
    fills = [topic, benefit]
    idx = {"i": 0}

    def repl(_m):
        i = idx["i"]
        idx["i"] += 1
        return fills[i] if i < len(fills) else topic

    return _BLANK_RE.sub(repl, tmpl).replace("（人名）", "")


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

    # 懶人包多樣化 + 主推優先：本批盡量用「不同」的懶人包，並優先多搭配
    # cfg.priority_packs（主推那幾份），只留第 1 支給當天最相關的那份。
    # 依當批內容輪替起點，避免每次都從同一份開始。
    seed_src = chosen[0]["id"] if chosen else "x"
    seed = int(hashlib.md5(seed_src.encode()).hexdigest(), 16)
    rot = (packs[seed % len(packs):] + packs[:seed % len(packs)]) if packs else []
    priority = [p for p in cfg.get("priority_packs", []) if (not packs or p in packs)]
    used_packs = set()

    out = []
    for i, c in enumerate(chosen):
        cat, tmpl = hooks[i]
        primary = suggest_pack(c.get("hook", "") + c.get("summary", ""), pack_hints, packs)
        if i == 0 and primary and primary not in used_packs:
            # 第 1 支：用跟當天最熱貼文最相關的懶人包，保留相關性。
            pack = primary
        else:
            # 其餘：優先補還沒用到的「主推」懶人包，再退而求其次用輪替清單／primary。
            pack = (next((p for p in priority if p not in used_packs), None)
                    or next((p for p in rot if p not in used_packs), None)
                    or (primary if primary and primary not in used_packs else None)
                    or (packs[0] if packs else ""))
        used_packs.add(pack)
        first_line = draft_first_line(tmpl, pack)
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
            "firstLine": first_line,
            "script": framework,
        })
    return out
