# tender-review-kit · 招标文件审标工具包(为投标人服务)

> **审的是招标方发的招标文件,服务的是要去投标的人。**
>
> 输入:招标文件(PDF/Word) → 输出:**投标核对清单**(废标项 + 评分项 + 证明材料 + ▲ 标识参数 + 时间节点),每条带行号出处。
> 帮投标人在**动手写投标文件之前**,把招标方的游戏规则全部吃透——不踩废标、不漏评分、不缺材料、不错节点。
>
> **产清单和事实,不下"投/不投"结论。** 决策是投标人自己的事,工具的本分是让他看见全部要求。

> ⚠️ **当前状态:开发中(WIP)**
>
> 接口与判词库仍在迭代,这是早期快照——生产使用请自行评估、先跑通自家标书。
>
> 本项目按 **MIT 许可开源**(见文末 License),可自由使用 / 修改 / 商用。欢迎试用、提 PR、扩词库。

## 版本路线

**当前版本:Community Edition v0.1.3(社区开源版)**——本仓库内容,**MIT 许可,免费使用 / 修改 / 商用**。
- 8 个核心程序(取数 / 撒网 / 补词×2 / 查漏 / 完整性 / 跨文件 / Excel) + 一键编排 `run_pipeline.py`
- **判词库分两层**:开源词库(共享,~120+ 词)+ 用户本地词库(私有积累,gitignored)
- **AI 发现新词的用户审批流**:不再自动入库,用户拍板决定是否接受
- **互惠贡献闭环**:你贡献几个,以后别人贡献的你也能拉到
- 4 类常见标书的类型特化规则(工程·合理低价 / 货物·综合评分 / 政采服务 / 央企货物,并入审标对照清单)
- 完整的两层防线 + 红蓝对抗方法论
- **够用,但你要的"省心 / 不漏 / 跨行业"得靠社区一起攒(欢迎贡献)**

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

**tender-review-kit 把两者长处缝起来,而且把"准确/不漏"摆在第一**:
> **判词库**(确定的底盘,保证该找的不漏) × **大模型读懂**(分清"无效投标"vs"无效数据") × **程序护栏**(防压缩 + 反向校验) × **A/B 红蓝对抗**(防判断死角)

**核心优势**:
1. **判词库是核心资产** —— 几百次实战攒的判决词,代码能开源,**判词库越用越厚是真护城河**。
2. **可复现的扫描** —— 同样一份标书,跑十次结果一样。判词扫描是确定性的;准确率量化需专家真值集(路线图中)。
3. **两层防漏机制** —— 反向校验防"漏抄",红蓝对抗防"判断死角"。
4. **跨工具** —— 线性主干在 Claude / Codex / 国产 agent 都能跑;Claude 下额外有 subagent 并行 + 红蓝对抗增强。

## 5 分钟上手

> 详细版见 [QUICKSTART.md](QUICKSTART.md)。下面是最短路径。

```bash
# 1. 装依赖(一次,需要 Python 3.8+)
pip install -r requirements.txt
# (PDF 提取建议装 pdftotext: Windows xpdf-tools / mac brew install poppler / ubuntu apt install poppler-utils。不装也能跑,自动回退 pypdf)

# 2. 程序自动跑(取数 + 撒网 + 补词,几秒)
python run_pipeline.py prep <招标文件.docx 或 .pdf>

# 3. 把 prep 结尾打印的那段提示发给你的 AI agent(Claude / Codex / Workbuddy 等)
#    → agent 按 SKILL.md 步骤产出 workspace/<项目>.工作区.md
#    → 含 AI 新发现的疑似判词(标 [AI发现])

# 4. 程序自动跑(护栏 + 出 Excel,几秒)
python run_pipeline.py verify workspace/<项目>.工作区.md

# 5. 如果 AI 发现了新判词,审批是否接受
python scripts/harvest_ai_words.py workspace/<项目>.工作区.md --accept-all
#    (接受的进 data/local_keywords.json 用户本地积累,下次扫别的标书自动用上)

# 6. (可选) 把普遍适用的新词加进开源词库,以后别人贡献的你也能拉到
python scripts/export_contribution.py --github
```

