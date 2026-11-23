# 理论定义 v1：Instance-Level Value Lineage under Incomplete Execution Evidence

> 本文件回应 P0：先把“什么叫值级血缘、什么叫 oracle 观测成功”定义清楚。第一版论文只主张**给定数据库实例 + 指定扰动族下的实例级反事实影响**，不主张普遍语义依赖。

## 1. 基本对象

- `D`：一个数据库实例（表、列、行、值）。
- `Q`：一条 SQL 查询（或展开后的管道脚本）。
- `Q(D)`：在实例 D 上执行 Q 得到的输出表；我们把它看成**多重集**（行序不算）。
- `O`：输出列集合；`o ∈ O` 是一个输出列。
- `c`：源列，记作 `(table t, column c)`。
- `P`：扰动族集合（见 §2）。
- `P_c`：只作用于列 c 的扰动子集。

## 2. 五类扰动族

| 族               | 操作                                 | 是否可归因到列      |
| --------------- | ---------------------------------- | ------------ |
| `CELL_VALUE`    | 把某行某列的值换成同类型另一个值（数值 +100，文本加 `_p`） | 是            |
| `VALUE_TO_NULL` | 把某行某列的非 NULL 值置为 NULL              | 是            |
| `NULL_TO_VALUE` | 把某行某列的 NULL 值置为一个默认非 NULL 值        | 是            |
| `ROW_DELETE`    | 删除某一行                              | 否（行级，不归因到单列） |
| `ROW_DUPLICATE` | 复制某一行                              | 否（行级，不归因到单列） |

列级血缘只用前三个**列级扰动族**；后两个用于“行是否影响结果”的辅助分析，不用于列归因。

## 3. 参考语义：`L_sem`

给定 `D, Q, P_col = {CELL_VALUE, VALUE_TO_NULL, NULL_TO_VALUE}`：

> `(o, t, c) ∈ L_sem(D, Q, P_col)` 当且仅当存在一个扰动 `p ∈ P_col`，只改列 c 的某一个单元格，使得输出列 o 的多重集发生变化。

这是**实例级反事实影响**：它问的是“在这个具体数据库实例上，改这个单元格会不会改变这个输出列”。它不代表“对所有可能实例都成立”的普遍语义依赖。

## 4. 预算化 oracle：`L_obs`

实际 oracle 不可能把每列每行都扰动一遍。给定：

- 扰动族子集 `P' ⊆ P_col`
- 每列最多测试 `B` 行（budget）

> `(o, t, c) ∈ L_obs(D, Q, P', B)` 当且仅当在 `P'` 与 `B` 的限制下，存在一个扰动使输出列 o 变化。

默认 `L_obs` 只返回正例；**未观测到 ≠ 不存在**，记为 `UNKNOWN`。

## 5. 覆盖、漏检与精确率

- `coverage = |L_obs ∩ L_sem| / |L_sem|`
- `false_negative_rate = |L_sem \ L_obs| / |L_sem|`
- `precision = |L_obs ∩ L_sem| / |L_obs|`（当 `L_obs` 只使用 `L_sem` 同族扰动时，precision 理论上为 1；实际实现错误会导致 <1）

## 6. Abstention（弃权）

对每条候选边，oracle 输出三态：

- `POSITIVE`：在 `P', B` 下观测到变化
- `UNKNOWN`：在 `P', B` 下未观测到变化（**不是 negative**）
- `NEGATIVE`：只有在参考语义 `L_sem` 被完整计算时才允许输出

Agent 的决策规则：

- `POSITIVE` → 接受该边
- `UNKNOWN` → 不宣称不存在；可选择补扰动/静态辅助/标记未知
- `NEGATIVE` → 仅在 reference 完整时接受

## 7. 可观测性预测（研究问题）

我们想回答：

> 能否在**不跑完整 reference** 的情况下，预测某条 query / 某个扰动族 / 某个 budget 的 `coverage` 会高还是低？

候选预测特征：

- 是否有空结果 / LIMIT / CASE / 聚合 / fan-out
- 源列是否出现在 WHERE / JOIN / GROUP BY / ORDER BY
- 表行数、列基数、NULL 比例
- 扰动族与 query 结构的交互

如果这些特征能预测 coverage，Agent 就可以“按证据质量决定信不信”，而不是盲目接受/拒绝。

## 8. 第一版论文的边界

- **主张**：instance-level counterfactual value lineage under a specified perturbation family。
- **不主张**：universal semantic dependency、所有可能实例、所有 SQL 方言、所有 UDF。
- **外部效度**：Spider 真实库 + dbt/Jinja 宏场景；不外推到任意生产管道。
- **人工标注**：reference 由穷举扰动计算；人工标注用于验证 reference 的语义合理性，而不是替代它。
