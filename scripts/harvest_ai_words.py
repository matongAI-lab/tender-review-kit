#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harvest_ai_words.py — 收割 AI 在判断阶段发现的疑似判词，合并进候选库 + 回扫当前标书

AI 在 Step 5 读条款时可能发现 hits.json 没覆盖的判决性语言。
按 SKILL.md 约定，AI 会把这些词写进工作区 md 的 `## AI发现疑似判词` 表格。

本脚本：
1. 解析该表格（疑似判词 | 原文摘要 | 出处 | 建议分类）
2. 合并进 workspace/<项目>.candidates.json（去重、标 source=ai_discovery）
3. 拿新发现的词回扫当前 lines.txt（--lines），找出 AI 没看到的行 → 补扫命中报告
4. 不自动入库 keywords.json，仍走 promote_candidates.py 人审流程

用法：
    python harvest_ai_words.py <工作区.md> [--lines <lines.txt>] [--out candidates.json]
"""
import sys
import re
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_SCOPE_MAP = {
    "primary": "primary",
    "secondary": "secondary",
    "customization": "customization",
    "certifications": "certifications",
    "bid_phase": "bid_phase",
    "evaluation_phase": "evaluation_phase",
    "contract_phase": "contract_phase",
}


def parse_ai_section(md_path):
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()

    in_section = False
    header_found = False
    results = []

    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+AI发现疑似判词", stripped):
            in_section = True
            continue
        if in_section and re.match(r"^##\s+", stripped):
            break
        if not in_section:
            continue
        if re.match(r"^\|[\s\-:|]+\|", stripped):
            header_found = True
            continue
        if not header_found:
            if "|" in stripped and "疑似判词" in stripped:
                continue
            continue

        cells = [c.strip() for c in stripped.split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue

        word = cells[0]
        context = cells[1]
        source_line = cells[2] if len(cells) >= 3 else ""
        category_hint = cells[3] if len(cells) >= 4 else ""

        scope = ["bid_phase"]
        category = "primary"
        if "/" in category_hint:
            parts = [p.strip() for p in category_hint.split("/")]
            if len(parts) == 2:
                category = parts[0] if parts[0] in _SCOPE_MAP else "primary"
                scope = [p for p in parts[1:] if p in _SCOPE_MAP] or ["bid_phase"]
        elif category_hint in _SCOPE_MAP:
            if category_hint in ("bid_phase", "evaluation_phase", "contract_phase"):
                scope = [category_hint]
            else:
                category = category_hint

        line_no = None
        m = re.search(r"行(\d+)", source_line)
        if m:
            line_no = int(m.group(1))

        results.append({
            "word": word,
            "status": "pending_review",
            "source": "ai_discovery",
            "suggested_scope": scope,
            "suggested_category": category,
            "occurrences": 1,
            "contexts": [context[:120]],
            "source_line": line_no,
        })

    return results


def merge_into_candidates(found, out_path):
    existing = {}
    if Path(out_path).exists():
        try:
            data = json.loads(Path(out_path).read_text(encoding="utf-8"))
            for c in data.get("candidates", []):
                existing[c["word"]] = c
        except (json.JSONDecodeError, KeyError):
            pass

    added = 0
    for c in found:
        if c["word"] in existing:
            entry = existing[c["word"]]
            if "ai_discovery" not in entry.get("source", ""):
                entry["source"] = entry.get("source", "pattern") + "+ai_discovery"
            ctx = entry.get("contexts", [])
            for new_ctx in c["contexts"]:
                if new_ctx not in ctx:
                    ctx.append(new_ctx)
                    if len(ctx) > 5:
                        ctx = ctx[:5]
            entry["contexts"] = ctx
        else:
            existing[c["word"]] = c
            added += 1

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"candidates": list(existing.values())}, f,
                  ensure_ascii=False, indent=2)

    return added, len(existing)


def rescan_lines(found, lines_path, worklist_path):
    """拿 AI 发现的词回扫 lines.txt，找出工作区 md 中没引用到的行"""
    rows = []
    with open(lines_path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if "\t" in raw:
                no, txt = raw.split("\t", 1)
                try:
                    rows.append((int(no), txt))
                    continue
                except ValueError:
                    pass
            if raw:
                rows.append((len(rows) + 1, raw))

    md_text = Path(worklist_path).read_text(encoding="utf-8")
    cited_lines = set()
    for m in re.finditer(r"行(\d+)", md_text):
        cited_lines.add(int(m.group(1)))

    words = [c["word"] for c in found]
    missed = []
    for lineno, text in rows:
        if lineno in cited_lines:
            continue
        for w in words:
            if w in text:
                missed.append({"line": lineno, "word": w, "text": text})
                break

    return missed


def main():
    if len(sys.argv) < 2:
        print("用法: python harvest_ai_words.py <工作区.md> [--lines <lines.txt>] [--out candidates.json]")
        sys.exit(1)

    md_path = sys.argv[1]
    if not Path(md_path).exists():
        print("✗ 文件不存在: %s" % md_path)
        sys.exit(1)

    out = None
    lines_path = None
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--out" and i + 1 < len(sys.argv):
            out = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--lines" and i + 1 < len(sys.argv):
            lines_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    stem = Path(md_path).stem.replace(".工作区", "")
    ws_dir = Path(md_path).parent

    if not out:
        out = str(ws_dir / (stem + ".candidates.json"))

    if not lines_path:
        auto = ws_dir / (stem + ".lines.txt")
        if auto.exists():
            lines_path = str(auto)

    found = parse_ai_section(md_path)

    if not found:
        print("OK AI发现疑似判词: 0 条（工作区中无该 section 或表格为空）")
        return

    added, total = merge_into_candidates(found, out)

    print("OK AI发现疑似判词: %d 条，新增 %d，候选库累计 %d" % (len(found), added, total))
    print("out=%s" % out)
    print("--- AI 发现 ---")
    for c in found:
        print("  %s (scope=%s cat=%s) | %s"
              % (c["word"], "/".join(c["suggested_scope"]),
                 c["suggested_category"], c["contexts"][0][:50]))

    if lines_path and Path(lines_path).exists():
        missed = rescan_lines(found, lines_path, md_path)
        if missed:
            print("\n⚠ 补扫命中 %d 条（AI 发现的词在当前标书中还出现在以下未引用行）：" % len(missed))
            for m in missed[:20]:
                print("  行%-5d [%s] %s" % (m["line"], m["word"], m["text"][:60]))
            if len(missed) > 20:
                print("  ... 还有 %d 条" % (len(missed) - 20))
            print("→ 建议让 AI 检查这些行，判断是否需要纳入清单。")
        else:
            print("\n✓ 补扫：AI 发现的词在当前标书中无遗漏行。")
    elif lines_path:
        print("\n⚠ 未找到 %s，跳过补扫。" % lines_path)
    else:
        print("\n⚠ 未指定 --lines 且未自动找到 lines.txt，跳过补扫。")

    print("\n提示：这些词仍需 promote_candidates.py 人审后才入库 keywords.json。")


if __name__ == "__main__":
    main()
