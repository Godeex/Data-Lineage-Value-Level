# 标注笔记 — 标注者 B（实例派）

- 角色：实例派标注者
- 日期：2026-11-18
- 工时：约 7.5 小时（42 条 SQL；对每条 query 做 3–8 次只读 SELECT 或临时 UPDATE+回滚）
- 提交：`annotation_sheet_B.csv`、`round1/annotation_sheet_B_round1.csv`

## 做法

1. 对每条 query 先跑基线，记下输出列、行数、关键列的类型（`typeof`）。
2. 对每条候选边做单格扰动：在事务里改一个单元格，重跑 query，比较输出多重集，然后回滚。
3. 只追求"可观测"：有变化 → POSITIVE；没有变化 → 先判断是"路径不存在"（NEGATIVE）还是"路径被挡住"（UNKNOWN）。
4. 判 NEGATIVE 的三类：列未出现在 SQL 中；只有 `ORDER BY` 没有 `LIMIT`；输出列是常量（改任何一格都不变）。

## 疑难

- **`validation-00043` / `synth-case-014`**：`concert.stadium_id` 是 TEXT、`stadium.stadium_id` 是 REAL。把 concert 侧改成 `'21'` 能让 `count(*)` 从 0 变 1（POSITIVE）；但改 stadium 的 capacity/id 观察不到变化，我判 UNKNOWN。
- **`validation-00053`**：无论改哪一列，`count(*)` 都是 0（两个合取条件）。判 UNKNOWN，不判 NEGATIVE，因为单看 SQL 语义这些列显然会影响结果。
- **`validation-00061/00063`**：子查询因为 `pettype='cat'` 无匹配而为空，所以 join 键全部观测不到；改 `pettype='cat'` 本身可以，因此只有 pettype 是 POSITIVE。
- **`validation-00505` / `validation-00635`**：右侧因为字面量过滤为空，join 键改不动结果；只有过滤列本身有见证。
- **`validation-00016` / `synth-cte-014` / `synth-case-006` 的 `average`**：SQLite 在 `max()` 聚合下，裸列取自极值所在行，所以改 `capacity` 会连带改变 `average`。这是个反直觉的 DATA 边，我记 confidence 2。
- **`synth-case-016`**：`count(*)` 从 17 出发，单格扰动不可能让它变 0，所以 bucket 恒为 `'pos'` → NEGATIVE。

## 定义问题（建议）

1. 手册的 `DATABASE` 边界里没有提"类型被改写"这种情况；匿名化后 REAL/TEXT 混用会让 join 失败，建议在数据说明里写清楚。
2. `evidence_type` 的 INDIRECT 定义不清。我把"只通过行数/派生值影响输出"（如 bucket 随 count 变化）记作 INDIRECT，建议在手册里给出定义。
3. 建议明确：**同一列在同一 query 里既有 DATA 又有 CONTROL（如 GROUP BY 键同时被投影）记 MIXED**。
