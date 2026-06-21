# 30 秒上手

> 把一份**招标文件**喂进去 → 拿到一份给你（投标人）的**投标核对清单**。
>
> 💡 **一行命令都不想敲?**把 [README「怎么开始」](README.md#怎么开始按你的情况选一条路)里的那段话发给你的 AI 助手,它会替你跑完全程(操作手册在 [FOR_AI.md](FOR_AI.md))。下面的步骤是给想自己跑的人。

## 1. 装依赖（一次）

需要 Python 3.8+。没装过的去 [python.org](https://www.python.org/downloads/) 下载安装，勾选 "Add to PATH"。

```bash
pip install -r requirements.txt
```

> pdftotext 可选装不装。不装也能跑 PDF（自动回退 pypdf，效果略差）。

## 2. 自动阶段：取数 + 扫描（几秒）

```bash
python run_pipeline.py prep <你的招标文件.docx>
```

跑完后 `workspace/` 里会有：带行号文本、判决词命中、候选新词。

## 3. 判断阶段：交给 AI agent

把下面这段话发给你的 AI（能操作本地文件的 AI 编程助手）：

> 请按 SKILL.md 的步骤 1-2-4-5 审核这份招标文件。
> 带行号文本在 workspace/xxx.lines.txt，撒网命中在 workspace/xxx.hits.json，
> 参考文档在 references/ 目录，输出写到 workspace/xxx.工作区.md。

agent 会读 SKILL.md 和 references/，产出工作区清单。

## 4. 验证阶段：护栏 + 出 Excel（几秒）

```bash
python run_pipeline.py verify workspace/xxx.工作区.md
```

跑完得到 Excel（多 sheet、带颜色、可筛选）。如果护栏报 warning，让 agent 补漏后重跑。

## 试跑（不需要真标书）

仓库自带测试样本，可以先跑通感受流程：

```bash
python run_pipeline.py prep tests/fixtures/sample_tender.docx
# → workspace/ 下产出 sample_tender.lines.txt + .hits.json + .candidates.json
```

## 流程图

```
你的招标文件
    │
    ▼
 run_pipeline.py prep     ← 全自动（取数+撒网+补词）
    │
    ▼
 AI agent 判断            ← 读 SKILL.md + references/，写工作区 md
    │
    ▼
 run_pipeline.py verify   ← 全自动（护栏检查+出Excel）
    │
    ▼
 xxx.xlsx 交付
```
