# bid-review-kit · 投标审核工具包

> 拿到招标文件(PDF/Word)→ 自动产出**投标核对清单**(废标项 + 评分项 + 证明材料 + ▲ 标识参数 + 时间节点)。
> 帮投标人在递交投标文件之前发现合规风险、估算得分、备齐材料。
>
> **产清单和事实,不下"投/不投"结论。**

> ⚠️ **当前状态:开发中(WIP)**
>
> 接口与判词库仍在迭代,这是早期快照——生产使用请自行评估、先跑通自家标书。
>
> 本项目按 **MIT 许可开源**(见文末 License),可自由使用 / 修改 / 商用。欢迎试用、提 PR、扩词库。

## 版本路线

**当前版本:Community Edition(社区开源版)**——本仓库内容,**MIT 许可,免费使用 / 修改 / 商用**。
- 7 个核心程序(取数 / 撒网 / 补词 / 查漏 / 完整性 / 跨文件 / Excel)
- 基础判词库(约 100 词,覆盖通用否决/废标信号)
- 4 类常见标书的类型特化规则(工程·合理低价 / 货物·综合评分 / 政采服务 / 央企货物,并入审标对照清单)
- 完整的两层防线 + 红蓝对抗方法论
- **够用,但你要的"省心 / 不漏 / 跨行业"得自己往里加**

**规划中:Professional Edition(专业版,正在开发)**——商业产品,不在本仓库:
- **更全的判词库**:几百至上千词,带行业细分 scope(医疗 / 军工 / 海外 / 科研…)和实战准确率证明
- **更全的类型规范**:几十类标书的完整机制档案(单一来源 / 询价 / 竞争性磋商 / 海外英标 / 政府购买服务 / 工程总承包 / 框架协议 等)
- **云端补词服务**:扫一份标书 → AI 自动提候选词 + 验证 + 入库,贡献给同订阅级别的所有用户(集体智能)
- **类型自动识别 + 定制化指南 API**
- **准确率验证服务**:你的清单 vs 专家答案库 → 给质量评分

**Enterprise / 定制版**:私有部署、行业专版、团队协作、一对一类型校准。

> Community Edition 是地基,够任何人验证方法论、试用流程、跑通自家标书。
> 想要"省心 + 不漏 + 跨行业",请关注 Professional Edition。

## 这个项目的价值在哪

市面上现在有两种东西:
- **老牌投标软件**:靠关键词匹配。死板,不会读——"无效投标"和"无效数据"分不清,误报一大堆。
- **新的 AI 标书工具**:让大模型读。会读,但**漏了你不知道、这次和下次不一样、攒不下东西**。

**bid-review-kit 把两者长处缝起来,而且把"准确/不漏"摆在第一**:
> **判词库**(确定的底盘,保证该找的不漏) × **大模型读懂**(分清"无效投标"vs"无效数据") × **程序护栏**(防压缩 + 反向校验) × **A/B 红蓝对抗**(防判断死角)

**核心优势**:
1. **判词库是核心资产** —— 几百次实战攒的判决词,代码能开源,**判词库越用越厚是真护城河**。
2. **可复现的扫描** —— 同样一份标书,跑十次结果一样。判词扫描是确定性的;准确率量化需专家真值集(路线图中)。
3. **两层防漏机制** —— 反向校验防"漏抄",红蓝对抗防"判断死角"。
4. **跨工具** —— 线性主干在 Claude / Codex / 国产 agent 都能跑;Claude 下额外有 subagent 并行 + 红蓝对抗增强。

## 5 分钟上手

```bash
# 1. 装依赖
pip install -r requirements.txt
# (PDF 提取需要 pdftotext, Windows 装 xpdf-tools, mac: brew install poppler, ubuntu: apt install poppler-utils)

# 2. 取数:招标文件 → 带行号文本
python scripts/extract_text.py <招标文件.docx 或 .pdf> --outdir workspace

# 3. 判词撒网:扫 5 类判决词信号
python scripts/scan_keywords.py workspace/<项目>.lines.txt

# 4. 补词引擎:扫"像判决词、未入库"的新词到候选区
#    → workspace/<项目>.candidates.json(含原文片段,留在本地、不进仓库)
python scripts/scan_candidates.py workspace/<项目>.lines.txt --hits workspace/<项目>.hits.json

# 5. 让 agent(Claude/Codex/国产)按 SKILL.md 流程整理清单,落到 workspace/<项目>.工作区.md

# 6. 两道护栏
python scripts/check_coverage.py workspace/<项目>.hits.json workspace/<项目>.工作区.md
python scripts/check_completeness.py workspace/<项目>.工作区.md --hits workspace/<项目>.hits.json

# 7. 出 Excel
python scripts/build_excel.py 输出.xlsx workspace/<项目>.工作区.md [其他专项 md...]
```

