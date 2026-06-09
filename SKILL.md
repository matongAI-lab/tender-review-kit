---
name: tender-review-skill
description: 招标文件审标 / tender document review for bidders。审的是招标方发的招标文件(PDF/Word),服务的是要去投标的人。输出投标核对清单(废标项+评分项+证明材料+▲标识参数+时间节点),帮投标人在动手写投标文件之前把游戏规则吃透。当用户给出招标文件要审、问废标点/否决条款/评分项/资格要求,或要做投标前合规自检时使用——即使没明说"审核"。产清单和事实,不下"投/不投"结论。Use when analyzing Chinese tender/RFP documents for bidders: extract disqualification/scoring items, required materials, ▲-marked parameters, with line-numbered evidence.
---

# 招标文件审标 tender-review-skill

**审的是招标方发的招标文件,服务的是要去投标的人。**

输入一份招标文件 → 产出「投标核对清单」——帮投标人在**动手写投标文件之前**,看清楚招标方的所有要求(哪些不达标会被废、哪些是评分点、要准备什么材料、哪些 ▲ 参数必须响应、哪些时间节点不能错)。

- 产出 = **清单 + 事实**(每条带原文出处行号),**不下"投/不投"结论**——决策是投标人自己的事。
- **工具无关主干**(任何 agent 工具能跑) + **Claude 增强**(subagent 并行 / 红蓝对抗)。
- 架构全貌见 `ARCHITECTURE.md`。

## 四条铁律(每个环节都守)

1. **产清单不下结论**:不写投/不投、不做报价推演、不排 P0-P4。最多 ≤5 条中性提示。
2. **全量不压缩**:撒网命中每条都要处置(纳入 或 写明排除理由);▲ 有多少列多少(本项目曾把 331 个压成 12)。
3. **维度不绑值**:列「业绩要求」「质保期」这些维度,不假设某个具体年限/平台。
4. **列事实带出处**:每条带 lines.txt 行号(护栏靠它核对)——行号要**覆盖判决词所在行**(单行精确,或跨行写范围 `行X–行Y`);`check_coverage` 默认 **±0 精确反查**,引用差几行会判"未覆盖"(宁可误报、不要假覆盖)。保留"否决/无效/视为/加盖原厂公章"等限制性原话;"详见下表/见前附表"必须跟进;评审表每行都是独立条款;评分项≠加分项。

## 核心分工:判断交 Claude,确定性/护栏交程序

| 沉进程序(scripts/) | 留给 Claude(读 references) |
|---|---|
| 确定性 / 可枚举 / 要保证不漏 / 量大 | 要读懂语义("无效投标"vs"无效数据")/ 随文本千变万化 / 靠上下文判断 |

护栏**必须**是程序——Claude 无法可靠审计自己有没有偷懒压缩。

## 端到端流程(招标文件 → Excel)

### 0. 取数　[程序]
`python scripts/extract_text.py <招标文件> --outdir workspace`
→ `<项目>.lines.txt`(带行号,一切定位的锚点) + `.tables.json`。支持 .docx/.pdf;.doc 先另存为 docx/pdf。

### 1. 摸底 + 对照审标清单　[Claude 判断]
读封面 + 目录 + 须知前 ~200 行,**扫基本盘**(什么法规、买货/工程/服务、综合评分/低价)。**不分 9 类、不套模板**——大模型直接读懂文件,不需要先分类选模板。然后对照 `references/disqualification-checklist.md` **逐条看这份有没有那些坑**(隐性门槛 / 中小企业价扣 / CCC 三者一致 / 投标担保…)。核心永远是:**找 ▲ 星号项 + 找商务非标项**。

### 2. 产物定位　[Claude 判断]
Grep 章节标题,定位 4 必扫产物的**行号范围**:投标人须知 / 评标办法 / 评分细则 / 评审标准表。形式多样(章节 / 表 / N 表替代),不盲信单一形式。

### 3. 双扫描:撒网 + 补词　[程序]

