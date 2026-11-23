# 标注笔记 — 标注者 B（实例派 / 探针派）

- 角色：实例派（探针派）标注者。独立完成 30 条 query 的盲标与对照，按 `ANNOTATION.md` 流程执行。
- 日期：2026-11-17
- 耗时：约 120 分钟（其中过半花在逐列单格 UPDATE 探针与回滚）
- 提交文件：`round1/annotation_B_round1.csv`、`annotation_B.csv`

## 策略

1. 只看 SQL 与 schema，先写一份预期边（不打开机器建议）。
2. 对每条 query 在 `dbs/<db_id>.sqlite` 上跑基线，记录输出列与行数。
3. 对 SQL 引用到的每个基表列，逐行做单格扰动（`+1 / -1 / 0 / NULL / SQL 字面量`），在 `SAVEPOINT` 内执行后回滚，比较输出列多重集是否变化。
4. 有见证 → POSITIVE；无见证且能从 SQL 结构证明不变 → NEGATIVE；其余 → UNKNOWN。
5. 最后与 `reference_edges_suggestion` 对照，机器漏掉的边标注 `machine missed`。

## 疑难（探针视角）

- **匿名化把类型改坏了**：`car_1.car_makers.Country` 是 TEXT、`countries.CountryId` 是 REAL；`concert_singer.concert.Stadium_ID` 是 TEXT、`stadium.Stadium_ID` 是 REAL。连接在 D 上恒不匹配，导致 `validation-00174` / `validation-00031` 的 join 键完全观测不到。
- **空过滤让聚合变常量**：`synth-cte-004` 的 `country='France'` 无匹配行，`avg/min/max` 恒为 NULL，`Age` 怎么改都不变。按实例级这是"没见证"，我没有据此判 NEGATIVE（THEORY §6 要求 NEGATIVE 只在参考语义完整时给）。
- **只有数字形态的字符串能触发类型强制**：`car_makers.Country` 改成 `'v9_0_p'` 不动，改成 `'5'` 才通过 NUMERIC 亲和命中 `CountryId=5`。这类见证依赖匿名化后的类型错配，我标 POSITIVE/medium 并在 note 写清。
- **LIMIT/CASE 只能看到一行**：`validation-00048`、`validation-00487`、`synth-case-007/018` 的未选中行不可观测。
- **极端值**：`synth-case-007` 的 `bucket` 需要把 `capacity` 压到 `-1e6` 才能让 `avg<0`。我首轮只试了 ±1 与 NULL，漏了这条，校准后接受 A 的见证。

## 定义问题（建议改手册）

1. **候选值域没有定义**：`CELL_VALUE` 的"另一个值"在实际枚举里必须有边界（预算 B、值域），否则 NEGATIVE 永远不可证。建议手册给出候选值生成规则（列内已有值、SQL 字面量、±1、极端哨兵、NULL）。
2. **类型亲和**：匿名化后的 REAL/TEXT 错配会制造"通过类型强制才成立的边"。建议记录实例 schema 是否被改动，或在 gold 里单列一类 `coercion-only` 边。
3. **NEGATIVE 的可证性**：建议区分"结构不变"（可证 NEGATIVE）与"未观测到"（UNKNOWN），并把判据写进 §5。

## 与机器的差异

- 我认为机器 reference 是"只报见证"的 L_obs，因此**没有假阳性**，但**漏报明显**：`WHERE`/`GROUP BY`/`ORDER BY LIMIT` 上的列几乎全漏（`validation-00020`、`synth-cte-018`、`synth-case-010`、`synth-cte-004`、`synth-case-005` 等）。
- 我自己的漏报 1 条：`validation-00174 car_makers.Country`（首轮没想到用数字字符串探测，校准后由 A 的见证补上）。
