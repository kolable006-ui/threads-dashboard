#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主流程：抓取 → 篩選分群 → 狀態(is_new/輪替) → 卡片/影片/腳本 → 產 HTML → 推 GitHub。

用法：
    python src/run.py                 # 完整跑（抓 + 產 + 推）
    python src/run.py --no-publish    # 不推 GitHub，只在 build/index.html 產出
    python src/run.py --dry-run FILE  # 用現成的原始貼文 JSON（list[dict]）跑，跳過瀏覽器
    python src/run.py --date 2026-06-04
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import yaml  # noqa: E402
import filters as F  # noqa: E402
import scripts as S  # noqa: E402
import render as R  # noqa: E402
import state as ST  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--dry-run", metavar="RAW_JSON", help="用現成原始貼文 JSON，不開瀏覽器")
    ap.add_argument("--date", help="覆寫快照日期 YYYY-MM-DD")
    ap.add_argument("--headful", action="store_true", help="顯示瀏覽器視窗（除錯用）")
    args = ap.parse_args()

    cfg = load_cfg()
    today = datetime.now(timezone.utc)
    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    today_str = today.strftime("%Y-%m-%d")

    # 1) 取得原始貼文
    if args.dry_run:
        with open(args.dry_run, encoding="utf-8") as f:
            raw = json.load(f)
        print(f"[run] dry-run：載入 {len(raw)} 則原始貼文")
    else:
        import scraper
        raw = scraper.scrape(cfg["search_keywords"],
                             scroll_rounds=cfg.get("scroll_rounds", 3),
                             page_wait_ms=cfg.get("page_wait_ms", 3500),
                             headless=not args.headful)

    # 2) 篩選 + 分群
    candidates = F.apply_filters(raw, cfg, today)
    candidates = candidates[: cfg.get("max_cards", 14)]
    print(f"[run] 篩選後卡片：{len(candidates)}")

    # 3) 狀態：is_new / 熱度上升 / 腳本輪替
    state = ST.load()
    new_cnt, rising = ST.mark(state, candidates, today_str)
    recent_ids, recent_cats = ST.recent_script_ids(state, days=7, today=today)

    # 4) 影片 caption + 腳本框架
    group_names = {gid: g.get("name", gid) for gid, g in cfg["groups"].items()}
    video_hooks = R.build_video_hooks(candidates, group_names, limit=4)
    scripts = S.build_frameworks(candidates, cfg,
                                 recent_used_ids=recent_ids,
                                 recent_categories=recent_cats)
    ST.record_scripts(state, scripts, today_str)

    # 5) 產 HTML
    with open(os.path.join(ROOT, "templates", "dashboard.html.template"), encoding="utf-8") as f:
        template = f.read()
    html = R.render(template, today_str, candidates, scripts, video_hooks)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    out_path = os.path.join(ROOT, "build", "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[run] 已產生 {out_path}（{len(html)} bytes）")

    # 6) 推 GitHub
    pushed = False
    if not args.no_publish:
        import publish
        pushed = publish.publish(html, cfg["publish"], today_str)

    # 狀態存檔（推成功 or 不推時都更新；避免重複算 new）
    ST.save(state)

    # 7) 摘要
    print("\n===== 摘要 " + today_str + " =====")
    print(f"卡片 {len(candidates)}｜新增 {new_cnt}｜熱度上升 {len(rising)}｜影片 {len(video_hooks)}｜腳本 {len(scripts)}")
    if candidates:
        top = candidates[0]
        print(f"最熱：@{top['author']}（{top['likes']}）")
    print("腳本來源：", [s["url"].split("/")[-1] for s in scripts])
    print("推送：", "成功" if pushed else ("略過" if args.no_publish else "無變化"))


if __name__ == "__main__":
    main()
