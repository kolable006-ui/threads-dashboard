# -*- coding: utf-8 -*-
"""用 Playwright 無頭瀏覽器抓 Threads 搜尋結果。

注意：
- 未登入時，Threads 每個關鍵字大約只看得到前 4 則，且部分讚數會被隱藏。
- 若提供 THREADS_COOKIE 環境變數（從已登入瀏覽器複製的 cookie 字串），
  可看到更多結果與完整讚數。非必要。
- Threads 的 DOM 會改版，若哪天抓不到資料，多半要更新這裡的選擇器。
  解析邏輯集中在 _PARSE_JS，改一個地方就好。
"""
import os
import re
import time
import urllib.parse

# 在頁面裡執行的解析腳本：回傳每則貼文的結構化資料。
# 邏輯：找出所有含 /@handle/post/<id> 連結的貼文容器，往上找文章節點，
# 取作者、貼文 id、內文、讚/留言/分享、是否有影片。
_PARSE_JS = r"""
() => {
  const num = (s) => {
    if (!s) return null;
    s = s.trim().replace(/,/g, '');
    let m = s.match(/([\d.]+)\s*萬/);
    if (m) return Math.round(parseFloat(m[1]) * 10000);
    m = s.match(/([\d.]+)\s*[kK]/);
    if (m) return Math.round(parseFloat(m[1]) * 1000);
    m = s.match(/^\d+$/);
    return m ? parseInt(s, 10) : null;
  };

  const seen = new Set();
  const out = [];
  // 找所有貼文連結
  const links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
  for (const a of links) {
    const mm = a.getAttribute('href').match(/\/@([^/]+)\/post\/([^/?#]+)/);
    if (!mm) continue;
    const author = mm[1];
    const pid = mm[2];
    if (seen.has(pid)) continue;
    // 找貼文容器：往上找最近的有意義區塊
    let node = a;
    for (let i = 0; i < 8 && node.parentElement; i++) node = node.parentElement;
    const text = (node.innerText || '').trim();
    if (text.length < 6) continue;
    seen.add(pid);

    // 影片判定：嚴格 — 要有 video 元素或「已靜音」按鈕
    const hasVideo = !!node.querySelector('video') ||
                     /已靜音/.test(node.innerText) ||
                     !!node.querySelector('[aria-label*="Video"]');

    // 嘗試抓數字：讚/留言/分享通常是 button 內的數字
    const stats = {likes: null, comments: null, shares: null};
    const btns = Array.from(node.querySelectorAll('[role="button"], button'));
    for (const b of btns) {
      const lbl = (b.getAttribute('aria-label') || '') + ' ' + (b.innerText || '');
      const n = num((b.innerText || '').replace(/[^\d.,萬kK]/g, ''));
      if (n == null) continue;
      if (/讚|like/i.test(lbl) && stats.likes == null) stats.likes = n;
      else if (/留言|comment/i.test(lbl) && stats.comments == null) stats.comments = n;
      else if (/轉|分享|share|repost/i.test(lbl) && stats.shares == null) stats.shares = n;
    }

    // 主要方法：Threads 貼文頁尾會把「讚/留言/轉發/分享」以一串純數字行呈現。
    // 取 innerText 結尾連續的純數字行，第一個＝讚數（比按鈕解析可靠很多，未登入也常看得到）。
    {
      const rawLines = (node.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
      const tail = [];
      for (let i = rawLines.length - 1; i >= 0 && tail.length < 4; i--) {
        if (/^[\d.,]+\s*[萬kK]?$/.test(rawLines[i])) {
          const v = num(rawLines[i]);
          if (v == null) break;
          tail.unshift(v);
        } else break;
      }
      if (tail.length) {
        stats.likes = tail[0];
        if (tail.length >= 2 && stats.comments == null) stats.comments = tail[1];
        if (tail.length >= 4 && stats.shares == null) stats.shares = tail[3];
      }
    }

    // 時間：找 time 元素或日期字串
    let dateStr = null;
    const t = node.querySelector('time');
    if (t) dateStr = t.getAttribute('datetime') || t.getAttribute('title') || t.innerText;

    out.push({
      author, id: pid,
      url: `/@${author}/post/${pid}`,
      text: text.slice(0, 1200),
      likes: stats.likes, comments: stats.comments, shares: stats.shares,
      has_video: hasVideo,
      date_raw: dateStr,
    });
  }
  return out;
}
"""


def _apply_cookies(context):
    cookie = os.environ.get("THREADS_COOKIE", "").strip()
    if not cookie:
        print("[cookie] 未設定 THREADS_COOKIE，以未登入訪客模式抓取（每關鍵字約 4 則、部分讚數隱藏）。")
        return
    # 容錯：使用者可能把整行「cookie: a=1; b=2」一起貼進來，去掉開頭的 cookie: 前綴
    if cookie.lower().startswith("cookie:"):
        cookie = cookie.split(":", 1)[1].strip()
    pairs = []
    for part in cookie.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            continue
        pairs.append((k, v))
    jar = []
    # 同時掛到 .threads.com 與 .threads.net，避免網域不符導致整批失效
    for domain in (".threads.com", ".threads.net"):
        for k, v in pairs:
            jar.append({"name": k, "value": v, "domain": domain, "path": "/"})
    if jar:
        context.add_cookies(jar)
        names = {k for k, _ in pairs}
        has_session = "sessionid" in names
        print(f"[cookie] 已載入 {len(pairs)} 個 cookie；sessionid={'有' if has_session else '無'}。"
              + ("" if has_session else " 注意：沒有 sessionid，Threads 仍會視為未登入！"))


def scrape(keywords, scroll_rounds=3, page_wait_ms=3500, headless=True):
    """回傳 list[dict] 原始貼文（未去重跨關鍵字之外的處理）。"""
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="zh-TW",
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
        )
        _apply_cookies(context)
        page = context.new_page()
        for kw in keywords:
            url = "https://www.threads.com/search?q=" + urllib.parse.quote(kw) + "&serp_type=default"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(page_wait_ms)
                for _ in range(max(0, scroll_rounds)):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1200)
                items = page.evaluate(_PARSE_JS)
            except Exception as e:
                print(f"[scrape] 關鍵字「{kw}」失敗：{e}")
                items = []
            for it in items:
                it["keyword"] = kw
                results.setdefault(it["id"], it)  # 跨關鍵字去重，保留第一次
            print(f"[scrape] {kw}: 取得 {len(items)} 則")
        browser.close()
    return list(results.values())