**两次扫描角色不同,务必区分。建议同时跑,几秒钟。**

**① 撒网(必做,为当前这份标书):**
`python scripts/scan_keywords.py workspace/<项目>.lines.txt`
→ `.hits.json`:用现有判词库(5 类、100+ 词)逐行扫,5 类命中(判决词 / 二级 / 关系门槛 / 证明文件 / ▲★,▲★ 自适应识别、少量也不丢)。**宽撒网、含噪音**,去噪留给 subagent。**不跑这步,后面 subagent 没线索池可用,流程断。**

**② 补词(顺手跑,为未来攒词库):**
`python scripts/scan_candidates.py workspace/<项目>.lines.txt --hits workspace/<项目>.hits.json`
→ `workspace/<项目>.candidates.json`:扫"像判决词、未入库"的新短语(用 8 个句式模式 + 已知判决词邻近度加分),进候选区,**强制 `pending_review`、绝不自动入库**。候选文件含**原文片段**,随项目留在 workspace(不进仓库);入库时 `promote_candidates.py` 只把词+scope 写进 keywords.json,不带原文。

**关键认知**(开源贡献者必看):
- `scan_keywords` = 用现有通缉令抓人 → **为当前办案**
- `scan_candidates` = 顺手记下长得像通缉犯但不在令上的人 → **更新通缉令,为以后办案**
- 两者**逻辑独立**,候选词审核入库后供下次扫描使用(当前标书已跑过 scan_keywords)
- **"当前标书不漏"靠三道保险**:① 两层防线(§6)防漏抄 ② AI 在 Step 5 判断时发现的新判决词直接纳入当前清单(标 `[AI发现]`) ③ 同时上报到 `## AI发现疑似判词`,由 `harvest_ai_words.py` 收割进候选库,人审入库后**下次标书自动扫到**。
- `scan_candidates` + AI 上报 = 两条补词通道(程序正则 + AI 语义),判词库从两个方向长大。

### 4. 建工作区
`workspace/<项目>.工作区.md`:项目元信息 + 第 2 步的章节行号 + 商务/技术分区。

### 5. 派专项(商务线 / 技术线分头)　[Claude 判断,可 subagent 并行]
每个专项:读对应 reference + hits.json → **只读自己的章节行号范围**(不全读) → 筛撒网去噪 + 对照 `disqualification-checklist.md`(审标对照总清单) + 实读条款 → 写工作区对应分区。

- **商务线**(`references/commercial/`):废标排查[✓] · 评分(价格分 + 商务分) · 证明文件清册(横切聚合,**输出标准 md 表格**) · 关系门槛 · 时间节点
- **技术线**(`references/technical/`):▲★ 响应[✓](**先定位"实质性要求"范围** → 范围内的 ▲ 才是废标,其余是评分项) · 技术评分 · 规范偏离

> 纪律:每个专项只读自己一片、写工作区、不背前序上下文(线性也不爆 token);并行态用 subagent,二者读同一套 references、同一套 data。

> ⭐ **输出结构规范(所有专项必守)**:**主清单 Markdown 表格放在 `## 专项标题` 正下方,不要嵌进 `### 子节`**。说明性内容(台账/对照核验/特化对照/发现/建议/边界)用 `### 子节`,程序会跳过其表格。否则护栏会漏数,Excel 也转不进对应 sheet。

> ⭐ **AI 发现疑似判词(所有专项必守)**:读条款时如果遇到**具有判决效力但 hits.json 未命中**的语言(如"取消中标资格""视为虚假应标""不列入合格名单"等),必须做两件事:
> 1. **纳入当前清单**:写进对应专项的主清单表格,出处列标注 `[AI发现]`——不能因为不在判词库就丢掉。
> 2. **上报候选词**:在工作区 md **最末尾**追加 `## AI发现疑似判词` section,用标准表格列出:
>
> ```markdown
> ## AI发现疑似判词
>
> | 疑似判词 | 原文摘要 | 出处 | 建议分类 |
> |----------|----------|------|----------|
> | 取消中标资格 | 若发现围标串标行为,取消中标资格 | 行156 | primary/bid_phase |
> ```
>
> 建议分类格式:`类别/scope`(类别=primary/secondary/customization/certifications;scope=bid_phase/evaluation_phase/contract_phase)。

