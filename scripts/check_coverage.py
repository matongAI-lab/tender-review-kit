#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_coverage.py — 查漏护栏：撒网判决词命中 ↔ 废标清单覆盖反查

读 hits.json（撒网命中）+ 工作区 md（专项 AI 产出的废标清单，含"出处(行号)"列），
反查每个 in-scope（bid_phase / evaluation_phase）的 primary 命中行号是否被某条废标项覆盖。
未覆盖的列出 + 严重度——这是「内容不漏」的程序兜底，不让 AI 当自己的裁判。

关键：只解析「## …废标」表格里的行号，不碰专项 AI 自己写的"台账/处置"段，
      否则台账里那些"已排除"的行号会被误当成已覆盖，自欺欺人。

纯标准库（json/re），零依赖。不设阈值——全部未覆盖列出，由人/主对话定夺。

用法:
    python check_coverage.py <hits.json> <工作区.md> [--tolerance 0] [--strict] [--out coverage.json]
"""
import sys
import re
import json
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 强判决词：未覆盖时判 high
STRONG = ["否决", "废标", "无效投标", "拒收", "予以否决", "无效"]
# 出处行号:认 行103 / 行100-105,以及 第103行 / 第100-105行。
# 故意只认带"行"锚的写法——裸数字(如金额 450、数量 10、型号 L300)绝不当行号,
# 否则相邻数字会造成「假覆盖」(把没引用的命中误判成已覆盖)。
_LINE_RES = [
    re.compile(r"行\s*(\d+)\s*(?:[–\-~至]\s*(\d+))?"),          # 行103 / 行100-105
    re.compile(r"第\s*(\d+)\s*(?:[–\-~至]\s*(\d+))?\s*行"),      # 第103行 / 第100-105行
]


# 子节(###)含这些关键词时跳过其内表格(说明性/台账/自检性子节,非主清单)
SKIP_SUBHEADER_KW = ["台账", "处置", "核验", "对照", "发现", "建议", "边界", "排除", "锚点"]


def extract_disq_lines(md_text):
    """从「## …废标」节的主表格里提取引用行号。
    ## 切换 section;### 默认保持 section 内,但跳过说明性子节;# 一级关闭。"""
    refs = set()
    in_section, in_table = False, True
    for raw in md_text.splitlines():
        s = raw.strip()
        if s.startswith("## "):
            in_section = "废标" in s
            in_table = True
            continue
        if s.startswith("# ") and not s.startswith("## "):
            in_section = False
            continue
        if s.startswith("### "):
            in_table = not any(kw in s for kw in SKIP_SUBHEADER_KW)
            continue
        if in_section and in_table and s.startswith("|"):
            for rex in _LINE_RES:
                for m in rex.finditer(raw):
                    a = int(m.group(1))
                    b = int(m.group(2)) if m.group(2) else a
                    for ln in range(min(a, b), max(a, b) + 1):
                        refs.add(ln)
    return refs


def severity(word, scope):
    if any(t in word for t in STRONG) and "bid_phase" in scope:
        return "high"
    if "evaluation_phase" in scope:
        return "medium"
    return "low"


def main():
    ap = argparse.ArgumentParser(description="查漏护栏：撒网命中 ↔ 废标清单覆盖反查")
    ap.add_argument("hits")
    ap.add_argument("worklist", help="工作区 md（含废标清单）")
    ap.add_argument("--tolerance", type=int, default=0,
                    help="行号容差，默认 ±0（精确匹配；放宽会把相邻不同条款误判为已覆盖）")
    ap.add_argument("--strict", action="store_true",
                    help="存在 high 级未覆盖时以非零码退出（供自动流程 gate）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    hits = json.load(open(args.hits, encoding="utf-8"))
    md = open(args.worklist, encoding="utf-8").read()
    disq_lines = extract_disq_lines(md)
    tol = args.tolerance

    covered, uncovered, seen = [], [], set()
    for h in hits["hits"]["primary"]:
        scope = h.get("scope", [])
        if not ({"bid_phase", "evaluation_phase"} & set(scope)):
            continue  # 合同期等不在投标/评标的，跳过
        ln = h["line"]
        key = (ln, h["word"])
        if key in seen:
            continue
        seen.add(key)
        rec = {"line": ln, "word": h["word"], "scope": scope, "text": h.get("text", "")[:120]}
        if any(abs(ln - d) <= tol for d in disq_lines):
            covered.append(rec)
        else:
            rec["severity"] = severity(h["word"], scope)
            uncovered.append(rec)

    total = len(covered) + len(uncovered)
    order = {"high": 0, "medium": 1, "low": 2}
    uncovered.sort(key=lambda r: (order[r["severity"]], r["line"]))
    result = {
        "hits_file": args.hits,
        "worklist": args.worklist,
        "disq_referenced_lines": len(disq_lines),
        "in_scope_primary": total,
        "covered": len(covered),
        "uncovered": len(uncovered),
        "coverage_ratio": round(len(covered) / total, 3) if total else None,
        "uncovered_detail": uncovered,
    }
    out = Path(args.out) if args.out else Path(args.worklist).with_suffix(".coverage.json")
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    n_hi = sum(1 for u in uncovered if u["severity"] == "high")
    n_md = sum(1 for u in uncovered if u["severity"] == "medium")
    n_lo = sum(1 for u in uncovered if u["severity"] == "low")
    print("OK in_scope=%d covered=%d uncovered=%d ratio=%s"
          % (total, len(covered), len(uncovered), result["coverage_ratio"]))
    print("废标清单引用行号=%d 条 (容差±%d)" % (len(disq_lines), tol))
    print("未覆盖: high=%d medium=%d low=%d" % (n_hi, n_md, n_lo))
    print("--- 未覆盖明细（high 优先，前 20）---")
    for u in uncovered[:20]:
        print("  [%-6s] 行%-5d %s | %s" % (u["severity"], u["line"], u["word"], u["text"][:46]))
    print("out=%s" % out)

    if args.strict and n_hi > 0:
        print("✗ strict: 存在 %d 条 high 级未覆盖，非零退出" % n_hi)
        sys.exit(1)


if __name__ == "__main__":
    main()
