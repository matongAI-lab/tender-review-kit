# 安装指南(完全不懂技术也能看)

> **目标**:让你下载完这个工具包后,**全程只回答「装」或「不装」**就能把环境配起来。
>
> 推荐路径:直接跑环境自检,缺什么它都告诉你。
>
> 💡 **更省事的办法**:如果你有能操作本地文件的 AI 助手,连这份指南都不用看——把 [README「怎么开始」](README.md#怎么开始按你的情况选一条路)里的那段话发给它,装环境的活它替你干。

---

## 一步到位:跑环境自检

打开终端(Windows 开始菜单搜 **PowerShell**;macOS 用 **Terminal**;Linux 用你的 shell),`cd` 进入 skill 目录,然后:

```bash
python scripts/check_env.py
```

### 三种结果

**① 全部 ✓ 就绪**
```
✓ 环境完全就绪,可以开始审标书。
```
→ 直接进 **5 分钟上手**,看 [README.md](README.md)。

**② 有缺失 ✗(必装项)**
```
▎必须装的(不装就跑不了):
  • python-docx:解析 .docx 招标文件
    不装的话:无法解析 .docx 文件(.pdf 仍可用)

▎安装命令:
  pip install python-docx
```
→ **复制粘贴跑这一行**,再跑一次 `python scripts/check_env.py` 确认。

**③ 有缺失 ⚠(可选项)**
```
▎可选系统工具:
  • pdftotext(poppler-utils):PDF 解析首选,质量比 pypdf 好
    不装的话:复杂 PDF 版面可能切碎;.docx 不受影响
```
→ **你自己决定**:装了更稳;不装也能跑(自动用 pypdf 兜底)。

---

## 完全没装 Python 怎么办?

按你的电脑系统选一个:

### Windows
推荐两种方式,选一个:
```powershell
# 方式 1:用 winget 一键装(Win10/Win11 自带)
winget install Python.Python.3.12

# 方式 2:从官网下载(适合不熟悉命令行的同学)
# 打开浏览器 → https://www.python.org/downloads/
# 下载 Python 3.12,装的时候 ⭐ 一定要勾「Add Python to PATH」
```
装完关掉 PowerShell 重开一次,然后:
```powershell
python --version    # 应该看到 Python 3.12.x
```

### macOS
推荐 Homebrew:
```bash
# 如果没装 Homebrew:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 装 Python
brew install python@3.12
```

### Linux(Ubuntu / Debian)
```bash
sudo apt update
sudo apt install python3.12 python3-pip
```

### Linux(CentOS / Fedora)
```bash
sudo dnf install python3.12 python3-pip
```

---

## 装完 Python 之后,缺什么都让 check_env 告诉你

```bash
cd <skill 目录>
python scripts/check_env.py
```

它会输出:
- 哪些 Python 包没装 → 给你 `pip install xxx` 命令
- 系统工具 pdftotext 装没装 → 给你对应平台的命令
- **不装的话什么做不了**(让你判断"我要不要这个能力")

---

## 装完之后

```bash
python scripts/check_env.py
# → 看到 "✓ 环境完全就绪" 就可以开始用了
```

回 [README.md](README.md) 的「5 分钟上手」开干。

---

## 常见问题

**Q1:`pip install` 报权限错误怎么办?**
A:加 `--user` 参数,装到用户目录:
```bash
pip install --user -r requirements.txt
```

**Q2:`python` 命令找不到,但我刚装完?**
A:Windows 装 Python 时**没勾「Add to PATH」**——重装一次,这次勾上。或者用 `py` 代替 `python` 试试。

**Q3:我不想装 pdftotext,会有什么影响?**
A:skill 会自动用 pypdf 解析 PDF,**主流程不影响**,只是复杂版面的 PDF(比如多栏 / 表格密集)可能切碎。如果你的标书是 .docx 格式,完全不需要 pdftotext。

**Q4:Mac 提示找不到 brew?**
A:你还没装 Homebrew。按 [https://brew.sh](https://brew.sh) 上的命令装一下。

**Q5:Linux apt install poppler-utils 但还是找不到 pdftotext?**
A:试试 `which pdftotext` 看一下;如果还是没有,可能要把 `/usr/bin` 加进 PATH。

---

**任何时候**,跑一遍 `python scripts/check_env.py` 都会告诉你当前环境状态——这是你的"故障排查第一招"。
