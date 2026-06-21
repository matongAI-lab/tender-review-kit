#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_env.py — 环境自检 + 友好安装引导

skill 第一步:确认运行环境就绪。
缺什么 → 列出缺失项 + 平台对应安装命令 + 不装的话什么做不了。
用户只需回答「装」或「不装」。

纯标准库(sys/shutil/platform/importlib)——本脚本本身**没有任何依赖**,
即使项目依赖都没装,这个脚本也能跑起来告诉用户该装啥。

用法:
    python scripts/check_env.py
"""
import sys
import shutil
import platform
import importlib.util

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def check_module(name, friendly_name=None):
    """返回 (已装?, 版本字符串 或 None)"""
    friendly = friendly_name or name
    spec = importlib.util.find_spec(name)
    if spec is None:
        return False, None
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", None) or "已装"
        return True, str(ver)
    except Exception as e:
        return False, "import 失败:" + str(e)[:60]


def main():
    print("=== tender-review-skill 环境自检 ===\n")
    system = platform.system()  # Windows / Darwin / Linux
    py_ver = sys.version_info
    py_ok = py_ver >= (3, 8)
    print(f"运行平台: {system}  Python: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    if py_ok:
        print(f"  ✓ Python ≥ 3.8\n")
    else:
        print(f"  ✗ Python 太旧!需要 ≥ 3.8(当前 {py_ver.major}.{py_ver.minor})\n")

    # ---- 检查项 ----
    # (key, 友好名, 用途, 缺失影响, 是否必须)
    checks = [
        ("docx", "python-docx", "解析 .docx 招标文件", "无法解析 .docx 文件(.pdf 仍可用)", True),
        ("pypdf", "pypdf", "解析 PDF(兜底)", "无法解析任何 PDF 文件", True),
        ("openpyxl", "openpyxl", "出 Excel", "无法生成最终 Excel 核对清单", True),
    ]

    print("▎Python 包")
    pkg_results = []
    for mod, name, use, impact, required in checks:
        ok, info = check_module(mod, name)
        status = "✓" if ok else "✗"
        ver = f" ({info})" if ok else ""
        print(f"  {status} {name:<14}{ver:<12} — {use}")
        pkg_results.append((ok, name, use, impact, required))
    print()

    # ---- 系统工具 pdftotext ----
    print("▎系统工具")
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        print(f"  ✓ pdftotext           {pdftotext}")
        pdftotext_ok = True
    else:
        print(f"  ⚠ pdftotext           未找到(可选,缺了 PDF 解析会自动降级用 pypdf,质量略低)")
        pdftotext_ok = False
    print()

    # ---- 汇总 + 安装命令 ----
    missing_required = [(n, u, i) for ok, n, u, i, req in pkg_results if not ok and req]
    missing_optional = [(n, u, i) for ok, n, u, i, req in pkg_results if not ok and not req]

    if not py_ok:
        print("=" * 60)
        print("✗ Python 版本不够,无法继续。")
        print()
        if system == "Windows":
            print("装 Python 3.12 (Windows):")
            print("  方法1:  https://www.python.org/downloads/ 下载 → 安装时勾「Add to PATH」")
            print("  方法2:  winget install Python.Python.3.12")
            print("  方法3:  Microsoft Store 搜 Python")
        elif system == "Darwin":
            print("装 Python 3.12 (macOS):")
            print("  方法1:  brew install python@3.12")
            print("  方法2:  https://www.python.org/downloads/ 下载安装包")
        else:
            print("装 Python 3.12 (Linux):")
            print("  Ubuntu/Debian:  sudo apt install python3.12 python3-pip")
            print("  CentOS/Fedora:  sudo dnf install python3.12 python3-pip")
        print()
        sys.exit(1)

    if not missing_required and not missing_optional and pdftotext_ok:
        print("=" * 60)
        print("✓ 环境完全就绪,可以开始审标书。")
        print()
        print("下一步:python scripts/extract_text.py <你的招标文件.pdf 或 .docx> --outdir workspace")
        return

    print("=" * 60)
    print("⚠ 环境检查结果:有缺失项")
    print()

    if missing_required:
        print("▎必须装的(不装就跑不了):")
        for name, use, impact in missing_required:
            print(f"  • {name}:{use}")
            print(f"    不装的话:{impact}")
        print()

    if missing_optional:
        print("▎可选的(不装不影响主流程):")
        for name, use, impact in missing_optional:
            print(f"  • {name}:{use}")
            print(f"    不装的话:{impact}")
        print()

    if not pdftotext_ok:
        print("▎可选系统工具:")
        print("  • pdftotext(poppler-utils):PDF 解析首选,质量比 pypdf 好")
        print("    不装的话:复杂 PDF 版面可能切碎;.docx 不受影响")
        print()

    # ---- 安装命令 ----
    pip_pkgs = [n for n, _, _ in missing_required + missing_optional]
    print("=" * 60)
    print("▎安装命令(选你要装的,装完再跑一次本脚本确认):")
    print()
    if pip_pkgs:
        print("  ► Python 包(一条命令搞定):")
        print(f"      pip install {' '.join(pip_pkgs)}")
        print(f"    或安装全部依赖:")
        print(f"      pip install -r requirements.txt")
        print()
    if not pdftotext_ok:
        print("  ► pdftotext(可选,各平台不同):")
        if system == "Windows":
            print("      Windows:  下载 https://www.xpdfreader.com/download.html")
            print("                解压后,把 bin64 目录加到 PATH 环境变量")
        elif system == "Darwin":
            print("      macOS:    brew install poppler")
        else:
            print("      Ubuntu/Debian:  sudo apt install poppler-utils")
            print("      CentOS/Fedora:  sudo dnf install poppler-utils")
        print()

    print("=" * 60)
    print("▎你的选择:")
    print("  装 → 按上面命令装,装完再跑:python scripts/check_env.py")
    print("  不装 → skill 仍可用,但有上述限制(注意必须装的项不装会报错)")
    sys.exit(0 if not missing_required else 2)


if __name__ == "__main__":
    main()
