#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cross_doc.py — 跨文件矛盾检测（多文件招标包用）

招标包通常含多份文件(主招标 + 限价 + 技术规范 + 答疑等)。本程序对多份 lines.txt
做**确定性比对**,识别跨文件的"数字/日期不一致":
  - 关键金额(最高限价 / 投标保证金 / 履约保证金)
  - 关键时间(投标截止 / 开标 / 计划开工 / 计划竣工)
  - 子系统/工程范围数量

只列矛盾**事实**,不下哪个对的结论——让人核。

设计原则：scanner 只列要点,不下"是否会违反"结论 — 那是主对话的活。
来源:工程类标书实战教训 — "投标人须知列 10 个子系统 vs 技术规范书列 15 个"。
纯标准库(re),零依赖。

用法:
    python cross_doc.py <lines1.txt> <lines2.txt> [lines3.txt ...]
"""
import sys
import re
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 金额锚词
MONEY_ANCHORS = {
    "最高投标限价": ["最高投标限价", "投标限价", "招标控制价", "最高限价"],
    "投标保证金": ["投标保证金"],
    "履约保证金": ["履约保证金", "履约担保"],
}

# 日期锚词
DATE_ANCHORS = {
    "投标截止": ["投标截止", "递交投标文件截止时间", "开标时间"],
    "计划开工": ["计划开工", "开工日期", "开工时间"],
    "计划竣工": ["计划竣工", "竣工日期", "竣工时间"],
}

_MONEY_RE = re.compile(r"¥?\s*([\d,]+(?:\.\d+)?)\s*(万元|元)")
_DATE_RE = re.compile(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})\s*日?")


def load_text(path):
    text = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            text.append(raw.split("\t", 1)[1] if "\t" in raw else raw)
    return "\n".join(text)


def normalize_money(num_str, unit):
    n = float(num_str.replace(",", ""))
    return n * 10000 if unit == "万元" else n


def extract_money(text, anchors):
    """每个锚词取最常见的金额值"""
    counts = Counter()
    for a in anchors:
        for m in re.finditer(re.escape(a), text):
            window = text[m.end(): m.end() + 60]
            mm = _MONEY_RE.search(window)
            if mm:
                v = normalize_money(mm.group(1), mm.group(2))
                counts[v] += 1
    return counts.most_common(1)[0][0] if counts else None


def extract_date(text, anchors):
    for a in anchors:
        for m in re.finditer(re.escape(a), text):
            window = text[m.end(): m.end() + 60]
            mm = _DATE_RE.search(window)
            if mm:
                return "%s-%02d-%02d" % (mm.group(1), int(mm.group(2)), int(mm.group(3)))
    return None


def extract_subsystem_count(text):
    """识别"X系统、Y系统、Z系统"枚举,取最长一段的子系统数。"""
    pat = re.compile(r"(?:[一-龥A-Za-z0-9]{2,12}系统[、,，]\s*){2,}[一-龥A-Za-z0-9]{2,12}系统")
    longest = None
    for m in pat.finditer(text):
        seg = m.group(0)
        if not longest or len(seg) > len(longest):
            longest = seg
    if not longest:
        return None
    return longest.count("系统")


def main():
    if len(sys.argv) < 3:
        print("用法: python cross_doc.py <lines1.txt> <lines2.txt> [lines3.txt ...]")
        sys.exit(1)
    paths = [Path(p) for p in sys.argv[1:]]
    docs = [(p.name, load_text(p)) for p in paths]

    conflicts = []

    # 金额
    for label, anchors in MONEY_ANCHORS.items():
        vals = [(name, extract_money(text, anchors)) for name, text in docs]
        nonnull = [(n, v) for n, v in vals if v is not None]
        if len(nonnull) >= 2 and len(set(v for _, v in nonnull)) > 1:
            conflicts.append({
                "type": "金额矛盾",
                "anchor": label,
                "severity": "high",
                "evidence": [{"file": n, "value": v} for n, v in vals],
            })

    # 日期
    for label, anchors in DATE_ANCHORS.items():
        vals = [(name, extract_date(text, anchors)) for name, text in docs]
        nonnull = [(n, v) for n, v in vals if v is not None]
        if len(nonnull) >= 2 and len(set(v for _, v in nonnull)) > 1:
            conflicts.append({
                "type": "日期矛盾",
                "anchor": label,
                "severity": "medium",
                "evidence": [{"file": n, "value": v} for n, v in vals],
            })

    # 子系统数量
    subs = [(name, extract_subsystem_count(text)) for name, text in docs]
    nonnull_subs = [(n, v) for n, v in subs if v is not None]
    if len(nonnull_subs) >= 2 and len(set(v for _, v in nonnull_subs)) > 1:
        conflicts.append({
            "type": "子系统数量矛盾",
            "anchor": "子系统枚举",
            "severity": "high",
            "evidence": [{"file": n, "count": v} for n, v in subs],
        })

    print("文件数：%d，矛盾数：%d" % (len(docs), len(conflicts)))
    for c in conflicts:
        print("\n[%s] %s （%s）" % (c["severity"], c["type"], c["anchor"]))
        for e in c["evidence"]:
            print("   %s: %s" % (e["file"], e.get("value", e.get("count"))))

    if not conflicts:
        print("\n✓ 各项金额/日期/子系统数量一致(或仅单文件涉及)，未发现确定性矛盾。")
    print("\n提示：本程序仅列事实，不下哪个对的结论——投标人需核实。")


if __name__ == "__main__":
    main()
