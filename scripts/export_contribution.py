#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_contribution.py — 脱敏导出候选词，方便社区贡献回项目

读 workspace 里的 candidates.json，去掉原文片段（保护标书隐私），
去重现有 keywords.json，输出干净的贡献文件。

三种提交方式：
  1. --github  自动创建 GitHub Issue（需装 gh CLI 并登录）
  2. --pr      自动创建 PR 到 contributions/ 目录（需装 gh CLI）
  3. 默认      输出到 contribution.md，手动粘贴到 Issue

用法：
    python export_contribution.py <candidates.json> [candidates2.json ...]
    python export_contribution.py workspace/*.candidates.json --github
    python export_contribution.py workspace/*.candidates.json --pr
"""
import sys
import json
import re
import subprocess
from pathlib import Path
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
KW_PATH = BASE / "data" / "keywords.json"


def load_existing_words():
    words = set()
    if KW_PATH.exists():
        data = json.loads(KW_PATH.read_text(encoding="utf-8"))
        for cat in data.get("categories", []):
            for w in cat.get("words", []):
                words.add(w["word"] if isinstance(w, dict) else w)
    return words


def load_candidates(paths):
    all_candidates = {}
    for p in paths:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for c in data.get("candidates", []):
            word = c.get("word", "")
            if not word:
                continue
            if word not in all_candidates:
                all_candidates[word] = {
                    "word": word,
                    "scope": c.get("suggested_scope", []),
                    "category": c.get("suggested_category", "primary"),
                    "source": c.get("source", "pattern"),
                    "count": c.get("occurrences", 1),
                }
            else:
                all_candidates[word]["count"] += c.get("occurrences", 1)
                if c.get("source") == "ai_discovery" and "ai" not in all_candidates[word]["source"]:
                    all_candidates[word]["source"] += "+ai_discovery"
    return list(all_candidates.values())


def build_markdown(candidates):
    lines = []
    lines.append("## 判词贡献 / Keyword Contribution")
    lines.append("")
    lines.append("以下判词由工具扫描 + AI 发现，已脱敏（不含原文）。")
    lines.append("请维护者审核后通过 `promote_candidates.py` 入库。")
    lines.append("")
    lines.append("| 判词 | 建议分类 | 建议 scope | 发现方式 | 出现次数 |")
    lines.append("|------|----------|------------|----------|----------|")
    for c in sorted(candidates, key=lambda x: (-x["count"], x["word"])):
        source_label = "AI语义" if "ai" in c["source"] else "正则模式"
        if "+" in c["source"]:
            source_label = "正则+AI"
        lines.append("| %s | %s | %s | %s | %d |"
                      % (c["word"], c["category"],
                         "/".join(c["scope"]) if c["scope"] else "—",
                         source_label, c["count"]))
    lines.append("")
    lines.append("---")
    lines.append("由 `tender-review-kit/export_contribution.py` 自动生成，%s" % date.today().isoformat())
    return "\n".join(lines)


def create_github_issue(md_body, count):
    title = "判词贡献：%d 个候选词" % count
    try:
        r = subprocess.run(
            ["gh", "issue", "create",
             "--repo", "matongAI-lab/tender-review-kit",
             "--title", title,
             "--body", md_body,
             "--label", "keyword-contribution"],
            capture_output=True, text=True, encoding="utf-8"
        )
        if r.returncode == 0:
            url = r.stdout.strip()
            print("✓ Issue 已创建: %s" % url)
            return True
        else:
            print("✗ 创建 Issue 失败: %s" % r.stderr.strip())
            if "label" in r.stderr:
                print("  提示: label 'keyword-contribution' 不存在，尝试不带 label...")
                r2 = subprocess.run(
                    ["gh", "issue", "create",
                     "--repo", "matongAI-lab/tender-review-kit",
                     "--title", title,
                     "--body", md_body],
                    capture_output=True, text=True, encoding="utf-8"
                )
                if r2.returncode == 0:
                    print("✓ Issue 已创建: %s" % r2.stdout.strip())
                    return True
            return False
    except FileNotFoundError:
        print("✗ 未找到 gh 命令。请先安装 GitHub CLI: https://cli.github.com/")
        return False


def create_pr(md_body, count):
    contrib_dir = BASE / "contributions"
    contrib_dir.mkdir(exist_ok=True)

    filename = "contribution-%s.md" % date.today().isoformat()
    filepath = contrib_dir / filename

    filepath.write_text(md_body, encoding="utf-8")

    branch = "contrib/%s" % date.today().isoformat()
    title = "判词贡献：%d 个候选词" % count

    try:
        subprocess.run(["git", "checkout", "-b", branch], cwd=str(BASE),
                        capture_output=True, text=True)
        subprocess.run(["git", "add", str(filepath)], cwd=str(BASE),
                        capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "贡献 %d 个候选判词" % count],
                        cwd=str(BASE), capture_output=True, text=True)
        subprocess.run(["git", "push", "origin", branch], cwd=str(BASE),
                        capture_output=True, text=True)

        r = subprocess.run(
            ["gh", "pr", "create",
             "--repo", "matongAI-lab/tender-review-kit",
             "--title", title,
             "--body", md_body],
            cwd=str(BASE), capture_output=True, text=True, encoding="utf-8"
        )
        if r.returncode == 0:
            print("✓ PR 已创建: %s" % r.stdout.strip())
            return True
        else:
            print("✗ 创建 PR 失败: %s" % r.stderr.strip())
            print("  贡献文件已保存到: %s" % filepath)
            return False
    except FileNotFoundError:
        print("✗ 未找到 gh 命令。贡献文件已保存到: %s" % filepath)
        return False


def main():
    args = sys.argv[1:]
    mode = "file"
    paths = []

    for a in args:
        if a == "--github":
            mode = "github"
        elif a == "--pr":
            mode = "pr"
        else:
            paths.append(a)

    if not paths:
        ws = BASE / "workspace"
        if ws.exists():
            paths = [str(p) for p in ws.glob("*.candidates.json")]
        if not paths:
            print("用法: python export_contribution.py <candidates.json ...> [--github|--pr]")
            print("  或: cd 项目根目录, workspace/ 下有 candidates.json 时直接跑")
            sys.exit(1)

    existing = load_existing_words()
    candidates = load_candidates(paths)

    new = [c for c in candidates if c["word"] not in existing]

    if not new:
        print("✓ 所有候选词已在 keywords.json 中，无需贡献。")
        return

    print("候选词: %d 个（来自 %d 个文件），其中 %d 个是新词（不在 keywords.json 中）"
          % (len(candidates), len(paths), len(new)))

    md = build_markdown(new)

    if mode == "github":
        create_github_issue(md, len(new))
    elif mode == "pr":
        create_pr(md, len(new))
    else:
        out = BASE / "contribution.md"
        out.write_text(md, encoding="utf-8")
        print("✓ 贡献文件已导出: %s" % out)
        print("  请复制内容到 GitHub Issue: https://github.com/matongAI-lab/tender-review-kit/issues/new")
        print("  或直接跑: python export_contribution.py <files...> --github")


if __name__ == "__main__":
    main()
