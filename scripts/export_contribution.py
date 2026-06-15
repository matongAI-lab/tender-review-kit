#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_contribution.py — 脱敏导出候选词，方便社区贡献回项目

读 workspace 里的 candidates.json，去掉原文片段（保护标书隐私），
去重现有 keywords.json，输出干净的贡献文件。

隐私边界:
  - 贡献完全自愿,不给也能正常使用工具。
  - 导出不包含标书原文、项目名、行号上下文、Excel、工作区全文。
  - 导出只包含判词短语、建议分类、建议 scope、发现方式、出现次数。
  - --github 只创建 GitHub Issue 供维护者审核,不会自动合并进总词库。

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
    """从 candidates.json（程序补词）合并去重"""
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


def load_local_keywords():
    """从用户本地词库（AI 发现已直接入库的词）读出贡献候选"""
    local_path = BASE / "data" / "local_keywords.json"
    if not local_path.exists():
        return []
    try:
        data = json.loads(local_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    out = []
    for cat in data.get("categories", []):
        cid = cat.get("id", "primary")
        for w in cat.get("words", []):
            if isinstance(w, dict):
                out.append({
                    "word": w["word"],
                    "scope": w.get("scope", []),
                    "category": cid,
                    "source": "local_keywords(ai_discovery)",
                    "count": 1,
                })
            else:
                out.append({
                    "word": w,
                    "scope": [],
                    "category": cid,
                    "source": "local_keywords(ai_discovery)",
                    "count": 1,
                })
    return out


def build_markdown(candidates):
    lines = []
    lines.append("## 判词贡献 / Keyword Contribution")
    lines.append("")
    lines.append("以下判词由工具扫描 + AI 发现，已脱敏。")
    lines.append("")
    lines.append("隐私声明：本贡献不含标书原文、项目名、行号上下文、Excel、工作区全文或用户本地词库文件；只包含用户自愿分享的判词短语及分类/scope 等元数据。")
    lines.append("")
    lines.append("请维护者审核后再合并进 `data/keywords.json`。")
    lines.append("")
    lines.append("| 判词 | 建议分类 | 建议 scope | 发现方式 | 出现次数 |")
    lines.append("|------|----------|------------|----------|----------|")
    for c in sorted(candidates, key=lambda x: (-x["count"], x["word"])):
        src = c["source"]
        if "local_keywords" in src and "pattern" in src:
            source_label = "AI发现+程序补词"
        elif "local_keywords" in src or "ai_discovery" in src or "ai" in src:
            source_label = "AI语义发现"
        elif "+" in src:
            source_label = "正则+AI"
        else:
            source_label = "正则模式"
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
    skip_local = False

    for a in args:
        if a == "--github":
            mode = "github"
        elif a == "--pr":
            mode = "pr"
        elif a == "--no-local":
            skip_local = True
        else:
            paths.append(a)

    # 两个来源：候选库（程序补词通道）+ 本地词库（AI 发现通道）
    if not paths:
        ws = BASE / "workspace"
        if ws.exists():
            paths = [str(p) for p in ws.glob("*.candidates.json")]

    existing = load_existing_words()
    candidates = load_candidates(paths) if paths else []
    local_words = [] if skip_local else load_local_keywords()

    # 合并两个来源，去重
    by_word = {}
    for c in candidates + local_words:
        if c["word"] in by_word:
            if "local_keywords" in c["source"] and "ai" not in by_word[c["word"]]["source"]:
                by_word[c["word"]]["source"] += "+local_keywords"
            continue
        by_word[c["word"]] = c

    all_words = list(by_word.values())

    if not all_words:
        print("没有找到任何待贡献的词（workspace 无 candidates.json，data/local_keywords.json 也不存在）")
        sys.exit(1)

    new = [c for c in all_words if c["word"] not in existing]

    if not new:
        print("✓ 所有候选词已在开源 keywords.json 中，无需贡献。")
        return

    print("待贡献来源汇总：")
    print("  - 候选库(candidates.json) %d 个文件 / %d 词" % (len(paths), len(candidates)))
    print("  - 本地词库(local_keywords.json) %d 词" % len(local_words))
    print("  合并去重后 %d 词，其中 %d 个是新词（开源库未收录）"
          % (len(all_words), len(new)))
    print()
    print("隐私声明：贡献完全自愿；本导出不包含标书原文、项目名、行号上下文、Excel 或工作区全文。")
    print("导出内容只包含判词短语、建议分类、scope、发现方式和出现次数。")
    print("--github 只会创建 GitHub Issue 供维护者审核，不会自动合并进总词库。")

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
