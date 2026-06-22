# -*- coding: utf-8 -*-
"""把 DATA / SCRIPTS / VIDEO_HOOKS 注入 HTML 模板，產生 index.html。
保留模板裡既有的 SUGGESTIONS、HOOK_LIB 不動。
用 lambda re.sub 防呆（避免 JSON 內的 \\g 等被當成反向參照）。
"""
import json
import re


def _replace_const(html, name, value):
    pat = r'const ' + name + r'\s*=\s*(?:\{.*?\}|\[.*?\]);'
    payload = 'const ' + name + ' = ' + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ';'
    new_html, n = re.subn(pat, lambda m: payload, html, count=1, flags=re.DOTALL)
    if n == 0:
        raise RuntimeError(f"模板裡找不到 const {name} = ...; 無法替換")
    return new_html


def _fmt_likes(n):
    if not n:
        return "-"
    if n >= 10000:
        return ("%.1f" % (n / 10000)).rstrip("0").rstrip(".") + "萬"
    return "{:,}".format(n)


def build_video_hooks(candidates, group_names, limit=4):
    out = []
    for c in candidates:
        if not c.get("has_video"):
            continue
        first = re.split(r"[ 　]", (c.get("hook") or "").strip())[0]
        out.append({
            "author": c["author"],
            "likes": _fmt_likes(c.get("likes")),
            "url": ("https://www.threads.com" + c["url"]) if c["url"].startswith("/") else c["url"],
            "hook": c.get("hook", ""),
            "first": first,
            "group": c.get("group", "G1"),
            "group_name": c.get("group_name", group_names.get(c.get("group", "G1"), "")),
            "template": "⭐⭐⭐",
            "note": "⚠️ 上面這句是貼文 caption，不是影片裡真正的第一句；想拿到影片內口白需要實際看影片。",
        })
        if len(out) >= limit:
            break
    return out


def render(template_html, snapshot_date, candidates, scripts, video_hooks):
    # 卡片用欄位：把內部欄位收斂成儀表板 schema
    cards = []
    for c in candidates:
        cards.append({
            "id": c["id"], "author": c["author"], "verified": c.get("verified", False),
            "date": c["date"], "url": c["url"], "likes": c.get("likes"),
            "likes_verified": c.get("likes_verified", False),
            "comments": c.get("comments"), "shares": c.get("shares"),
            "has_video": c.get("has_video", False), "hook": c.get("hook", ""),
            "summary": c.get("summary", ""), "group": c.get("group", "G1"),
            "group_name": c.get("group_name", ""), "hook_type": c.get("hook_type", ""),
            "imitate_score": c.get("imitate_score", 3), "imitate_note": c.get("imitate_note", ""),
            "is_new": c.get("is_new", False),
        })
    data = {"snapshot_date": snapshot_date, "candidates": cards}

    html = template_html
    html = _replace_const(html, "DATA", data)
    html = _replace_const(html, "SCRIPTS", scripts)
    html = _replace_const(html, "VIDEO_HOOKS", video_hooks)
    html = re.sub(r"快照日期：[0-9-]{10}", "快照日期：" + snapshot_date, html)
    html = re.sub(r'"snapshot_date":"[0-9-]{10}"', '"snapshot_date":"' + snapshot_date + '"', html)

    # 防呆：三個 const 必須是合法 JSON
    for name in ["DATA", "SCRIPTS", "VIDEO_HOOKS"]:
        m = re.search(r"const " + name + r"\s*=\s*(\{.*?\}|\[.*?\]);", html, re.DOTALL)
        json.loads(m.group(1))
    return html
