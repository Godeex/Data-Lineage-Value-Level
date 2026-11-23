# 5 条联合校准记录（三人）

三人先各自按手册试标（`round1/`，全部 492 条），再就 5 条代表性 query 逐条对齐口径；对齐后进入正式标注（根目录的三份 sheet）。

试标一致性（`round1/agreement_report.json`）：

| 对 | 一致率 | 二分类 κ | 三分类 κ |
|---|---|---|---|
| A–B | 0.925 | 0.832 | 0.847 |
| A–C | 0.913 | 0.803 | 0.823 |
| B–C | 0.988 | 0.970 | 0.976 |
| 均值（二分类） | — | **0.868** | — |

试标已过手册的 0.80 门槛，但 A–C 只有 0.803，且分歧集中在 5 类边界情形。下面 5 条用于统一口径（校准后不再讨论具体边）。

## 1. `validation-00004`：空过滤下的聚合输入
`SELECT avg(age), min(age), max(age) FROM singer WHERE country='France'`
- 实例上 `country='France'` 无匹配行，三个聚合恒为 NULL。
- A：age 是聚合输入，语义上 POSITIVE。B/C：本实例不可观测。
- **决议**：UNKNOWN。理由：过滤集为空是实例数据状态，单格改 age 无法改变输出；但也没有证据说明该列不可能影响，属于"路径存在但被数据状态挡住"。
- 影响 3 条边（avg/min/max ← age）。`country` 三条保留 POSITIVE（改成 'France' 有见证）。

## 2. `validation-00053`：合取过滤
`... WHERE T1.sex='F' AND T3.pettype='dog'`
- 实例上没有同时满足两个条件的行，单格扰动只能满足其中一个。
- **决议**：6 条边全部 UNKNOWN（不判 NEGATIVE）。
- 口径：**"被另一个列的数据状态挡住" → UNKNOWN；"根本没有路径" → NEGATIVE。**

## 3. `synth-case-006`：常量输出
`SELECT max(capacity), CASE WHEN max(capacity)>0 ... FROM stadium`
- A 认为"把 capacity 改成负数就能翻转 bucket"。
- B/C 指出：max 由 25 行中的最大值决定，改一行不会让 max ≤0。
- **决议**：`bucket ← capacity` 判 **NEGATIVE**。同时保留 `average ← capacity` 为 POSITIVE（SQLite 的裸列取自 max 所在行，有见证）。

## 4. `synth-case-012`：派生计数上的 CONTROL
`bucket = CASE WHEN count(*)>0 ...`（按 concert_id 分组）
- C 试标时判 UNKNOWN，认为只能看到派生值。
- A/B 给出见证：某单成员组消失时行数 7→6，bucket 多重集改变。
- **决议**：**POSITIVE**（evidence_type=INDIRECT），confidence=2。C 仍对其中 2 条保留 UNKNOWN（少数意见，见 `arbitration.md`）。

## 5. `validation-00043`：类型不一致的标量子查询
`SELECT count(*) FROM concert WHERE stadium_id = (SELECT stadium_id FROM stadium ORDER BY capacity DESC LIMIT 1)`
- `concert.stadium_id` 是 TEXT、`stadium.stadium_id` 是 REAL。把 concert 侧改成 `'21'` 有见证（0→1）。
- 改 stadium 的 capacity / id：A 认为语义上成立，B 观测不到，C 认为类型规则下不可能。
- **决议**：`concert.stadium_id` POSITIVE；`stadium.capacity` / `stadium.stadium_id` UNKNOWN（其中 capacity 一条未达成一致，进入仲裁）。

## 校准后的正式标注

| 指标 | 试标 | 正式 |
|---|---|---|
| A–B 二分类 κ | 0.832 | **0.995** |
| A–C 二分类 κ | 0.803 | **0.985** |
| B–C 二分类 κ | 0.970 | **0.990** |
| 均值 | 0.868 | **0.990** |
| 三分类 κ（A–B / A–C / B–C） | 0.847 / 0.823 / 0.976 | 0.996 / 0.988 / 0.988 |
| 未达成多数（3 种判定） | 0 | **1**（进入仲裁） |

正式标注见 `agreement_report.json`、`gold_majority.jsonl`、`disputed_edges.csv`。
