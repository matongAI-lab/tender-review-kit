# Changelog

## 2026-06-15 · Community Edition v0.1.9

### Changed

- 强化用户贡献隐私声明：贡献完全自愿,不给也能正常使用工具。
- 明确脱敏贡献只包含判词短语、建议分类、scope、发现方式、出现次数。
- 明确不会导出标书原文、项目名称、行号上下文、Excel、工作区全文或用户本地词库文件。
- 明确 `export_contribution.py --github` 默认创建 GitHub Issue 供维护者审核,不会自动合并进开源总词库。
- `README.md`、`SKILL.md`、`FOR_AI.md`、`run_pipeline.py` 和 `export_contribution.py` 均同步展示同一套说明。

## 2026-06-15 · Community Edition v0.1.8

### Changed

- 开源 `data/keywords.json` 新增 5 个用户确认过的通用判词：
  - `视为无效投标响应`
  - `取消中标资格`
  - `不接受联合体投标`
  - `不接受分包、转包`
  - `视为未实质响应采购文件`

### Privacy

- 本次词库贡献只包含判词短语和 scope,不包含任何真实标书原文、项目名称、Excel 结果、workspace 产物或用户本地词库文件。

## 2026-06-15 · Community Edition v0.1.7

### Fixed

- 解耦“当前标书补漏”和“是否入本地词库”：`harvest_ai_words.py` 默认用 AI 发现词临时回扫当前 `lines.txt`,不写 `data/local_keywords.json`;用户接受/拒绝只影响以后标书是否自动命中。
- `--reject-all` 现在明确提示：拒绝入库不代表当前标书忽略这些词,当前补漏应以上一次临时回扫新增命中为准。

### Changed

- `run_pipeline.py verify` 收尾固定说明词库互惠机制,即使当前还没有本地词库,也会提示以后如何脱敏贡献。
- `SKILL.md` 和 `FOR_AI.md` 明确三条红线：当前补漏不等用户入库;入库必须用户拍板;对外贡献必须用户明确同意。

### Tests

- 新增回归：默认收割 AI 发现词时会临时回扫当前标书。
- 新增回归：拒绝入库只清待审清单,不会被解释为忽略当前补漏。

## 2026-06-15 · Community Edition v0.1.6

### Fixed

- 修复 `exclude_patterns_global` 中 `目录` 匹配过宽的问题：现在只排除独立目录页行，避免正文技术参数中的“目录树/控制面板目录”等字样导致整行被跳过。
- 修复 `scan_keywords.py` 对强调标识的行级压缩问题：当 Word 表格被摊平成一条长行、且同一行包含多个 `▲/★/※` 参数时，现在会按标识逐条写入 `hits.emphasis_marks`。

### Changed

- `hits.emphasis_marks` 新增 `item_index` 字段，用于标记同一原始行内拆出的第几条强调标识。
- `SKILL.md` 和技术线参考文档明确要求：技术 `▲/★` 清单必须回到 `lines.txt` 或原表格逐项核对，`hits.json` 只作为线索底稿，不作为最终清单。
- 审标总清单新增“表格长行要拆”的通用检查提醒。

### Tests

- 新增回归：正文中出现“目录”不应被全局排除。
- 新增回归：同一表格行内多个 `▲/★` 必须拆成多条 emphasis hit。

### Privacy

- 本次更新不包含任何真实招标文件、Excel 结果、workspace 运行产物或用户本地词库。
