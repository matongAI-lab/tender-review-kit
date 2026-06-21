#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_keywords.py — 判决词撒网：在「带行号文本」上扫 6 类信号

读取 extract_text.py 产出的 *.lines.txt + data/keywords.json，逐行扫描：
  - primary       一级判决词（带 scope：bid_phase/evaluation_phase/contract_phase）
  - contract      合同条款·要点（中标后约束，不计入废标）
  - secondary     二级判决词
  - customization  商务定制门槛（关系门槛：厂商授权/必须接入…）
  - certifications 证明文件要求（正则，含 exclude 排除质保维保类误命中）
  - emphasis_marks 强调标识（▲/★/◆…按出现频次自适应识别本文档实际用的；同一长表格行内多项逐条拆分）

输出命中清单（行号 + 词 + 类别 + scope）→ *.hits.json。
这是「全文撒网」，后续 check_coverage.py 据此反查废标项是否覆盖。

纯标准库（json/re），零额外依赖。

用法:
    python scan_keywords.py <file.lines.txt> [--keywords data/keywords.json] [--out hits.json]
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


def load_lines(path):
    """读 *.lines.txt → [(line_no, text)]"""
    rows = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if "\t" in raw:
                no, text = raw.split("\t", 1)
                try:
                    rows.append((int(no), text))
                    continue
                except ValueError:
                    pass
            if raw:
                rows.append((len(rows) + 1, raw))
    return rows


def get_category(cats, cid):
    for c in cats:
        if c.get("id") == cid:
            return c
    return {}


_STAR_EMPH = re.compile(r'(?:^|\|\s*|\[T\d+\]\s*)\*\s*[一-鿿]')


def _emph_count(mark, text):
    if mark == "*":
        return len(_STAR_EMPH.findall(text))
    return text.count(mark)


def _emph_hit(mark, text):
    if mark == "*":
        return bool(_STAR_EMPH.search(text))
    return mark in text


def _emph_positions(mark, text):
    """Return valid emphasis mark start positions in text."""
    if mark == "*":
        for m in _STAR_EMPH.finditer(text):
            pos = text.find("*", m.start(), m.end())
            if pos != -1:
                yield pos
        return
    start = text.find(mark)
    while start != -1:
        yield start
        start = text.find(mark, start + len(mark))


def _emph_segments(detected, text, max_chars=240):
    """Split one extracted line into per-mark emphasis snippets.

    extract_text.py flattens each table row into one long line. A single line can
    therefore contain many ▲/★ parameters; recording only one hit per line loses
    clauses. This returns one snippet per mark occurrence, ending at the next
    detected mark where possible.
    """
    starts = []
    seen = set()
    for mark in detected:
        for pos in _emph_positions(mark, text):
            if pos in seen:
                continue
            seen.add(pos)
            starts.append((pos, mark))
    starts.sort()

    for idx, (pos, mark) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(text)
        snippet = text[pos:end].strip()
        snippet = snippet.strip("|").strip()
        if len(snippet) > max_chars:
            snippet = snippet[:max_chars].rstrip() + "..."
        yield mark, snippet


def _literal_spans(word, text):
    """Return all literal match spans for word in text."""
    start = text.find(word)
    while start != -1:
        end = start + len(word)
        yield start, end
        start = text.find(word, start + 1)


def _primary_hits_for_line(prim_words, text):
    """Prefer longer primary phrases when matches overlap on the same line."""
    matches = []
    for w in prim_words:
        word = w.get("word", "")
        if not word:
            continue
        for start, end in _literal_spans(word, text):
            matches.append({"entry": w, "word": word, "start": start, "end": end})

    kept = []
    seen_words = set()
    for i, m in enumerate(matches):
        nested_in_longer = any(
            i != j
            and len(other["word"]) > len(m["word"])
            and m["start"] >= other["start"]
            and m["end"] <= other["end"]
            for j, other in enumerate(matches)
        )
        if nested_in_longer or m["word"] in seen_words:
            continue
        kept.append(m["entry"])
        seen_words.add(m["word"])
    return kept


