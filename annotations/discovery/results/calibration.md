# 校准记录（5 条联合校准，ANNOTATION.md §7）

首轮 κ（`round1/kappa_report_round1.json`）：A–B 0.219、A–C 0.219、B–C 0.897，均值 0.445，低于 0.6 的重标阈值。
按 §7 先做 **5 条联合校准**，再各自重标（终稿 `annotation_*.csv`，首轮留档在 `round1/`）。

> 注意：首轮 κ 低并不是"边判错"，而是三类系统性口径差异集中在少数边上：96 条边里 87 条是 POSITIVE，`p_e≈0.89`，8–10 条分歧就足以把 κ 压到 0.2 附近（高患病率下的 κ 悖论）。校准的目标是统一口径，不是拉高数字。

## 校准的 5 条（每人都要给出立场）

### 1. `validation-00031` / `validation-00174` / `synth-cte-004`：D 上不可观测怎么办？
- A：语义上 join 键/过滤列必然影响输出 → POSITIVE。
- B/C：D 上单格扰动产生不了见证（REAL vs TEXT 连接死掉、`country='France'` 无匹配）→ UNKNOWN。
- **决议**：采用实例级定义，判 **UNKNOWN**；note 里保留"语义上成立"。
- 影响 7 条边（00031×3、00174×1、cte-004×3）。

### 2. `synth-case-005`：`bucket` 恒为 `'pos'`，改 `country` 算不算？
- A/B：单成员组消失 → 输出行数减少 → 多重集变化 → POSITIVE。
- C：值没变，不算。
- **决议**：多重集包含行数，**POSITIVE**（C 改判）。

### 3. `synth-case-007`：`bucket ← capacity` 需要极端值
- A：把一格压到 `-1e6`，`avg<0`，bucket 翻转 → POSITIVE。
- B/C：只试了 ±1/NULL，判 UNKNOWN。
- **决议**：`CELL_VALUE` 允许任意同类型值（含极端值），**POSITIVE**（B/C 改判），confidence=medium。

### 4. `synth-case-018`：`bucket ← pet_age` 是否 NEGATIVE？
- A/B：D 上所有 `weight>0`，无论选中哪一行 bucket 恒 `'pos'` → NEGATIVE。
- C：无法证明"所有可能扰动"都不变 → UNKNOWN。
- **决议**：未能完全一致，**保留分歧**，仲裁判 **NEGATIVE**（理由：bucket 是 `weight` 符号的函数，与"哪一行被选中"无关；D 上权重全正）。C 的 UNKNOWN 作为弃权记录在 `arbitration.md`。

### 5. 谁的见证算数？
- B 首轮漏了 `validation-00174 car_makers.Country`（需要把文本改成 `'5'` 才会被 NUMERIC 亲和命中）。
- **决议**：一方给出的可复现探针，其他两人接受；A/C 保留 POSITIVE，B 仍不列该边（他坚持"只有自己复现过才写"），该差异保留为 A–B 的一条缺席分歧。

## 重标结果

| 指标 | 首轮 | 终稿 |
|---|---|---|
| A–B 二分类 κ（union） | 0.219 | **0.942** |
| A–C 二分类 κ（union） | 0.219 | **1.000** |
| B–C 二分类 κ（union） | 0.897 | **0.942** |
| 三分类 κ（共同边，A–C / B–C） | 0.319 / 0.895 | **0.940 / 0.940** |
| 均值（二分类） | 0.445 | **0.961** |
| 剩余分歧 | 13 处（10 条判定分歧 + 3 条缺席） | **2 处**（1 缺席 + 1 NEG/UNKNOWN） |

终稿达到 §7 的门槛（≥0.7）。

## 口径固化（已写入报告，建议下版手册采纳）

1. 输出是行多重集，**行数变化 = 多重集变化**。
2. `CELL_VALUE` 的候选值域必须显式声明（列内值、SQL 字面量、±1、极端哨兵、NULL），否则 NEGATIVE 不可证。
3. `UNKNOWN`（D 上未观测到）≠ `NEGATIVE`（可证不变）。可证不变的两类典型：`ORDER BY` 无 `LIMIT`、整表 `COUNT`。
