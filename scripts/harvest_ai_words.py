#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harvest_ai_words.py — AI 发现的新判词:待审 → 用户拍板 → 入本地库 + 回扫

AI 在 Step 5 读条款时可能发现 keywords.json 没覆盖的判决性语言。
按 SKILL.md 约定,AI 把这些词写进工作区 md 的 `## AI发现疑似判词` 表格。

**两步走** (v0.1.3 设计:不再"自动入库",用户必须拍板):

Step 1. 列出待审 (默认行为,不写本地库):
    python harvest_ai_words.py <工作区.md>
    → 解析表格 → 写 workspace/<项目>.pending_words.json → 打印每个词

Step 2. 用户/AI 拍板后,入本地库 + 回扫:
    python harvest_ai_words.py <工作区.md> --accept-all          # 全接受
    python harvest_ai_words.py <工作区.md> --accept "词A,词B"     # 部分接受
    python harvest_ai_words.py <工作区.md> --reject-all          # 全拒绝(清空 pending)

接受的词写入 data/local_keywords.json(用户本地积累,gitignored),
然后用合并后的词库重扫 lines.txt → diff 新旧 hits → 报新增命中行。
"""
import sys
import re
import json
import subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
SCAN_KW = BASE / "scripts" / "scan_keywords.py"
LOCAL_KW_PATH = BASE / "data" / "local_keywords.json"

_VALID_CATEGORIES = {"primary", "secondary", "customization", "certifications"}
_VALID_SCOPES = {"bid_phase", "evaluation_phase", "contract_phase"}


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
            if len(parts) >= 2:
                category = parts[0] if parts[0] in _VALID_CATEGORIES else "primary"
                scope = [p for p in parts[1:] if p in _VALID_SCOPES] or ["bid_phase"]
        elif category_hint in _VALID_SCOPES:
            scope = [category_hint]
        elif category_hint in _VALID_CATEGORIES:
            category = category_hint

        line_no = None
        m = re.search(r"行(\d+)", source_line)
        if m:
            line_no = int(m.group(1))

        results.append({
            "word": word,
            "scope": scope,
            "category": category,
            "context_snippet": context[:120],
            "source_line": line_no,
        })

    return results


def write_pending(found, pending_path):
    """写待审清单文件"""
    Path(pending_path).parent.mkdir(parents=True, exist_ok=True)
    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump({"pending": found}, f, ensure_ascii=False, indent=2)


def load_pending(pending_path):
    if not Path(pending_path).exists():
        return []
    try:
        data = json.loads(Path(pending_path).read_text(encoding="utf-8"))
        return data.get("pending", [])
    except (json.JSONDecodeError, OSError):
        return []


def merge_into_local(accepted):
    """把用户接受的词合并进 data/local_keywords.json"""
    if LOCAL_KW_PATH.exists():
        local = json.loads(LOCAL_KW_PATH.read_text(encoding="utf-8"))
    else:
        local = {
            "version": "2.0",
            "_edition": "Local · 用户本地积累(gitignored)",
            "_about": "由 harvest_ai_words.py 在用户审批后追加 AI 发现的新词。scan_keywords 会自动合并加载。",
            "categories": [
                {"id": "primary", "name": "一级判决词", "level": 1, "match_type": "literal",
                 "scope_required": True, "words": []},
                {"id": "secondary", "name": "二级判决词", "level": 2, "match_type": "literal", "words": []},
                {"id": "customization", "name": "关系门槛", "match_type": "literal", "words": []},
                {"id": "certifications", "name": "证明文件", "match_type": "regex", "words": []},
            ],
        }

    cat_by_id = {c["id"]: c for c in local.get("categories", [])}
    added_words = []

    for f in accepted:
        cid = f["category"]
        if cid not in cat_by_id:
            cat_by_id[cid] = {"id": cid, "words": []}
            local["categories"].append(cat_by_id[cid])

        existing = set()
        for w in cat_by_id[cid].get("words", []):
            existing.add(w["word"] if isinstance(w, dict) else w)

        if f["word"] in existing:
            continue

        if cid == "primary":
            cat_by_id[cid].setdefault("words", []).append({"word": f["word"], "scope": f["scope"]})
        else:
            cat_by_id[cid].setdefault("words", []).append(f["word"])
        added_words.append(f["word"])

    LOCAL_KW_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_KW_PATH.write_text(
        json.dumps(local, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return added_words


def rescan_and_diff(lines_path, old_hits_path):
    new_hits_path = Path(lines_path).with_name(
        Path(lines_path).stem.replace(".lines", "") + ".hits.v2.json"
    )

    r = subprocess.run(
        [sys.executable, str(SCAN_KW), str(lines_path), "--out", str(new_hits_path)],
        capture_output=True, text=True, encoding="utf-8"
    )
    if r.returncode != 0:
        print("✗ 重扫失败: %s" % r.stderr)
        return None, []

    new_hits = json.loads(new_hits_path.read_text(encoding="utf-8"))

    old_set = set()
    if old_hits_path and Path(old_hits_path).exists():
        old_hits = json.loads(Path(old_hits_path).read_text(encoding="utf-8"))
        for cat, hits in old_hits.get("hits", {}).items():
            for h in hits:
                key = (h.get("line"), h.get("word", h.get("pattern", h.get("mark", ""))))
                old_set.add(key)

    new_in_new = []
    for cat, hits in new_hits.get("hits", {}).items():
        for h in hits:
            key = (h.get("line"), h.get("word", h.get("pattern", h.get("mark", ""))))
            if key not in old_set:
                new_in_new.append({**h, "_category": cat})

    return new_hits_path, new_in_new


def _already_in_local(word):
    """检查词是否已在本地词库中"""
    if not LOCAL_KW_PATH.exists():
        return False
    try:
        local = json.loads(LOCAL_KW_PATH.read_text(encoding="utf-8"))
        for cat in local.get("categories", []):
            for w in cat.get("words", []):
                key = w["word"] if isinstance(w, dict) else w
                if key == word:
                    return True
    except (json.JSONDecodeError, OSError):
        pass
    return False


def print_pending(pending):
    """打印待审清单"""
    print()
    print("=" * 60)
    print("AI 在本次审标中发现了 %d 个疑似新判词,需要你审批" % len(pending))
    print("=" * 60)
    print()
    for i, f in enumerate(pending, 1):
        line_str = "行%d" % f["source_line"] if f.get("source_line") else "?"
        already = _already_in_local(f["word"])
        tag = " [已在本地库,无需重复接受]" if already else ""
        print("  %d. **%s**%s" % (i, f["word"], tag))
        print("     建议: %s / %s" % (f["category"], "/".join(f["scope"])))
        print("     原文 (%s): %s" % (line_str, f["context_snippet"]))
        print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    md_path = sys.argv[1]
    if not Path(md_path).exists():
        print("✗ 文件不存在: %s" % md_path)
        sys.exit(1)

    accept_all = False
    reject_all = False
    accept_specific = []
    lines_path = None
    hits_path = None

    i = 2
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--accept-all":
            accept_all = True
            i += 1
        elif a == "--reject-all":
            reject_all = True
            i += 1
        elif a == "--accept" and i + 1 < len(sys.argv):
            accept_specific.extend([w.strip() for w in sys.argv[i + 1].split(",") if w.strip()])
            i += 2
        elif a == "--lines" and i + 1 < len(sys.argv):
            lines_path = sys.argv[i + 1]
            i += 2
        elif a == "--hits" and i + 1 < len(sys.argv):
            hits_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    stem = Path(md_path).stem.replace(".工作区", "")
    ws_dir = Path(md_path).parent
    pending_path = ws_dir / (stem + ".pending_words.json")

    if not lines_path:
        auto = ws_dir / (stem + ".lines.txt")
        if auto.exists():
            lines_path = str(auto)
    if not hits_path:
        auto = ws_dir / (stem + ".hits.json")
        if auto.exists():
            hits_path = str(auto)

    # === 模式 1: 默认 — 解析 + 生成待审清单 ===
    if not accept_all and not reject_all and not accept_specific:
        found = parse_ai_section(md_path)

        if not found:
            print("OK AI发现疑似判词: 0 条（工作区中无该 section 或表格为空）")
            return

        write_pending(found, pending_path)
        print_pending(found)

        print("─" * 60)
        print("⚠  这些词【尚未入库】。请审批:")
        print()
        print("  全部接受  →  python scripts/harvest_ai_words.py %s --accept-all" % md_path)
        print("  部分接受  →  python scripts/harvest_ai_words.py %s --accept \"词A,词B\"" % md_path)
        print("  全部拒绝  →  python scripts/harvest_ai_words.py %s --reject-all" % md_path)
        print()
        print("  待审清单已保存: %s" % pending_path)
        return

    # === 模式 2: --reject-all ===
    if reject_all:
        if pending_path.exists():
            pending_path.unlink()
        print("✓ 已拒绝所有待审词,清单文件已删除。本地词库不变。")
        return

    # === 模式 3: --accept-all 或 --accept ===
    pending = load_pending(pending_path)
    if not pending:
        # 待审清单不存在:可能是首次直接 --accept-all,重新解析
        pending = parse_ai_section(md_path)
        if not pending:
            print("OK 工作区中无待审词,本地词库不变。")
            return

    if accept_all:
        accepted = pending
        rejected = []
    else:
        accepted = [p for p in pending if p["word"] in accept_specific]
        rejected = [p for p in pending if p["word"] not in accept_specific]
        unknown = [w for w in accept_specific if not any(p["word"] == w for p in pending)]
        if unknown:
            print("⚠  以下词不在待审清单中,已忽略: %s" % ", ".join(unknown))

    if not accepted:
        print("✗ 没有接受任何词,本地词库不变。")
        return

    added = merge_into_local(accepted)

    print("✓ 已接受 %d 词进本地词库(其中 %d 是新增,其余已存在):" % (len(accepted), len(added)))
    for w in added:
        print("  + %s" % w)
    if rejected:
        print()
        print("  以下词被跳过(未入库):")
        for r in rejected:
            print("  - %s" % r["word"])

    # 清理 pending（已处理）
    if pending_path.exists():
        pending_path.unlink()

    # === 触发回扫 ===
    if lines_path and Path(lines_path).exists():
        print()
        print("▶ 用合并后的词库重扫 lines.txt,对照旧 hits 找新增命中…")
        new_hits_path, new_hits = rescan_and_diff(lines_path, hits_path)

        if new_hits_path:
            print()
            if new_hits:
                print("⚠  新词在当前标书共找到 %d 条**新增命中**:" % len(new_hits))
                for h in new_hits[:30]:
                    line = h.get("line", "?")
                    key = h.get("word", h.get("pattern", h.get("mark", "?")))
                    text = h.get("text", "")
                    print("  行%-5s [%s] %s" % (line, key, text[:60]))
                if len(new_hits) > 30:
                    print("  ... 还有 %d 条" % (len(new_hits) - 30))
                print()
                print("→ AI/用户:逐条检查这些新增命中,判断是否需要补到工作区清单。")
                print("→ 重扫产物: %s" % new_hits_path)
            else:
                print("✓ 新词未在当前标书产生新增命中(工作区已记录了所有出现位置)。")
    else:
        print("⚠ 未找到 lines.txt,跳过回扫。")

    print()
    print("提示: 这些新词已在你的本地词库中(下次扫别的标书会自动用到)。")
    print("     最后 Step 8 会问你要不要把它们贡献给开源 keywords.json。")


if __name__ == "__main__":
    main()
