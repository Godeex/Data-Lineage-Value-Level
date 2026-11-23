# 标注笔记 — 标注者 A（语义派）

- 角色：语义派标注者
- 日期：2026-11-18
- 工时：约 6.5 小时（42 条 SQL、492 条候选边；含 8 次针对性 SELECT 复核）
- 提交：`annotation_sheet_A.csv`（正式）、`round1/annotation_sheet_A_round1.csv`（校准前试标）

## 做法

1. 先通读 42 条 SQL 与 `schemas/`，按 DATA / CONTROL 给每条候选边定性，再打开自己的表格填。
2. 对 DATA 边（投影列、聚合输入、CASE 操作数）直接判 POSITIVE。
3. 对 CONTROL 边（WHERE / JOIN / GROUP BY / ORDER BY+LIMIT / CASE 分支）先看它是否能改变行集合或行数；能则 POSITIVE。
4. 我倾向于按 SQL 的语义直觉判断：只要"改这一列原则上可能影响输出"，就给 POSITIVE，即使实例上没直接看到变化。

## 疑难

- **`validation-00004`**：`WHERE country='France'`，实例上没有 France 行，`avg/min/max` 恒为 NULL。语义上 age 是聚合输入，但改 age 看不到任何变化。试标时我给了 POSITIVE，校准后接受 UNKNOWN。
- **`validation-00053`**：`sex='F' AND pettype='dog'` 两个合取条件同时不成立，单格扰动只能满足一个。试标时我给 6 条全 POSITIVE，校准后改 UNKNOWN。
- **`synth-case-006`**：`bucket = CASE WHEN max(capacity)>0`。我以为把容量改成负数就能翻转，但 max 是 38，改一行不会让 max ≤0。校准后接受 NEGATIVE（本实例上 bucket 恒为 'pos'）。
- **`validation-00043`**：`count(*) WHERE stadium_id = (子查询)`，两侧类型不一致（TEXT vs REAL）。我坚持"capacity 决定子查询返回哪个 id"是真实语义影响，因此保留了 POSITIVE；这条进入仲裁。
- **LIMIT 查询**（`validation-00006/00018/00067/00155/00269`、`synth-cte-006`）：排序键影响被选中的那一行，我给 POSITIVE，但 confidence 记 2。
- **`synth-case-012` 的 bucket**：bucket 只随分组行数变化，属于间接影响，我按"行数变化即多重集变化"判 POSITIVE。

## 定义问题（建议）

1. 手册没有说明"实例上被另一个列的数据状态挡住"时该判 UNKNOWN 还是 NEGATIVE。建议明确：**路径存在但本实例不可观测 → UNKNOWN；路径不存在或输出对该列不变 → NEGATIVE**。
2. `CASE` 派生的输出（bucket）常常只依赖一个聚合结果，建议在手册里给一个"常量输出"的示例，避免把 bucket 当成所有列的下游。
3. `ORDER BY` 的说明很清楚（无 LIMIT 不算影响），但 `LIMIT` 情形建议补一句：排序键只影响"被选中的行"，属于 CONTROL。
