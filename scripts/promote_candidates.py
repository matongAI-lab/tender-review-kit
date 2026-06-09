#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""promote_candidates.py — 候选词审批入库(补词闭环最后一环)

读 workspace 候选文件里 pending_review 的候选词,逐条问你 y/n/s/q;
入库时**只把 词+scope 写进 keywords.json,绝不带原文片段**——data/ 不沾用户标书内容。
y → 加进 keywords.json 对应类别,候选状态改 promoted;
n → 拒绝,标 rejected,下次不再问;
s → 跳过,保持 pending_review,下次还问;
q → 退出。

退出时自动跑 tests/test_smoke.py,确保词库改动没把基准搞坏。

排序:★ 邻近已知判决词 → 出现次数高 → 先问(噪音低、价值高优先)。

默认读 workspace/ 下最新的 *.candidates.json;也可 --candidates 指定具体文件。

用法:
    python scripts/promote_candidates.py                    # 交互式(默认最新 workspace 候选)
    python scripts/promote_candidates.py --candidates workspace/<项目>.candidates.json
    python scripts/promote_candidates.py --list             # 只列,不审
    python scripts/promote_candidates.py --decisions FILE   # 批量(FILE 每行 "y 视为xxx")
    python scripts/promote_candidates.py --no-regression    # 改完不跑回归
"""
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def find_category(kw, cat_id):
    for c in kw["categories"]:
        if c.get("id") == cat_id:
            return c
    return None


def is_in_keywords(kw, word):
    for c in kw["categories"]:
        for w in c.get("words", []):
            if isinstance(w, dict):
                if w.get("word") == word:
                    return True
            elif w == word:
                return True
    return False


def add_to_keywords(kw, cand):
    cat_id = cand.get("suggested_category", "primary")
    cat = find_category(kw, cat_id)
    if not cat:
        return False, "类别 %s 不存在" % cat_id
    cat.setdefault("words", [])
    if cat_id == "primary":
        cat["words"].append({"word": cand["word"], "scope": cand.get("suggested_scope", [])})
    else:
        cat["words"].append(cand["word"])
    return True, cat_id


def display(c, idx, total):
    print()
    print("=" * 70)
    near = " ★邻近已知判决词" if c.get("near_known") else ""
    print("[%d/%d] %s  (%d次%s)" % (idx, total, c["word"], c.get("occurrences", 1), near))
    print("  类别建议: %s | scope: %s"
          % (c.get("suggested_category", "primary"),
             "/".join(c.get("suggested_scope", [])) or "—"))
    print("  原文上下文:")
    for ctx in c.get("contexts", [])[:3]:
        print("    ·", ctx)


def main():
    base = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="候选词审批入库")
    ap.add_argument("--candidates", default=None,
                    help="候选文件;默认取 workspace/ 下最新的 *.candidates.json")
    ap.add_argument("--keywords", default=str(base / "data" / "keywords.json"))
    ap.add_argument("--list", action="store_true", help="只列待审候选,不交互")
    ap.add_argument("--decisions", default=None, help="批量决定文件(每行: y/n/s <词>)")
    ap.add_argument("--no-regression", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="--list 默认隐藏纯 contract_phase 候选(合同期 noise);加 --all 显示全部")
    args = ap.parse_args()

    if args.candidates:
        cand_path = Path(args.candidates)
    else:
        ws = base / "workspace"
        found_files = sorted(ws.glob("*.candidates.json"),
                             key=lambda p: p.stat().st_mtime, reverse=True)
        if not found_files:
            print("没有找到候选文件。先跑 scan_candidates.py 生成 workspace/<项目>.candidates.json")
            return
        cand_path = found_files[0]
        print("使用最新候选文件:", cand_path.name)

    cand_data = json.load(open(cand_path, encoding="utf-8"))
    kw_data = json.load(open(args.keywords, encoding="utf-8"))
    cands = cand_data.get("candidates", [])
    pending = [c for c in cands if c.get("status", "pending_review") == "pending_review"]
    pending.sort(key=lambda c: (not c.get("near_known", False), -c.get("occurrences", 1)))

    if not pending:
        print("✓ 没有待审候选词。candidates 总数:", len(cands))
        return

    if args.list:
        # 默认隐藏纯合同期候选(scope 只含 contract_phase)— 这些是合同噪音,不是投标废标
        if args.all:
            shown = pending
            hidden_note = ""
        else:
            shown = [c for c in pending if set(c.get("suggested_scope", [])) != {"contract_phase"}]
            hidden = len(pending) - len(shown)
            hidden_note = f"(已隐藏 {hidden} 条纯合同期 noise,加 --all 显示)" if hidden else ""
        print(f"待审候选 {len(shown)} 条 {hidden_note}(按 ★+次数 排序,前 30):")
        for i, c in enumerate(shown[:30], 1):
            near = "★" if c.get("near_known") else " "
            print("  %s[%2d] %dx %-22s %s | scope=%s | %s"
                  % (near, i, c.get("occurrences", 1), c["word"],
                     c.get("suggested_category", "primary"),
                     "/".join(c.get("suggested_scope", [])) or "—",
                     (c.get("contexts", [""])[0])[:40]))
        return

    decisions_map = {}
    if args.decisions:
        for line in open(args.decisions, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0] in ("y", "n", "s"):
                decisions_map[parts[1]] = parts[0]
        print("批量决定模式: %d 条决定" % len(decisions_map))

    print("待审 %d 条。命令: y=入库 n=拒绝 s=跳过 q=退出" % len(pending))
    today = date.today().isoformat()
    tag = "promoted_" + today
    promoted, rejected, skipped, changed = 0, 0, 0, False

    try:
        for i, c in enumerate(pending, 1):
            if is_in_keywords(kw_data, c["word"]):
                c["status"] = "auto_skip_duplicate_" + today
                changed = True
                continue

            if decisions_map:
                ans = decisions_map.get(c["word"])
                if not ans:
                    continue  # 决定文件没列就跳过
                display(c, i, len(pending))
                print("  > 批量决定: %s" % ans)
            else:
                display(c, i, len(pending))
                while True:
                    try:
                        ans = input("  > [y/n/s/q]: ").strip().lower()
                    except EOFError:
                        ans = "q"
                        break
                    if ans in ("y", "n", "s", "q"):
                        break
                    print("  ?? 请回 y/n/s/q")

            if ans == "q":
                print("  → 退出")
                break
            if ans == "y":
                ok, info = add_to_keywords(kw_data, c)
                if ok:
                    c["status"] = tag
                    promoted += 1
                    changed = True
                    print("  ✓ 入 keywords.json [%s] 类" % info)
                else:
                    print("  ✗", info)
            elif ans == "n":
                c["status"] = "rejected_" + today
                rejected += 1
                changed = True
                print("  → 拒绝")
            else:
                skipped += 1
                print("  → 跳过")
    except KeyboardInterrupt:
        print("\n中断")

    if changed:
        cand_data["candidates"] = cands
        json.dump(cand_data, open(cand_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        json.dump(kw_data, open(args.keywords, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("\n本次:入库 %d / 拒绝 %d / 跳过 %d" % (promoted, rejected, skipped))

        if not args.no_regression and promoted > 0:
            print("\n== 自动跑回归基准 ==")
            r = subprocess.run([sys.executable, str(base / "tests" / "test_smoke.py")])
            if r.returncode != 0:
                print("\n⚠️  回归失败! 词库变化可能影响基准,请人工核对。")
                sys.exit(1)
            print("✓ 回归通过 — 入库未引起基准退化")
    else:
        print("无变更")


if __name__ == "__main__":
    main()