### 5.5. 列出待审新词　[程序,自动跑]
`python scripts/harvest_ai_words.py <工作区.md>` (verify 阶段自动调用)
解析 `## AI发现疑似判词` 表格 → 写 `workspace/<项目>.pending_words.json`(**待审清单,尚未入库**)→ 打印每个词的建议分类、scope、原文片段。

### 5.6. AI 对话,请用户拍板　[Claude 询问]
**关键:AI 发现的词不能默默入库**——AI 判断可能漏估语境("无效投标"vs"无效数据"),用户最了解自己领域,必须由用户拍板。

AI 用自然对话告知用户:

> 本次审标我发现了 N 个 hits.json 没覆盖、但具有判决效力的语言:
> 1. **不接受联合体投标**(建议 primary/bid_phase,行9)
> 2. **取消中标资格**(建议 primary/bid_phase,行156)
> ...
>
> 这些词如果加入你的**本地词库**(只存你机器上,不传任何地方),下次扫别的标书会自动扫到。**你看哪些要接受?**
>
> - 全部接受 → 我帮你跑 `--accept-all`
> - 部分接受 → 告诉我哪几个(比如"接受第 1、3 个")
> - 全部拒绝 → 跑 `--reject-all`

用户答复后,AI 调用:
- 全接受:`python scripts/harvest_ai_words.py <工作区.md> --accept-all`
- 部分:`python scripts/harvest_ai_words.py <工作区.md> --accept "词A,词B"`
- 全拒绝:`python scripts/harvest_ai_words.py <工作区.md> --reject-all`

接受的词进 `data/local_keywords.json`(gitignored)。

### 5.7. 自动回扫 + AI 补漏　[程序 + Claude 判断]
`--accept-all`/`--accept` 命令**自动触发回扫**:用合并后的词库重扫 lines.txt → diff 新旧 hits → 报出"因新词而新增的命中行"。

AI 看新增命中,逐条判断:
- **是新废标点 / 评分项 / 标识项** → 补到工作区对应清单(出处标 `[新词补扫]`)。
- **是误命中**(语境不同) → 跳过,但记录原因。

> 5.5+5.6+5.7 闭环的意义:AI 在 Step 5 只读了自己负责的章节,发现的新词可能在文件其他位置也出现。**用户拍板**(避免本地库被污染)+ **回扫**(当前标书不漏)+ **本地积累**(下次自动扫到)。

### 6. 两层护栏　[防漏命根子]
**第一层 · 程序(防"漏抄")**:
- `python scripts/check_coverage.py <hits.json> <工作区.md> [--strict]` —— 撒网命中是否被废标清单覆盖,未覆盖按严重度列出,**逐条核**(未覆盖 ≠ 漏,不卡覆盖率阈值)。容差默认 **±0 精确匹配**(放宽会把相邻不同条款误判已覆盖);`--strict` 在有 high 级未覆盖时非零退出,供自动流程 gate。
- `python scripts/check_completeness.py <工作区.md> --hits <hits.json> [--strict]` —— 条数通用基线 / 评分梯度含"分"字 / ▲ ≥ 撒网 ×80%;`--strict` 有 warning 时非零退出。

**第二层 · Claude(防"判断死角")** —— 见下「质量旋钮」。

### 7. 出报告　[程序]
`python scripts/build_excel.py <out.xlsx> <各专项 md...>` → 多 sheet Excel(废标红 / 评分绿 / ▲橙 / 证明紫 / 时间蓝,冻结首行、可筛选)。另存一份 Markdown 总览。

