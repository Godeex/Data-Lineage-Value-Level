# 确认集结果：42 条 query、492 条候选边

> 目的：在**未参与 literal-aware probing 设计**的 42 条模板上，用三人独立标注的 gold 检验 fixed / literal / union 三种冻结预测。
> 标注完成日期：2026-11-18。所有数字可用 `compute_agreement.py`、`score_confirmation.py`、`tools/analyze_results.py` 复现。

## 1. 标注质量

| 指标 | 试标（校准前） | 正式 |
|---|---|---|
| A–B 二分类 κ | 0.832 | **0.995** |
| A–C 二分类 κ | 0.803 | **0.985** |
| B–C 二分类 κ | 0.970 | **0.990** |
| 均值 | 0.868 | **0.990** |
| 三分类 κ（A–B / A–C / B–C） | 0.847 / 0.823 / 0.976 | 0.996 / 0.988 / 0.988 |
| 未形成多数的边 | 0 | **1**（已仲裁） |

- 三人一致率 0.994–0.998（492 条），达到手册的 κ ≥ 0.80 目标。
- 试标 → 正式：5 条联合校准（`calibration.md`）统一了"空过滤 / 合取条件 / 常量输出 / 派生计数 / 类型不一致"五类边界。
- 仲裁：`validation-00043 count(*) ← stadium.capacity` 判 UNKNOWN（`arbitration.md`）。

## 2. gold 构成

`gold_final.jsonl`：**492 条 = POSITIVE 145 / NEGATIVE 313 / UNKNOWN 34**。

| category | queries | POS | NEG | UNK |
|---|---|---|---|---|
| aggregate | 10 | 20 | 45 | 11 |
| case | 6 | 25 | 127 | 4 |
| cte | 5 | 14 | 76 | 0 |
| join | 11 | 54 | 31 | 19 |
| projection | 10 | 32 | 34 | 0 |

34 条 UNKNOWN 均来自"路径存在但本实例不可观测"：空字面量过滤 11、合取条件 6、子查询为空 11、类型不一致 6（明细见 `arbitration.md` §3）。

## 3. 预测对比（`confirmation_results.json`）

| method | micro TP | FP | FN | P | R | F1 | macro F1 |
|---|---|---|---|---|---|---|---|
| fixed | 95 | 4 | 50 | 0.960 | 0.655 | 0.779 | 0.704 |
| literal | 92 | 0 | 53 | **1.000** | 0.634 | 0.776 | 0.723 |
| union | 117 | 4 | 28 | 0.967 | **0.807** | **0.880** | **0.819** |

paired bootstrap（按 query，10,000 次）：

| 对比 | Δmacro-F1 | 95% CI | p（双侧） |
|---|---|---|---|
| literal − fixed | +0.019 | [−0.061, +0.103] | 0.653 |
| union − fixed | **+0.115** | [+0.059, +0.183] | **<0.001** |

**结论**：literal 单独使用在本集上**没有显著优于** fixed（精度更高、召回更低，F1 基本持平）；**union 显著优于 fixed**。

## 4. 分类型结果（`analysis_summary.md`）

| category | fixed F1 | literal F1 | union F1 |
|---|---|---|---|
| aggregate | 0.750 | 0.824 | **0.857** |
| case | 0.792 | 0.684 | **0.840** |
| cte | 0.880 | 0.833 | **0.963** |
| join | 0.729 | 0.773 | **0.851** |
| projection | 0.815 | 0.792 | **0.933** |

- literal 在 `case` 上明显弱：`bucket` 边依赖分组是否为空/单成员，budget=3 行常常取不到那个关键行。
- fixed 在 `case` 上有 4 个假阳性（`bucket ← average/capacity/concert_name/theme`），属于"把 CASE 的所有上游列都当成控制列"的过度近似。

## 5. 两个方法都漏掉的 POSITIVE（28 条）

| category | missed by both |
|---|---|
| join | 14 |
| aggregate | 5 |
| case | 4 |
| projection | 4 |
| cte | 1 |
| **total** | **28** |

典型原因：

1. **budget 只覆盖前 3 行**：`LIMIT` 查询的选中行不在前 3 行时，投影列与排序键都会漏（如 `validation-00067` 的 `pettype ← pettype`、`weight ← weight`）。
2. **分组键的间接边**：`count(*) ← GROUP BY 键`、聚合列 `← GROUP BY 键`（`validation-00010/00049/00071`、`synth-cte-010`）。
3. **join 键**：`validation-00095/00353/00399/00459` 的多个 join 键，静态解析与 3 行扰动都没覆盖。
4. **字面量过滤列**：`validation-00505/00635` 中 `ship.location`、`cartoon.written_by` 对 EXCEPT 左右两侧的影响。

## 6. 需要说明的评测口径

- `score_confirmation.py` 只把"预测 ∩ gold POSITIVE"计 TP、"预测 ∩ gold NEGATIVE"计 FP；**预测落在 UNKNOWN 上的边被忽略**（不计 TP/FP/FN）。本次：fixed 4 条、literal 0 条、union 4 条。
- 若把 UNKNOWN 当作 NEGATIVE 重新计分（`analysis_summary.md` §4）：

| method | P | R | F1 |
|---|---|---|---|
| fixed | 0.922 | 0.655 | 0.766 |
| literal | 1.000 | 0.634 | 0.776 |
| union | 0.936 | 0.807 | 0.867 |

结论方向不变，但 fixed 的 precision 会从 0.960 降到 0.922 —— 这是"空过滤 / 类型不一致"类 UNKNOWN 造成的口径差异，报告时应同时给出。

## 7. 边界与局限

1. **42 条模板、一模板一 query**：结果按 paired query-level 统计报告，不外推到所有 SQL 形态。
2. **实例被匿名化**：多处 REAL/TEXT 混用、字面量过滤为空，产生 34 条 UNKNOWN；这是"实例级"定义的直接后果，不是标注者犹豫。
3. **不能确认 evolution**：本集只用于 literal vs fixed（见包内 scope 说明）。
4. **一致性 ≠ 正确性**：κ 很高且只有 1 条仲裁，说明三人对同一手册的理解一致；但本集没有第二套独立 gold 交叉验证。
5. **标注者只有 3 人**，且 492 条边中 34 条弃权；建议在论文附录给出 UNKNOWN 清单与本文第 6 节的口径敏感性。

## 8. 复现

```bash
cd annotations/confirmation/package
python check_sheet.py --sheet annotation_sheet_A.csv
python compute_agreement.py --a annotation_sheet_A.csv --b annotation_sheet_B.csv \
    --c annotation_sheet_C.csv
python tools/make_gold_final.py                 # 合并多数 + 仲裁
python score_confirmation.py --gold gold_final.jsonl
python tools/analyze_results.py                 # 分类别 + 敏感性
```
