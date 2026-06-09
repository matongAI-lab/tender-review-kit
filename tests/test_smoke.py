#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_smoke.py — 回归基准(合成样本招标文件)

用一份**纯虚构的合成招标 docx**(tests/fixtures/sample_tender.docx)做回归测试。
改判词库 / 改程序后,跑这个保证关键指标不退化。

不依赖任何真实标书。Fixture 由 generate_fixture.py 生成,内容完全公开可控。

直接 `python tests/test_smoke.py` 跑,无 pytest 依赖。
"""
import sys
import json
import subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KIT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_tender.docx"
WS = KIT / "workspace"
STEM = "sample"

# 合成样本基准(由 generate_fixture.py 构造的内容决定)
BASELINE = {
    "lines_min": 40,                # 取数行数(实际 55,容差 15)
    "primary_total_min": 12,        # 一级判决词命中(长词优先去噪后实际 12)
    "primary_bid_phase_min": 9,     # bid_phase 命中(长词优先去噪后实际 9)
    "customization_min": 6,         # 关系门槛(实际 9)
    "certifications_min": 5,        # 证明文件要求(实际 8)
    "emphasis_min": 10,             # ▲ 命中(实际 13)
    "detected_marks": ["▲"],         # 应识别的强调符号
}


def red(s): return "\033[31m" + s + "\033[0m"
def green(s): return "\033[32m" + s + "\033[0m"


def assert_ge(name, actual, expected, errors):
    if actual >= expected:
        print(green("✓"), name, "=", actual, "≥", expected)
    else:
        errors.append("%s: 实际 %s < 基准 %s" % (name, actual, expected))
        print(red("✗"), name, "=", actual, "< 基准", expected)


def run(cmd, errors):
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        errors.append("子命令失败: " + " ".join(cmd))
        print(red("✗ 子命令失败:"), " ".join(cmd))
        if r.stderr:
            print(r.stderr.strip()[:300])
        return False
    return True


def main():
    errors = []

    if not FIXTURE.exists():
        print(red("✗ fixture 不存在: " + str(FIXTURE)))
        print("  请先跑: python tests/generate_fixture.py")
        sys.exit(1)

    # 跑取数 + 撒网(每次跑测试都重新生成,验证全链路)
    WS.mkdir(parents=True, exist_ok=True)
    if not run([str(KIT / "scripts" / "extract_text.py"), str(FIXTURE),
                "--outdir", str(WS), "--name", STEM], errors):
        sys.exit(1)
    lines_file = WS / (STEM + ".lines.txt")
    hits_file = WS / (STEM + ".hits.json")
    # 显式指定开源词库,避免本地词库 local_keywords.json 影响测试可重复性
    open_kw = KIT / "data" / "keywords.json"
    if not run([str(KIT / "scripts" / "scan_keywords.py"), str(lines_file),
                "--keywords", str(open_kw)], errors):
        sys.exit(1)

    # 1. 取数基线
    with open(lines_file, encoding="utf-8") as f:
        n_lines = sum(1 for _ in f)
    assert_ge("取数行数", n_lines, BASELINE["lines_min"], errors)

    # 2. 撒网基线
    h = json.load(open(hits_file, encoding="utf-8"))
    s = h["summary"]
    assert_ge("一级判决词", s["primary"], BASELINE["primary_total_min"], errors)
    assert_ge("bid_phase 命中", s["primary_by_scope"].get("bid_phase", 0),
              BASELINE["primary_bid_phase_min"], errors)
    assert_ge("关系门槛", s["customization"], BASELINE["customization_min"], errors)
    assert_ge("证明文件要求", s["certifications"], BASELINE["certifications_min"], errors)
    assert_ge("▲ 命中", s["emphasis_marks"], BASELINE["emphasis_min"], errors)

    # 3. ▲ 符号识别
    detected = set(h["detected_emphasis_marks"])
    expected = set(BASELINE["detected_marks"])
    missing = expected - detected
    if not missing:
        print(green("✓"), "强调符号识别:", sorted(detected))
    else:
        errors.append("强调符号识别缺失: %s (实际识别 %s)" % (sorted(missing), sorted(detected)))
        print(red("✗"), "强调符号识别缺失:", sorted(missing))

    print()
    if errors:
        print(red("✗ 回归失败 %d 项:" % len(errors)))
        for e in errors:
            print("  ", e)
        sys.exit(1)
    print(green("✓ 合成样本基准全部通过"))


if __name__ == "__main__":
    main()