def scan(lines, kw):
    cats = kw["categories"]
    global_excl = [re.compile(p) for p in kw.get("exclude_patterns_global", [])]

    def excluded(text):
        return any(p.search(text) for p in global_excl)

    hits = {"primary": [], "contract": [], "secondary": [], "customization": [],
            "certifications": [], "emphasis_marks": []}

    # 强调标识自适应：先统计候选符号频次，达阈值的才认定为本文档强调标识
    em = get_category(cats, "emphasis_marks")
    candidates = em.get("candidates", [])
    min_occ = em.get("min_occurrences", 10)
    occ_overrides = em.get("min_occurrences_overrides", {})  # 明确强调符(▲★)阈值更低,少量也不丢
    counts = {m: 0 for m in candidates}
    for _, text in lines:
        for m in candidates:
            c = _emph_count(m, text)
            if c:
                counts[m] += c
    detected = [m for m in candidates if counts[m] >= occ_overrides.get(m, min_occ)]

    prim_words = get_category(cats, "primary").get("words", [])
    contract_words = get_category(cats, "contract").get("words", [])
    sec_words = get_category(cats, "secondary").get("words", [])
    cust_words = get_category(cats, "customization").get("words", [])
    cert = get_category(cats, "certifications")
    cert_pats = [re.compile(p) for p in cert.get("words", [])]
    cert_excl = [re.compile(p) for p in cert.get("exclude_patterns", [])]

    for no, text in lines:
        if not text.strip() or excluded(text):
            continue
        for w in _primary_hits_for_line(prim_words, text):
            hits["primary"].append({"line": no, "word": w["word"],
                                    "scope": w.get("scope", []), "text": text[:160]})
        for w in contract_words:
            if w in text:
                hits["contract"].append({"line": no, "word": w, "text": text[:160]})
        for w in sec_words:
            if w in text:
                hits["secondary"].append({"line": no, "word": w, "text": text[:160]})
        for w in cust_words:
            if w in text:
                hits["customization"].append({"line": no, "word": w, "text": text[:160]})
        for p in cert_pats:
            if p.search(text):
                if any(e.search(text) for e in cert_excl):
                    continue
                hits["certifications"].append({"line": no, "pattern": p.pattern, "text": text[:160]})
                break
        for idx, (m, snippet) in enumerate(_emph_segments(detected, text), 1):
            hits["emphasis_marks"].append({
                "line": no,
                "mark": m,
                "item_index": idx,
                "text": snippet[:160],
            })

    return hits, detected, counts


def _merge_keywords(base_kw, local_kw):
    """把本地库 categories 的 words 合并进基础库（同 category id 去重合并）"""
    base_cats = {c["id"]: c for c in base_kw.get("categories", [])}
    for lc in local_kw.get("categories", []):
        cid = lc.get("id")
        if not cid:
            continue
        if cid in base_cats:
            existing_words = set()
            for w in base_cats[cid].get("words", []):
                existing_words.add(w["word"] if isinstance(w, dict) else w)
            for w in lc.get("words", []):
                wkey = w["word"] if isinstance(w, dict) else w
                if wkey not in existing_words:
                    base_cats[cid].setdefault("words", []).append(w)
                    existing_words.add(wkey)
        else:
            base_kw.setdefault("categories", []).append(lc)
    return base_kw


def main():
    ap = argparse.ArgumentParser(description="判决词撒网：带行号文本 → 命中清单")
    ap.add_argument("lines_file")
    ap.add_argument("--keywords", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    lines_path = Path(args.lines_file)
    if not lines_path.exists():
        print("ERROR file_not_found:", lines_path)
        sys.exit(1)

    base = Path(__file__).resolve().parent.parent
    kw_path = Path(args.keywords) if args.keywords else base / "data" / "keywords.json"
    kw = json.load(open(kw_path, encoding="utf-8"))

    # 合并本地词库（用户私有积累，gitignored）
    local_path = base / "data" / "local_keywords.json"
    if not args.keywords and local_path.exists():
        try:
            local = json.load(open(local_path, encoding="utf-8"))
            kw = _merge_keywords(kw, local)
            print("[已合并本地词库 %s]" % local_path.name)
        except (json.JSONDecodeError, KeyError) as e:
            print("⚠ 本地词库解析失败，跳过：%s" % e)

    lines = load_lines(lines_path)
    hits, detected, counts = scan(lines, kw)

    by_scope = {}
    for h in hits["primary"]:
        for s in h["scope"]:
            by_scope[s] = by_scope.get(s, 0) + 1

    result = {
        "source": str(lines_path),
        "total_lines": len(lines),
        "detected_emphasis_marks": detected,
        "emphasis_counts": {k: v for k, v in counts.items() if v > 0},
        "hits": hits,
        "summary": {
            "primary": len(hits["primary"]),
            "primary_by_scope": by_scope,
            "contract": len(hits["contract"]),
            "secondary": len(hits["secondary"]),
            "customization": len(hits["customization"]),
            "certifications": len(hits["certifications"]),
            "emphasis_marks": len(hits["emphasis_marks"]),
        },
    }

    out_path = (Path(args.out) if args.out
                else lines_path.with_name(lines_path.stem.replace(".lines", "") + ".hits.json"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    s = result["summary"]
    print("OK source=%s lines=%d" % (lines_path.name, len(lines)))
    print("detected_marks=%s counts=%s" % (detected, result["emphasis_counts"]))
    print("primary=%d by_scope=%s" % (s["primary"], s["primary_by_scope"]))
    print("contract=%d (合同条款·要点,不计入废标)" % s.get("contract", 0))
    print("secondary=%d customization=%d certifications=%d emphasis=%d"
          % (s["secondary"], s["customization"], s["certifications"], s["emphasis_marks"]))
    print("out=%s" % out_path)


if __name__ == "__main__":
    main()
