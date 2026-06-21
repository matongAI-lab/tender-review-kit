#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_pipeline.py — 一键串联程序步骤，让 AI agent 只需专注判断

两个阶段：
  prep   — 取数 + 撒网 + 补词（全自动，几秒跑完）
  verify — 护栏检查 + 出 Excel（agent 写完工作区 md 后跑）

用法：
  python run_pipeline.py prep   <招标文件.docx/.pdf> [--outdir workspace]
  python run_pipeline.py verify <工作区.md> [--out 输出.xlsx]

示例（用自带测试样本跑通全流程）：
  python run_pipeline.py prep   tests/fixtures/sample_tender.docx
  python run_pipeline.py verify workspace/sample_tender.工作区.md
"""
import sys
import subprocess
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPTS = Path(__file__).resolve().parent / "scripts"


def run(cmd, label):
    print("\n" + "=" * 60)
    print("▶ %s" % label)
    print("  %s" % " ".join(str(c) for c in cmd))
    print("-" * 60)
    r = subprocess.run([sys.executable] + [str(c) for c in cmd])
    if r.returncode != 0:
        print("✗ %s 失败 (exit %d)" % (label, r.returncode))
        return False
    return True


def prep(tender_file, outdir):
    tender = Path(tender_file)
    if not tender.exists():
        print("✗ 文件不存在: %s" % tender)
        sys.exit(1)

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = tender.stem

    ok = run([SCRIPTS / "extract_text.py", str(tender), "--outdir", str(outdir)],
             "Step 0 · 取数：%s → 带行号文本" % tender.name)
    if not ok:
        sys.exit(1)

    lines_file = outdir / (stem + ".lines.txt")
    if not lines_file.exists():
        print("✗ 取数后未找到 %s" % lines_file)
        sys.exit(1)

    ok = run([SCRIPTS / "scan_keywords.py", str(lines_file)],
             "Step 3a · 撒网：扫判决词 → hits.json")
    if not ok:
        sys.exit(1)

    hits_file = outdir / (stem + ".hits.json")

    hits_arg = ["--hits", str(hits_file)] if hits_file.exists() else []
    run([SCRIPTS / "scan_candidates.py", str(lines_file)] + hits_arg,
        "Step 3b · 补词：扫候选新词 → candidates.json")

    print("\n" + "=" * 60)
    print("✓ prep 完成！产出文件在 %s/" % outdir)
    print()
    print("接下来：")
    print("  1. 把下面这段话发给你的 AI agent：")
    print()
    print('  ─── 复制开始 ───')
    print('  请按 SKILL.md 的步骤 1-2-4-5 审核这份招标文件。')
    print('  - 带行号文本：%s' % lines_file)
    if hits_file.exists():
        print('  - 撒网命中：%s' % hits_file)
    print('  - 参考文档在 references/ 目录')
    print('  - 输出写到：%s' % (outdir / (stem + ".工作区.md")))
    print('  ─── 复制结束 ───')
    print()
    print("  2. agent 写完工作区 md 后，跑：")
    print("     python run_pipeline.py verify %s" % (outdir / (stem + ".工作区.md")))


def verify(worklist_file, out_xlsx):
    worklist = Path(worklist_file)
    if not worklist.exists():
        print("✗ 工作区文件不存在: %s" % worklist)
        print("  请先让 AI agent 按 SKILL.md 步骤 1-2-4-5 写完工作区 md")
        sys.exit(1)

    ws_dir = worklist.parent
    stem = worklist.stem.replace(".工作区", "")
    hits_file = ws_dir / (stem + ".hits.json")

    lines_file = ws_dir / (stem + ".lines.txt")
    harvest_args = [SCRIPTS / "harvest_ai_words.py", str(worklist)]
    if lines_file.exists():
        harvest_args += ["--lines", str(lines_file)]
    ok = run(harvest_args,
             "Step 5+ · 收割 + 补扫：AI 发现的疑似判词 → 候选库 + 回扫当前标书")
    if not ok:
        print("✗ verify 中止：新词收割/补扫失败，未生成 Excel。")
        sys.exit(1)

    if hits_file.exists():
        ok = run([SCRIPTS / "check_coverage.py", str(hits_file), str(worklist)],
                 "Step 6a · 查漏：撒网命中 vs 废标清单覆盖反查")
        if not ok:
            print("✗ verify 中止：查漏护栏失败，未生成 Excel。")
            sys.exit(1)

        ok = run([SCRIPTS / "check_completeness.py", str(worklist), "--hits", str(hits_file)],
                 "Step 6b · 完整性：条数 / 梯度 / ▲ 覆盖校验")
        if not ok:
            print("✗ verify 中止：完整性护栏失败，未生成 Excel。")
            sys.exit(1)
    else:
        print("⚠ 未找到 %s，跳过护栏检查" % hits_file)

    if not out_xlsx:
        out_xlsx = str(ws_dir / (stem + ".xlsx"))

    ok = run([SCRIPTS / "build_excel.py", out_xlsx, str(worklist)],
             "Step 7 · 出 Excel")
    if not ok:
        print("✗ verify 中止：Excel 生成失败。")
        sys.exit(1)

    pending_file = ws_dir / (stem + ".pending_words.json")
    local_kw_file = SCRIPTS.parent / "data" / "local_keywords.json"
    print("\n" + "=" * 60)
    print("✓ verify 完成！")
    print("  Excel: %s" % out_xlsx)
    print("  如有护栏 warning，回去让 agent 补漏后重跑 verify。")

    if pending_file.exists():
        print()
        print("⚠  AI 发现了一些新判词，已生成待审清单【尚未入库】：")
        print("    %s" % pending_file)
        print()
        print("  注意:入库只影响以后标书;当前标书补漏已经在 Step 5+ 用临时词库回扫过。")
        print("  请先让用户审批，再按选择入库:")
        print("    python scripts/harvest_ai_words.py %s --accept \"词A,词B\"" % worklist)
        print("    （用户明确全部接受才用 --accept-all；全部拒绝用 --reject-all）")

    print()
    print("  词库互惠机制:")
    print("    - AI/程序发现的新判词,用户接受后会进 data/local_keywords.json,只存在本机。")
    print("    - 贡献完全自愿;不给也能正常使用。")
    print("    - 我们不拿标书、Excel、工作区、原文片段、项目名称或行号上下文。")
    print("    - 如果其中有普遍适用、无项目隐私的词,可只贡献判词短语 + 分类/scope。")
    print("    - --github 默认创建 Issue 给维护者审核,不会自动直写开源总词库。")
    print("    - 你定期 git pull,也能拿到别人贡献的新词。")
    if local_kw_file.exists():
        print()
        print("  你接受入库的判词已留在本地,下次扫别的标书会自动用上。")
        print("  把本地词库里适合公开共享的词贡献给开源 keywords.json:")
        print("    python scripts/export_contribution.py --github  # 一键提 Issue")
        print("    python scripts/export_contribution.py           # 先导出预览(脱敏,不含原文)")
    else:
        print("  当前还没有本地词库;以后接受新词后,可用:")
        print("    python scripts/export_contribution.py           # 导出预览(脱敏,不含原文)")


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("prep", "verify"):
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "prep":
        outdir = "workspace"
        rest = sys.argv[2:]
        for i, a in enumerate(rest):
            if a == "--outdir" and i + 1 < len(rest):
                outdir = rest[i + 1]
                rest = rest[:i] + rest[i + 2:]
                break
        if not rest:
            print("用法: python run_pipeline.py prep <招标文件> [--outdir workspace]")
            sys.exit(1)
        prep(rest[0], outdir)

    elif cmd == "verify":
        out = None
        rest = sys.argv[2:]
        for i, a in enumerate(rest):
            if a == "--out" and i + 1 < len(rest):
                out = rest[i + 1]
                rest = rest[:i] + rest[i + 2:]
                break
        if not rest:
            print("用法: python run_pipeline.py verify <工作区.md> [--out 输出.xlsx]")
            sys.exit(1)
        verify(rest[0], out)


if __name__ == "__main__":
    main()