**自带 sample 试跑**(不需要真标书):
```bash
python run_pipeline.py prep tests/fixtures/sample_tender.docx
```

## 项目结构

```
tender-review-kit/
├── QUICKSTART.md         # 30 秒上手指南
├── SKILL.md              # skill 入口 + 端到端工作流(7步)
├── ARCHITECTURE.md       # 设计纲领(六层栈 + Python/LLM 分工 + 数据驱动)
├── run_pipeline.py       # 一键编排: prep(取数+扫描) / verify(护栏+Excel)
├── scripts/              # 程序层(确定性 + 护栏,纯标准库+少量 pip)
│   ├── extract_text.py        # 取数: PDF/Word → 带行号文本
│   ├── scan_keywords.py       # 判词撒网: 自动合并加载开源 + 本地词库
│   ├── scan_candidates.py     # 补词引擎(程序通道): 正则扫疑似新判决词
│   ├── harvest_ai_words.py    # 补词引擎(AI通道): AI 发现的词 → 待审 → 用户拍板 → 入本地库 + 回扫
│   ├── promote_candidates.py  # 候选词审批入库(scan_candidates 产物)
│   ├── export_contribution.py # 脱敏导出本地新词 → 开源 keywords.json(一键提 Issue)
│   ├── check_coverage.py      # 反向校验: 命中是否被废标清单覆盖
│   ├── check_completeness.py  # 完整性: 条数/梯度/▲ 覆盖
│   ├── cross_doc.py           # 跨文件矛盾: 金额/日期/数量
│   └── build_excel.py         # md 清单 → 多 sheet Excel
├── data/                 # 数据层
│   ├── keywords.json          # 开源判词库 5 类 ⭐ 命根子(PR 可改,所有用户共享)
│   └── local_keywords.json    # 用户本地积累(gitignored,审批入库后下次扫别标书自动用上)
├── references/           # 知识层(专项工作指南)
│   ├── disqualification-checklist.md   # 审标对照总清单(废标点+隐性门槛+类型特化+必拿字段)
│   ├── commercial/                     # 商务线: 废标/评分/证明/时间
│   └── technical/                      # 技术线: ▲★ 响应/评分/规范偏离
├── workspace/            # 运行时中间产物
└── tests/                # 回归基准
```

## 怎么贡献(互惠机制)

**开源词库 = 所有用户一起攒**——你今天贡献几个词,以后别人贡献的你也能拉到。
- ✅ Follow 这个仓库 + 定期 `git pull` → 自动用上所有贡献者的发现
- ✅ 用 `export_contribution.py` 把你的词加进开源 → 别人也能用上你的判断
- ✅ 你的本地词库(`data/local_keywords.json`)永远是你自己的,贡不贡献都在,扫别的标书继续用

**最有价值的贡献 = 扩判词库**:
```bash
# 1. 审完标书后,审批 AI 发现的词(--accept-all 全收 / --accept "词" 部分收 / --reject-all 全弃)
python scripts/harvest_ai_words.py workspace/<项目>.工作区.md --accept-all

# 2. 把本地词库里普遍适用的词加进开源(自动脱敏,不含标书原文)
python scripts/export_contribution.py            # 导出预览
python scripts/export_contribution.py --github   # 一键提 Issue(需装 gh CLI 并登录)
```
工具会同时收集两条通道(程序补词 candidates.json + AI 发现 local_keywords.json),去掉原文片段,去重现有开源词库,生成干净的贡献表。

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
- [x] 8 大程序 + 一键编排(`run_pipeline.py`)+ 通用机制清单
- [x] 判词库分两层(开源共享 + 用户本地积累)+ 互惠贡献闭环(v0.1.3)
- [x] AI 发现新词的用户审批流(v0.1.3)
- [ ] 更多类型实战覆盖
- [ ] 准确率量化(真值标注 + 测试集)
- [ ] 词库扩展(目标:200+ 判决词,靠贡献闭环自然生长)

## License

本项目采用 **MIT License** —— 自由使用 / 修改 / 商用,保留版权与许可声明即可。完整条款见仓库根目录 `LICENSE` 文件。

## 致谢

本项目方法论沉淀自多份真实招标文件实战。判词库是公共资产,欢迎扩充。
