# 仲裁记录（第三人裁决）

裁决原则（对齐 `ANNOTATION.md` §2 与 `THEORY.md` §3/§6）：

1. 有可复现的单格扰动见证 → `POSITIVE`；
2. 能一句话证明"任何允许的扰动都不改变输出"（结构不变量）→ `NEGATIVE`；
3. 路径存在但本实例不可观测（类型不一致、字面量过滤为空、合取条件互相遮挡）→ `UNKNOWN`；
4. 仍无法裁决 → `UNKNOWN`。

正式标注的三方判定中，只有 1 条边没有形成多数（`disputed_edges.csv`）。

## 1. 进入仲裁的边

| qid | 边 | A | B | C | 最终 | 理由 |
|---|---|---|---|---|---|---|
| validation-00043 | count(*) ← stadium.capacity | POSITIVE | UNKNOWN | NEGATIVE | **UNKNOWN** | 子查询确实按 capacity 选 id（A 的语义判断成立）；但 `concert.stadium_id` 为 TEXT、`stadium.stadium_id` 为 REAL，单格改 capacity 在实例上未观测到变化（B）。C 认为文本/数值比较规则下不可能命中，但该结论依赖对 SQLite 亲和规则的完整枚举，无法一句话证明。按"路径存在但被类型不一致遮蔽"判 UNKNOWN。 |

## 2. 少数意见（已形成多数，但记录在案）

| qid | 边 | 多数 | 少数 | 说明 |
|---|---|---|---|---|
| synth-case-012 | bucket ← concert.concert_id | POSITIVE（A/B） | UNKNOWN（C） | C 认为 bucket 只随派生 count 变化，未直接看到值变化；A/B 给出"单成员组消失→行数 7→6"的见证。采纳见证。 |
| synth-case-014 | bucket ← concert.stadium_id | POSITIVE（A/B） | UNKNOWN（C） | 同上：count 0→1 使 bucket 由 `nonpos` 变 `pos`。采纳见证。 |

## 3. 对 gold 的影响

- 492 条候选边：`POSITIVE 145` / `NEGATIVE 313` / `UNKNOWN 34`。
- `gold_final.jsonl` = `gold_majority.jsonl`（491 条）+ 仲裁 1 条（UNKNOWN）。
- 34 条 UNKNOWN 全部是"路径存在但本实例不可观测"：
  - 空字面量过滤（`validation-00004` 3 条、`validation-00505` 6 条、`validation-00635` 2 条）；
  - 合取条件遮挡（`validation-00053` 6 条）；
  - 子查询为空导致 join 键不可观测（`validation-00061` 8 条、`validation-00063` 3 条）；
  - 类型不一致（`validation-00043` 2 条、`synth-case-014` 4 条）。
- 这些边在 `score_confirmation.py` 中不计入 P/R；预测落在其上的数量单列在 `analysis_summary.md` §3（fixed 4、literal 0、union 4）。
