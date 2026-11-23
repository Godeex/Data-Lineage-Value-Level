# 标注笔记 — 标注者 C（保守派 / 手册字面派）

- 角色：保守派（手册字面派）标注者。独立完成 30 条 query 的盲标与对照，按 `ANNOTATION.md` 流程执行。
- 日期：2026-11-17
- 耗时：约 80 分钟
- 提交文件：`round1/annotation_C_round1.csv`、`annotation_C.csv`

## 策略

1. 严格按 §4 顺序：先用空白表盲标，再对照机器建议。
2. 严格套用 §5 三态细则：空结果、LIMIT、CASE 分支未触发一律 UNKNOWN；只有能明确说出机理的才 POSITIVE。
3. 不主动做穷举探针，只跑少量 `SELECT count(*)` 确认结果是否为空。

## 疑难

- **`validation-00048` / `validation-00487` / `synth-cte-016` / `synth-case-018`**：LIMIT 1 只有一行可观测，未选中行无法验证，首轮全标 UNKNOWN（confidence low）。
- **`synth-case-007` bucket**：需要极端扰动才能触发 CASE 分支，按"未触发分支不可观测"标 UNKNOWN，校准后接受极端值可触发，改 POSITIVE。
- **`synth-case-005` bucket**：我一开始判 NEGATIVE —— 每个组的 `count(*)` 都 ≥1，`bucket` 恒为 `'pos'`。校准后接受"单成员组消失会让 bucket 行消失，行数变化即多重集变化"，改 POSITIVE。
- **`synth-case-018` bucket ← pet_age**：校准后仍坚持 UNKNOWN。D 上所有权重都是正的，我承认很可能等于 NEGATIVE，但按 THEORY §6"只有参考语义完整计算才允许 NEGATIVE"，我不敢断言。
- **`validation-00031` / `validation-00174` / `synth-cte-004`**：D 上不可观测，全部 UNKNOWN（与 B 一致）。

## 定义问题（建议改手册）

1. §5 说"空结果 → 没有输出值可被影响"，但又说"若无法判断结构依赖，标 UNKNOWN"。这两句对 `synth-cte-004` 这种"过滤为空、聚合恒 NULL"的情形给出相反指引。建议直接规定：**聚合在空集上仍有一行输出，列依赖不可观测 → UNKNOWN**。
2. §6 说"整条 query 没有边时加一行 NONE"。建议再补一行说明：**NONE 与"全部 UNKNOWN"不同**，前者是已证明无边（如整表 `count(*)`），后者是证据不足。
3. 建议在 §7 明确 κ 的计算口径（缺席的行算不算一票），本次我按"缺席 = 未表态"理解，脚本按 union + ABSENT 处理。

## 自评

- 强项：三态边界守得住，很少把"没看到"写成 POSITIVE/NEGATIVE。
- 弱项：对 LIMIT/CASE 过度保守，导致 3 条真实边在首轮被压成 UNKNOWN；对 GROUP BY 的行数效应不敏感（`synth-case-005`）。
- 条数：首轮 96 条判定，终稿 96 条。
