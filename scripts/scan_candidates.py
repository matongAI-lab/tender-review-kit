#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_candidates.py — 补词引擎：扫"像判决词、还没入库"的新短语

判词库是这个项目的核心；这是让它**自己长大**的引擎：
扫文本里符合判决句式、但不在现有 keywords.json 的短语 → 列为候选(pending_review)。
**绝不自动入库**（避免污染）——人确认后才手动加进 keywords.json。

识别策略（纯标准库，不依赖 LLM）：
- 句式模式：`视为X / 不予X / 取消X / 将不X / 被X处理 / 作为X处理 / 按X处理 / 驳回X`
- 位置邻近：紧邻已知判决词命中（±N 行）的优先（near_known=True，噪音更低）
- 去重：已在词库的跳过；候选累计出现次数

候选文件含**原文片段**（contexts），默认落在 `workspace/<项目>.candidates.json`——
随项目走、不进开源仓库（workspace/ 已被 .gitignore 整体忽略）。入库时 promote 只把
词+scope 转进 keywords.json，绝不带原文，确保 data/ 不沾任何用户标书内容。

用法:
    python scan_candidates.py <lines.txt> [--keywords data/keywords.json] [--hits hits.json] [--out workspace/<项目>.candidates.json]
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

PATTERNS = [
    r"视为[一-龥]{2,8}",
    r"不予[一-龥]{2,8}",
    r"取消[一-龥]{2,10}",
    r"将不[一-龥]{2,8}",
    r"被[一-龥]{1,4}处理",
    r"作为[一-龥]{2,6}处理",
    r"按[一-龥]{2,6}处理",
    r"驳回[一-龥]{2,6}",
]


def known_words(kw):
    s = set()
    for c in kw.get("categories", []):
        for w in c.get("words", []):
            s.add(w["word"] if isinstance(w, dict) else w)
    return s


CONTRACT_PHRASE_HINTS = ["承包人", "履行", "施工", "竣工", "质保期内", "乙方", "甲方",
                         "工程师", "监理", "验收", "试车", "签证", "结算",
                         "工程量", "工程款", "付款义务", "索赔", "不可抗力",
                         "违约", "赔偿", "质量保证期", "返修", "维护期"]
CONTRACT_PHRASE_IN_WORD = ["承包人", "乙方", "甲方", "验收", "试车", "工程师",
                           "结算", "工程量", "索赔", "不可抗力", "违约", "履约"]


def classify(phrase, context):
    scope = []
    if any(p in phrase for p in ["视为", "不予", "取消", "将不", "驳回"]):
        scope.append("bid_phase")
    if any(w in context for w in ["评标", "评审", "评委"]) and "evaluation_phase" not in scope:
        scope.append("evaluation_phase")
    if any(w in context for w in CONTRACT_PHRASE_HINTS) and "contract_phase" not in scope:
        scope.append("contract_phase")
    # 强规则:短语本身就是合同期(如"视为承包人实际完成的"/"视为验收通过")→ 强制只 contract_phase
    if any(w in phrase for w in CONTRACT_PHRASE_IN_WORD):
        scope = ["contract_phase"]
    if not scope:
        scope = ["evaluation_phase"]
    category = "primary"
    if any(w in phrase for w in ["接入", "加盖", "兼容", "原厂", "授权", "厂商"]):
        category = "customization"
    elif re.search(r"提供.{0,5}(报告|证书|认证|入网|许可)", phrase):
        category = "certifications"
    return scope, category


def load_lines(path):
    rows = []
    with open(path, encoding="utf-8") as f:
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
    return rows


def main():
    ap = argparse.ArgumentParser(description="补词引擎：扫疑似新判决词 → 候选区")
    ap.add_argument("lines_file")
    ap.add_argument("--keywords", default=None)
    ap.add_argument("--hits", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--proximity", type=int, default=3)
    args = ap.parse_args()

    base = Path(__file__).resolve().parent.parent
    kw = json.load(open(Path(args.keywords) if args.keywords else base / "data" / "keywords.json", encoding="utf-8"))
    known = known_words(kw)

    lines = load_lines(args.lines_file)
    line_map = {no: txt for no, txt in lines}

    hit_lines = set()
    if args.hits and Path(args.hits).exists():
        h = json.load(open(args.hits, encoding="utf-8"))
        for x in h.get("hits", {}).get("primary", []):
            hit_lines.add(x["line"])

    pats = [re.compile(p) for p in PATTERNS]
    cands = {}
    for no, txt in lines:
        near = (not hit_lines) or any(abs(no - hn) <= args.proximity for hn in hit_lines)
        for pat in pats:
            for m in pat.finditer(txt):
                ph = m.group(0)
                if ph in known:
                    continue
                ctx = " ".join(line_map.get(no + d, "") for d in (-2, -1, 0, 1, 2)).strip()[:200]
                snip = txt.strip()[:120]
                if ph in cands:
                    cands[ph]["occurrences"] += 1
                    if snip not in cands[ph]["contexts"] and len(cands[ph]["contexts"]) < 5:
                        cands[ph]["contexts"].append(snip)
                    if near:
                        cands[ph]["near_known"] = True
                else:
                    scope, cat = classify(ph, ctx)
                    cands[ph] = {
                        "word": ph, "occurrences": 1, "contexts": [snip],
                        "suggested_scope": scope, "suggested_category": cat,
                        "near_known": near, "first_line": no, "status": "pending_review",
                    }

    found = sorted(cands.values(), key=lambda c: (-c["occurrences"], c["first_line"]))

    # 增量合并到 per-project 候选文件（含原文，留在 workspace，不进仓库）
    lines_path = Path(args.lines_file)
    out = (Path(args.out) if args.out
           else lines_path.with_name(lines_path.stem.replace(".lines", "") + ".candidates.json"))
    existing = {}
    if out.exists():
        try:
            for c in json.load(open(out, encoding="utf-8")).get("candidates", []):
                existing[c["word"]] = c
        except Exception:
            pass
    added = 0
    for c in found:
        if c["word"] in existing:
            existing[c["word"]]["occurrences"] = existing[c["word"]].get("occurrences", 0) + c["occurrences"]
        else:
            existing[c["word"]] = c
            added += 1
    json.dump({"candidates": list(existing.values())}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("OK 候选词：本次发现 %d 个，新增 %d，累计 %d" % (len(found), added, len(existing)))
    print("out=%s" % out)
    print("--- 本次发现（前 15，按出现次数）---")
    for c in found[:15]:
        flag = "★邻近判决词" if c.get("near_known") else ""
        print("  [%dx] %s (scope=%s cat=%s) %s | %s"
              % (c["occurrences"], c["word"], "/".join(c["suggested_scope"]),
                 c["suggested_category"], flag, c["contexts"][0][:36]))


if __name__ == "__main__":
    main()
