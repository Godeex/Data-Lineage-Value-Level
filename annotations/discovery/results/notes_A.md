# 标注笔记 — 标注者 A（语义派）

- 角色：语义派标注者。独立完成 30 条 query 的 Phase A/B 盲标与对照，按 `ANNOTATION.md` 流程执行。
- 日期：2026-11-17
- 耗时：约 95 分钟（30 条 SQL 通读 + 8 个库 schema/样例 + 约 40 次 `SELECT` 抽查）
- 提交文件：`round1/annotation_A_round1.csv`（首轮）、`annotation_A.csv`（校准后终稿）

## 策略

1. 先只看 `sql` 与 `inspect_db.py` 的 schema，不打开 `reference_edges_suggestion`，在空白表上写出边。
2. 对拿不准的过滤/连接键，用 `SELECT` 抽查边界（例如 `weight>10` 有几行的 weight 落在 10/11）。
3. 打开机器建议逐条对照；与机器不一致的写理由。
4. 判断依据是"语义上这条列是否影响该输出列"，数据只用作佐证 —— 这一取向在校准前对"D 上不可观测"的边偏 POSITIVE。

## 疑难

- **实例级 vs 语义级**：`validation-00031`、`validation-00174`、`synth-cte-004` 三条，语义上 join 键/过滤列显然影响输出，但在匿名化后的 D 上（REAL 与 TEXT 连接死掉、`country='France'` 无匹配）根本观测不到。首轮我按语义判 POSITIVE；校准后接受"实例级不可观测 → UNKNOWN"，但语义结论仍写在 note 里。
- **GROUP BY 键的传导**：`validation-00033` 里 `singer_in_concert.concert_id` 只通过"单成员组消失"影响 `concert_name/theme`，一开始我认为太间接，漏了 `theme` 那条；重新推演多重集行数后才补上。
- **行数变化算不算多重集变化**：`synth-case-005` 的 `bucket` 恒为 `'pos'`，只有"整组消失导致行数变少"才能改变多重集。首轮我漏了 `count(*)`，校准后补。
- **LIMIT**：`validation-00048`/`00487`/`synth-cte-016` 只能观测被选中行，未选中行的扰动不可见，confidence 一律压到 medium。

## 定义问题（建议改手册）

1. §1 写"多重集发生变化"，但没明说**行数变化**属于变化。建议补一句：行数属于多重集的一部分，组消失/新增即改变输出。
2. `CELL_VALUE` 写"换成同类型另一个值"，没说是否可以取极端值。`synth-case-007` 的 `bucket` 只有把一格压到 `-1e6` 才能翻转；若限定"邻近值"，这条边就变成 UNKNOWN。建议明确扰动值域。
3. UNKNOWN 与 NEGATIVE 的边界：`validation-00262` 的 `ORDER BY`（无 LIMIT）可以**证明**输出多重集不变，属于 NEGATIVE；而空过滤导致的常量聚合只是"在 D 上看不到"，属于 UNKNOWN。建议在 §5 加这两类判据。

## 自评

- 强项：投影/过滤类边稳定；对语义路径敏感。
- 弱项：首轮对"实例级不可观测"过度自信；对 GROUP BY 行数效应不敏感。
- 条数：首轮 94 条判定，终稿 96 条（补 2 条漏标的边）。
