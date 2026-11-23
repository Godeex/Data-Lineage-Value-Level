# 仲裁记录（第三人裁决 + 三人讨论）

裁决原则（对齐 `THEORY.md` §3/§6 与 `ANNOTATION.md` §8）：

1. 有可复现的单格扰动见证 → `POSITIVE`，并记录见证（哪张表、哪一行、改成什么）。
2. 能证明"任何扰动都不改变输出"（结构不变量）→ `NEGATIVE`。
3. 只在给定实例 `D` 上观测不到（匿名化导致的空过滤、类型错配、LIMIT/CASE 遮蔽）→ `UNKNOWN`，不许强行二值化。
4. 无法裁决 → `UNKNOWN`。

终稿 gold：`gold_edges.jsonl`（POSITIVE 87 / NEGATIVE 2 / UNKNOWN 7，共 96 条，30 条 query）。

## 分歧逐条裁决

| # | qid | 边 | A | B | C | 最终 | 理由 |
|---|---|---|---|---|---|---|---|
| 1 | validation-00031 | name ← stadium.stadium_id | POSITIVE | UNKNOWN | UNKNOWN | **UNKNOWN** | D 上 `stadium.Stadium_ID`(REAL) 与 `concert.Stadium_ID`(TEXT) 恒不匹配，任何单格扰动都无法让右表非空；语义上该边成立，属于实例遮蔽 |
| 2 | validation-00031 | name ← concert.stadium_id | POSITIVE | UNKNOWN | UNKNOWN | **UNKNOWN** | 要同时满足"id 匹配"和 `Year=2014`，单格扰动在 D 上做不到 |
| 3 | validation-00031 | name ← concert.year | POSITIVE | UNKNOWN | UNKNOWN | **UNKNOWN** | 即使把 Year 改成 `'2014'`，连接仍因类型错配为空，右表不变 |
| 4 | validation-00174 | countryname ← countries.countryid | POSITIVE | UNKNOWN | UNKNOWN | **UNKNOWN** | 同类遮蔽：REAL id 不会等于 TEXT 的 `v*_*`；语义上改 id 会改变 EXCEPT 右侧 |
| 5 | synth-cte-004 | avg(age) ← singer.age | POSITIVE | UNKNOWN | UNKNOWN | **UNKNOWN** | `country='France'` 零匹配，聚合恒 NULL；改 Age 恒无效果 |
| 6 | synth-cte-004 | min(age) ← singer.age | POSITIVE | UNKNOWN | UNKNOWN | **UNKNOWN** | 同上 |
| 7 | synth-cte-004 | max(age) ← singer.age | POSITIVE | UNKNOWN | UNKNOWN | **UNKNOWN** | 同上 |
| 8 | synth-case-007 | bucket ← stadium.capacity | POSITIVE | UNKNOWN | UNKNOWN | **POSITIVE** | 见证：`capacity 17 → -1e6` 使 `avg(capacity)<0`，bucket 由 `pos` 变 `nonpos`；`CELL_VALUE` 未限制值域，允许极端值 |
| 9 | synth-case-005 | bucket ← singer.country | POSITIVE | POSITIVE | NEGATIVE | **POSITIVE** | 见证：singer 有 25 个组、每组 1 人；把某组唯一成员的 country 改成另一组的值，输出行数 25→24，bucket 行消失；行数属于多重集 |
| 10 | synth-case-018 | bucket ← pets.pet_age | NEGATIVE | NEGATIVE | UNKNOWN | **NEGATIVE** | `bucket = CASE WHEN weight>0`，只依赖 `weight` 的符号；D 上 `min(weight)=1>0`，无论选中哪一行都是 `'pos'`。C 弃权（见下） |
| 11 | validation-00033 | theme ← singer_in_concert.concert_id | 缺席 | POSITIVE | POSITIVE | **POSITIVE** | 见证：改连接键后某单成员组消失，`theme` 行消失；行数变化即可观测 |
| 12 | synth-case-005 | count(*) ← singer.country | 缺席 | POSITIVE | POSITIVE | **POSITIVE** | 见证：`v9_1 → v5_0` 合并两组，组计数 `(2,1,…)` 变为 `(3,…)` |
| 13 | validation-00174 | countryname ← car_makers.country | POSITIVE | 缺席 | POSITIVE | **POSITIVE** | 见证：`Country 'v3_0' → '5'`，NUMERIC 亲和把它强制成 5，与 `countries.CountryId=5` 匹配，右侧非空、输出 25→23 行；B 未复现故缺席，按"见证优先"采信 |

## 无法完全裁决的两处（保留为弃权）

1. **第 10 条（`bucket ← pet_age`）**：C 的理由是"THEORY §6 要求 NEGATIVE 只在参考语义完整计算后给出，我无法穷举所有扰动"。裁决判 `NEGATIVE`，因为该列对输出的影响路径已经闭合（bucket 只依赖 weight 符号，与选行无关），属于**结构可证**，不需要穷举。C 的 UNKNOWN 记入 `annotation_C.csv`，three-class κ 因此为 0.94 而非 1.0。
2. **第 13 条**：B 坚持"只有自己复现的见证才写"，缺席该边。裁决采信 A/C 的可复现探针；A–B 的二分类 κ 因此为 0.942（union 口径）。

## 对 gold 的影响

- 机器 reference 76 条 → gold 96 条：**新增 11 条 POSITIVE、7 条 UNKNOWN、2 条 NEGATIVE**。
- 机器 reference 没有一条被推翻成 NEGATIVE（precision 76/76 = 100%），但漏报 11 条（recall 76/87 = 87.4%，按 POSITIVE 计）。
- 7 条 UNKNOWN 全部由匿名化造成（REAL/TEXT 类型错配 4 条、空过滤 3 条），不是标注者犹豫。