### 8. 收尾：开源词库的互惠机制（可选）　[Claude 询问]
出完 Excel 后,检查 `data/local_keywords.json` 是否存在且非空（本次或历次审标接受入库的词）。如果有,**用自然对话告知用户**:

> 这次你接受入库的判词(像"取消中标资格""不接受联合体投标"这种),已经留在你的本地词库里——下次扫别的标书会自动用上。
>
> 想不想让其中**普遍适用**的词也进入开源 keywords.json?这个项目的判词库就是大家一起攒的——
>
> - 你今天贡献几个词,**别人下次更新时也能用上你的发现**
> - 别人今天贡献几个词,**你下次 `git pull` 后也能直接用**
>
> 你的本地词库**永远是你自己的**(下次审标 AI 还会发现新词,继续往里加),而开源词库是公共的——**只有你 follow 这个项目并定期拉取,才能享受大家一起攒的成果**。
>
> 完全自愿。要把这些词加进开源吗?

- 用户说好 → 跑 `python scripts/export_contribution.py --github`(自动从 `data/local_keywords.json` 读取并创建 GitHub Issue)。如果没装 gh CLI,改用 `export_contribution.py`(无 --github)导出文件,告诉用户粘贴到 https://github.com/matongAI-lab/tender-review-kit/issues/new
- 用户说不 → 正常结束,不再提。**也顺便告诉用户:即使不贡献,follow 仓库 + 定期 `git pull` 就能持续拿到别人贡献的更新**。
- **只问一次,不纠缠;语气是平等的、说明机制,不是请求**

## 两层防线 + 质量旋钮(核心方法论)

**两种漏,两种药,缺一不可:**
- **反向校验**(check_coverage):防"漏抄"——原文有判决词命中、清单没纳入。**程序**能逮,每次自动跑。
- **A/B 红蓝对抗**:防"判断死角"——该不该算废标、隐性门槛、原文数据矛盾。**只能靠第二个独立的脑子**,程序逮不到。

**A/B 红蓝对抗怎么做**:关键专项派**两个独立 subagent**各做一遍,再比差异——差异处就是至少一方的盲区,重点核。前提:**必须真独立(双盲),不能互看答案**,否则盲区会传染。

**质量旋钮**(按标书重要性拧):
- **重要标书** → 关键专项(废标 / ▲)开 A/B 双跑对抗。
- **普通标书** → 单跑 + 程序护栏(第一层)就够。

## 文件地图

```
scripts/    extract_text✓ scan_keywords✓(为当前) scan_candidates✓(为未来,程序补词)
            harvest_ai_words✓(收割AI发现) check_coverage✓ check_completeness✓
            cross_doc✓(跨文件矛盾) build_excel✓
references/ disqualification-checklist✓(审标对照总清单:废标点+隐性门槛+类型特化+必拿字段)
            commercial/ disqualification✓ scoring✓ certifications-roster✓ timeline✓
            technical/  essential-response✓ scoring✓ spec-deviation✓
data/       keywords.json✓(命根子,120+ 词) | 候选词在 workspace/<项目>.candidates.json(含原文,不入库) | 不再分 9 类,改用 disqualification-checklist.md 逐条对照
ARCHITECTURE.md  六层架构纲领
```

## 已验证(跨多类实战)
端到端跑通涵盖货物·综合评分、央企货物、政采服务、工程·合理低价等多类标书。典型规模:取数千行级 / 撒网百级判决词 / 双线专项产出废标项 + 评分项 + ▲ 清单(数百级) + 证明清册 + 时间节点 → 程序护栏 + 人工复核。A/B 红蓝对抗已实证可逮出各方盲区(计分说明行 / 隐性门槛升格)。

## 跨工具 / 依赖
程序 = Python 标准库 + python-docx + pypdf + openpyxl(均 pip);系统依赖仅 pdftotext(PDF 用,缺则回退 pypdf)。相对路径。subagent 是 Claude / Claude Code 专属,其他工具(Codex / workbuddy / 阿里)走线性 §5,输出一致。
