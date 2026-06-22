# -*- coding: utf-8 -*-
"""把產生好的 index.html 推到 GitHub。

Token 來源（擇一，皆從環境變數讀，絕不寫死）：
  - GH_TOKEN      ：自己的 PAT（跨 repo 用）
  - GITHUB_TOKEN  ：GitHub Actions 內建（同 repo 用，最推薦，連 PAT 都不用）

在 GitHub Actions 同 repo 情境下，直接用 actions/checkout 取得的工作目錄 git 推送即可，
本模組也支援獨立 clone 推送（本機執行用）。
"""
import os
import subprocess
import tempfile


def _run(cmd, cwd=None, check=True):
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip())
        if check:
            raise RuntimeError(f"指令失敗：{' '.join(cmd)}")
    return r


def get_token():
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise RuntimeError(
            "找不到 token。請設定環境變數 GH_TOKEN（PAT）或 GITHUB_TOKEN（Actions 內建）。"
        )
    return tok


def publish(html, pub_cfg, snapshot_date):
    token = get_token()
    repo = pub_cfg["repo"]
    branch = pub_cfg.get("branch", "main")
    index_path = pub_cfg.get("index_path", "index.html")
    url = f"https://x-access-token:{token}@github.com/{repo}.git"

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = os.path.join(tmp, "repo")
        _run(["git", "clone", "--depth=1", "-b", branch, url, repo_dir])
        target = os.path.join(repo_dir, index_path)
        with open(target, "w", encoding="utf-8") as f:
            f.write(html)
        _run(["git", "config", "user.email", pub_cfg.get("commit_email", "auto@local")], cwd=repo_dir)
        _run(["git", "config", "user.name", pub_cfg.get("commit_name", "Dashboard Bot")], cwd=repo_dir)
        _run(["git", "add", index_path], cwd=repo_dir)
        diff = _run(["git", "diff", "--cached", "--quiet"], cwd=repo_dir, check=False)
        if diff.returncode == 0:
            print("[publish] 內容無變化，跳過 commit。")
            return False
        _run(["git", "commit", "-m", f"Daily update {snapshot_date}"], cwd=repo_dir)
        _run(["git", "push", "origin", branch], cwd=repo_dir)
        print(f"[publish] 已推送 {snapshot_date} 到 {repo}@{branch}")
        return True
