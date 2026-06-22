# Threads 投資監測儀表板（獨立版）

每天自動：抓 Threads 熱門投資/理財貼文 → 篩選分群 → 產生儀表板 `index.html` → 推上 GitHub Pages，並產出 4 支「廣告腳本框架」供人工填寫。

**完全獨立**：純 Python + Playwright，不依賴 Claude、Cowork 或任何特定帳號。換帳號／換人維護，只要改 `config.yaml` 和 GitHub Secrets 即可。

---

## 目錄結構

```
threads-dashboard-tool/
├── config.yaml                  # ★ 所有設定（關鍵字、門檻、分群、懶人包、repo）
├── requirements.txt
├── src/
│   ├── run.py                   # 主流程（入口）
│   ├── scraper.py               # Playwright 抓 Threads
│   ├── filters.py               # 篩選（讚數/日期/排除明牌）+ 分群 G1–G8
│   ├── hooks.py                 # 39 個開頭鉤子模板
│   ├── scripts.py               # 產生「腳本框架」（不寫死、不呼叫 API）
│   ├── render.py                # 把資料注入 HTML 模板
│   ├── publish.py               # 推 GitHub（本機/跨 repo 用）
│   └── state.py                 # 跨天狀態（is_new / 熱度 / 7 天輪替）
├── templates/
│   └── dashboard.html.template  # 儀表板外觀（CSS/JS 都在這，含 SUGGESTIONS、HOOK_LIB）
├── data/
│   └── state.json               # 自動更新，請一起 commit 才能跨天記憶
└── .github/workflows/daily.yml  # 每天定時跑（GitHub Actions）
```

---

## 設定（只改 config.yaml）

- `search_keywords`：要掃的關鍵字
- `min_likes` / `days_window`：讚數門檻、幾天內
- `exclude_patterns`：命中就排除（報明牌、拉群、詐騙字眼）
- `groups`：G1–G8 分群關鍵字
- `packs` / `pack_hints`：5 份懶人包與對應提示
- `max_cards`：卡片數
- `publish.repo` / `branch` / `index_path`：要推到哪

---

## 兩種跑法

### A. GitHub Actions 自動跑（推薦，連 PAT 都不用）

把本工具放進**儀表板那個 repo**（`kolable006-ui/threads-dashboard`）：

1. 複製整個資料夾到 repo 根目錄並推上去。
2. repo → **Settings → Actions → General → Workflow permissions** 選 **Read and write**。
3. （選用）若要看到更多結果，repo → **Settings → Secrets → Actions** 新增 `THREADS_COOKIE`。
4. 完成。每天 UTC 04:00（台灣 12:00）自動跑；也可在 **Actions** 分頁手動 **Run workflow**。

Actions 用 GitHub 內建的 `GITHUB_TOKEN` 寫回 repo，**不需要任何 PAT**。

### B. 本機手動跑

```bash
pip install -r requirements.txt
python -m playwright install chromium

# 推 GitHub 需要 token（擇一）：
export GH_TOKEN=ghp_你的PAT          # 或
export GITHUB_TOKEN=...

python src/run.py                    # 抓 + 產 + 推
python src/run.py --no-publish       # 只產出 build/index.html，不推
python src/run.py --headful          # 顯示瀏覽器視窗除錯
python src/run.py --dry-run raw.json # 用現成原始貼文 JSON 跑（不開瀏覽器）
```

---

## Token / 安全

- 程式**不會**把 token 寫進任何檔案，一律從環境變數讀（`GH_TOKEN` 或 `GITHUB_TOKEN`）。
- ⚠️ 舊版工具曾把 PAT 明文寫在 SKILL.md 裡並推上公開 repo。**建議你到 GitHub → Settings → Developer settings → Personal access tokens 把那顆舊 PAT 作廢（Revoke）並重新產生一顆**，尤其你打算換帳號時更該如此。新版完全不需要把 token 放進程式碼。

---

## 廣告腳本是「框架」，不是成品

`scripts.py` 會挑出改編潛力高、且非個股/明牌的貼文，幫你：

- 從 39 個鉤子模板挑一個（4 支盡量分屬不同類別，並避開 7 天內用過的來源貼文）
- 建議對應哪一份懶人包
- 產出含三條鐵則的**空白逐字稿框架**（`＿＿` 留給你填）

三條鐵則：① 開頭用模板改寫（≤15 字）② 前 2 句帶出懶人包好處 ③ 結尾固定 CTA「點擊下方按鈕，填寫表單，免費領取懶人包」。框架本身會提醒**不要寫保證獲利、收益承諾或個股買賣建議**（Meta 廣告政策與法遵考量）。

---

## Threads 改版了怎麼辦？

抓取邏輯集中在 `src/scraper.py` 的 `_PARSE_JS`（在頁面裡跑的 JS）。若哪天抓不到資料，多半是 Threads 改了 DOM，更新這段選擇器即可，其餘模組不受影響。未登入時每個關鍵字大約只看得到前 4 則且部分讚數隱藏；設定 `THREADS_COOKIE` 可改善。

## 注意事項

- 排除明顯詐騙、報明牌貼文（見 `exclude_patterns`，可自行增修）。
- `imitate_score` 自動給 3 分並標註「請人工覆核」——自動分類無法取代人工判斷貼文的改編潛力。
- 抓不到讚數的貼文會標「未驗證、僅供觀察」，不會假裝它通過了 `min_likes` 門檻。
