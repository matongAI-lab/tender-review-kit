#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_completeness.py — 完整性护栏（第二道墙）

清单产出后自动数一遍，防「少了内容」：
  - 废标条数 < 8 条 → 警告（任何招标文件几乎不可能少于这个数）
  - 评分条数 < 5 条 → 警告（通常有商务分若干 + 技术分若干）
  - 评分项每行含「分」字 → 防止只填大类摘要、漏逐档梯度
  - ▲/★ 清单条数 ≥ 撒网识别数 × 80% → 防止压缩标识项
  - 证明材料清册 < 5 条 → 警告（通常包含资质 + 业绩 + 检测 + 认证 + 软著等多类）

设计：脱钩 9 类分类——不再按 A/B/C/D 设死基线，改用通用"明显偏少"判定。
真正的"够不够"由 AI 的红蓝对抗 + 反向校验兜底。

纯标准库（json/re），零依赖。

用法:
    python check_completeness.py <工作区.md> [--hits <hits.json>]
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

# 通用「明显偏少」阈值（与具体类型无关）
MIN_DISQ = 8
MIN_SCORING = 5
MIN_CERT = 5
EMPHASIS_RATIO = 0.8  # ▲ 清单应 ≥ 撒网识别数 × 80%

_SEP = re.compile(r"^\|[\s\-:|]+\|?$")
_HEADER_WORDS = ["ID", "类别", "出处", "序号", "废标条款", "子项名称", "评分梯度", "评分项"]

# 子节(###)含这些关键词时跳过其内表格(说明性/台账/自检性子节,非主清单)
SKIP_SUBHEADER_KW = ["台账", "处置", "核验", "对照", "发现", "建议", "边界", "排除", "锚点"]


def count_section_rows(md, section_kw_any):
    """数 section 主表格数据行(排除表头/分隔行/说明性子节)。"""
    if isinstance(section_kw_any, str):
        section_kw_any = [section_kw_any]
    rows = []
    in_section, in_table = False, True
    for raw in md.splitlines():
        s = raw.strip()
        if s.startswith("## "):
            in_section = any(kw in s for kw in section_kw_any)
            in_table = True
            continue
        if s.startswith("# ") and not s.startswith("## "):
            in_section = False
            continue
        if s.startswith("### "):
            in_table = not any(kw in s for kw in SKIP_SUBHEADER_KW)
            continue
        if in_section and in_table and s.startswith("|"):
            if _SEP.match(s):
                continue
            if any(h in s for h in _HEADER_WORDS):
                continue
            rows.append(s)
    return rows


def main():
    ap = argparse.ArgumentParser(description="完整性护栏：清单条数/梯度/标识覆盖通用校验")
    ap.add_argument("worklist", help="工作区 md")
    ap.add_argument("--hits", default=None, help="hits.json（用于 ▲ 覆盖率校验）")
    ap.add_argument("--strict", action="store_true",
                    help="有 warning 时以非零码退出（供自动流程 gate）")
    args = ap.parse_args()

    md = open(args.worklist, encoding="utf-8").read()
    warnings = []

    disq = count_section_rows(md, ["废标"])
    scoring = count_section_rows(md, ["评分"])
    emph = count_section_rows(md, ["标识"])
    cert = count_section_rows(md, ["证明", "材料清册", "材料"])

    if len(disq) < MIN_DISQ:
        warnings.append("废标条数 %d < 通用基线 %d（明显偏少，可能漏识别或专项未跑）" % (len(disq), MIN_DISQ))
    if len(scoring) < MIN_SCORING:
        warnings.append("评分条数 %d < 通用基线 %d（明显偏少，评分细则可能未拆全）" % (len(scoring), MIN_SCORING))
    if len(cert) > 0 and len(cert) < MIN_CERT:
        warnings.append("证明材料 %d < 通用基线 %d（可能聚合不全，▲ 里的检测/认证要求都进了吗）" % (len(cert), MIN_CERT))

    no_fen = [r for r in scoring if "分" not in r]
    if no_fen:
        warnings.append("%d 条评分项不含「分」字（可能只填大类摘要，没展开逐档梯度）" % len(no_fen))

    if args.hits and Path(args.hits).exists():
        h = json.load(open(args.hits, encoding="utf-8"))
        net = h.get("summary", {}).get("emphasis_marks", 0)
        if net > 0 and len(emph) < net * EMPHASIS_RATIO:
            warnings.append("▲/★ 清单 %d 条 < 撒网 %d ×%d%%=%d（可能压缩了标识项）"
                            % (len(emph), net, int(EMPHASIS_RATIO * 100), int(net * EMPHASIS_RATIO)))

    print("废标=%d  评分=%d  标识=%d  证明=%d" % (len(disq), len(scoring), len(emph), len(cert)))
    if warnings:
        print("⚠️  %d 条 warning：" % len(warnings))
        for w in warnings:
            print("   -", w)
    else:
        print("✓ 完整性校验通过")
    print("\n提示：通用阈值只逮『明显偏少』；判断死角靠 A/B 红蓝对抗,漏抄靠 check_coverage 反向校验。")

    if args.strict and warnings:
        sys.exit(1)


if __name__ == "__main__":
    main()
