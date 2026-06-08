#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harvest_ai_words.py — 收割 AI 在判断阶段发现的疑似判词，合并进候选库

AI 在 Step 5 读条款时可能发现 hits.json 没覆盖的判决性语言。
按 SKILL.md 约定，AI 会把这些词写进工作区 md 的 `## AI发现疑似判词` 表格。

本脚本：
1. 解析该表格（疑似判词 | 原文摘要 | 出处 | 建议分类）
2. 合并进 workspace/<项目>.candidates.json（去重、标 source=ai_discovery）
3. 不自动入库 keywords.json，仍走 promote_candidates.py 人审流程

用法：
    python harvest_ai_words.py <工作区.md> [--out candidates.json]
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


def main():
    if len(sys.argv) < 2:
        print("用法: python harvest_ai_words.py <工作区.md> [--out candidates.json]")
        sys.exit(1)

    md_path = sys.argv[1]
    if not Path(md_path).exists():
        print("✗ 文件不存在: %s" % md_path)
        sys.exit(1)

    out = None
    for i, a in enumerate(sys.argv):
        if a == "--out" and i + 1 < len(sys.argv):
            out = sys.argv[i + 1]

    if not out:
        stem = Path(md_path).stem.replace(".工作区", "")
        out = str(Path(md_path).parent / (stem + ".candidates.json"))

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
    print("\n提示：这些词仍需 promote_candidates.py 人审后才入库 keywords.json。")


if __name__ == "__main__":
    main()
