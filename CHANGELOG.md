# Changelog

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
