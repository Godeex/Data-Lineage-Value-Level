# 标注笔记 — 标注者 C（保守派）

- 角色：保守派标注者
- 日期：2026-11-18
- 工时：约 6 小时（42 条 SQL；只做只读查询，不做临时写入）
- 提交：`annotation_sheet_C.csv`、`round1/annotation_sheet_C_round1.csv`

## 做法

1. 先按手册 §1.2 把每条边分成 DATA / CONTROL / MIXED。
2. CONTROL 边只有在"能清楚说出改哪一格、为什么行集合会变"时才判 POSITIVE。
3. 任何依赖派生值（如 bucket 依赖 count）的边，试标时一律 UNKNOWN：我只能看到派生结果，不能直接看到源头。
4. 明显无关的列（源表不在 FROM 中、列名不在 SQL 中）判 NEGATIVE。

## 疑难

- **`synth-case-012` / `synth-case-014` 的 bucket**：bucket 在每个分组里恒为 `'pos'`，只有"少一行/多一行"才会改变多重集。这属于行数效应，我试标时判 UNKNOWN，校准后接受 POSITIVE（诚实说：我没被完全说服，最终仍保留 2 条 UNKNOWN）。
- **`synth-case-006` 的 bucket**：max(capacity)=38，把一行改成负数不会让 max 变负，因此 bucket 恒定 —— 这条我判 NEGATIVE。
- **`validation-00043` stadium.capacity**：SQLite 在文本列与数值列比较时的类型规则我没把握，因此判 NEGATIVE；A 坚持 POSITIVE，B 判 UNKNOWN，这条进入仲裁。
- **`validation-00004`**：空过滤导致聚合恒 NULL，我试标时判 UNKNOWN；校准后保持 UNKNOWN。
- **`synth-case-008` 的 bucket←average**：换一个被选中的行，它的 capacity 仍然为正，bucket 不变 → NEGATIVE。
- **`validation-00095` / `validation-00133`**：`LIMIT 1` 下排序键进入 CONTROL，我接受为 POSITIVE，但 confidence 记 2。

## 定义问题（建议）

1. **NEGATIVE 的门槛**：手册说"仅在有把握时使用"，但没有说明"把握"是指 SQL 结构可证，还是指观测不到。我按"结构可证"执行。
2. **UNKNOWN 的评测处理**：`score_confirmation.py` 把预测落在 UNKNOWN 上的边直接忽略，这会抬高 precision。建议在报告里单列这一栏（本次已单列：fixed 4 条、literal 0 条、union 4 条）。
3. **`ORDER BY` + `LIMIT`**：手册只说明了"仅改变行顺序不算影响"，建议补一句"有 LIMIT 时排序键属于 CONTROL"。