## 项目结构

```
bid-review-kit/
├── SKILL.md              # skill 入口 + 端到端工作流(7步)
├── ARCHITECTURE.md       # 设计纲领(六层栈 + Python/LLM 分工 + 数据驱动)
├── scripts/              # 程序层(确定性 + 护栏,纯标准库+少量 pip)
│   ├── extract_text.py        # 取数: PDF/Word → 带行号文本
│   ├── scan_keywords.py       # 判词撒网: 5 类判决词命中
│   ├── scan_candidates.py     # 补词引擎: 扫疑似新判决词
│   ├── check_coverage.py      # 反向校验: 命中是否被废标清单覆盖
│   ├── check_completeness.py  # 完整性: 条数/梯度/▲ 覆盖
│   ├── cross_doc.py           # 跨文件矛盾: 金额/日期/数量
│   └── build_excel.py         # md 清单 → 多 sheet Excel
├── data/                 # 数据层(开源活资产,可 PR)
│   └── keywords.json          # 判词库 5 类 ⭐ 命根子(候选词在 workspace/,含原文不入库)
├── references/           # 知识层(专项工作指南)
│   ├── disqualification-checklist.md   # 审标对照总清单(废标点+隐性门槛+类型特化+必拿字段)
│   ├── commercial/                     # 商务线: 废标/评分/证明/时间
│   └── technical/                      # 技术线: ▲★ 响应/评分/规范偏离
├── workspace/            # 运行时中间产物
└── tests/                # 回归基准
```

## 怎么贡献

**最有价值的贡献 = 扩判词库**:
1. 用本工具扫一份你手上的招标文件 → `scan_candidates.py` 扫出新候选词
2. 选出真信号(投标/评标阶段、完整短语、不被现有词包含) → PR 到 `data/keywords.json`
3. 附上"在哪个标书发现 + 原文片段"作说明

**其他贡献方向**:
- 补 references(给审标对照清单加条目 / 补专项工作指南)
- 程序层小修复(extraction edge case / Excel 输出样式)
- 拿真标书 + 专家答案对比,提供准确率量化数据(测试集)

## 设计原则

1. **判词库是核心,准确第一** —— 提示词没壁垒、不可复现;判词库才是护城河。
2. **判断交大模型,确定性/护栏交程序** —— 护栏必须是程序,大模型不能审计自己。
3. **全量不压缩** —— 撒网命中每条都要处置,▲ 有多少列多少。
4. **列事实带出处,不下结论** —— 不写投/不投、不做报价推演。
5. **数据驱动 + 工具无关** —— 知识沉淀进 `data/` 和 `references/`,核心流程任何 agent 工具都能跑。

详见 `ARCHITECTURE.md` 与 `SKILL.md`。

## 路线图

- [x] 端到端跑通(覆盖货物·综合评分、央企货物、政采服务、工程·合理低价多类标书实战验证)
- [x] A/B 红蓝对抗实验(两个独立 subagent 处理同一份 300+ ▲ 标书,覆盖一条不差,各自逮到对方盲区)
- [x] 七大程序 + 补词引擎 + 通用机制清单
- [ ] 更多类型实战覆盖
- [ ] 准确率量化(真值标注 + 测试集)
- [ ] 词库扩展(目标:200+ 判决词)

## License

本项目采用 **MIT License** —— 自由使用 / 修改 / 商用,保留版权与许可声明即可。完整条款见仓库根目录 `LICENSE` 文件。

## 致谢

本项目方法论沉淀自多份真实招标文件实战。判词库是公共资产,欢迎扩充。
