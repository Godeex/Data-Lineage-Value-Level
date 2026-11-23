# DATA / CONTROL / MIXED：值级血缘的两种影响

> 回应 comment02 §5：`country → name` 这类边不是“值直接贡献”，而是“控制行是否出现/分组/分支”。  
> 我们用启发式分类对 30 条 gold 的 87 条 POSITIVE 边做了标注，结果：**CONTROL 49（56%）、DATA 29（33%）、MIXED 9（10%）**。  
> 注意：这是**启发式分类**，不是人类逐条标注；论文应标为 exploratory。

---

## 1. 定义

| 类型 | 含义 | 典型来源 |
|---|---|---|
| **DATA** | 源列的值直接参与输出列值的计算 | `SELECT amount*2 AS d`；`SUM(amount)` |
| **CONTROL** | 源列影响输出行是否存在、分组、排序或分支选择，但不直接进入输出值 | `WHERE country='France'`；`GROUP BY country`；`CASE WHEN ...`；`JOIN ON` |
| **MIXED** | 同一源列既进入值计算，又出现在控制子句 | `SELECT country, COUNT(*) ... GROUP BY country` |
| **INDIRECT** | 通过 CTE/子查询/多跳传导，启发式无法直接归到上述两类 | 复杂嵌套 |

这解释了 comment02 的例子：

```sql
SELECT name FROM singer WHERE country = 'France';
```

`country → name` 是 **CONTROL**：它不改变 `name` 的值，但决定哪些行出现。  
按我们的实例级反事实定义，扰动 `country` 改变输出多重集，所以它是合法边；但它与 `amount → doubled` 的 DATA 边不是同一种关系。

---

## 2. 启发式分类结果（87 条 POSITIVE）

| 类型 | 数量 | 占比 |
|---|---|---|
| CONTROL | 49 | 56% |
| DATA | 29 | 33% |
| MIXED | 9 | 10% |

### 按类别

| 类别 | DATA | CONTROL | MIXED |
|---|---|---|---|
| projection | 9 | 6 | 2 |
| join | 8 | **22** | 1 |
| aggregate | 4 | **11** | 1 |
| cte | 5 | 7 | 0 |
| case | 3 | 3 | 5 |

- **join 主要是 CONTROL**（22/31）：join 键决定行匹配，不直接进入输出值。
- **aggregate 也主要是 CONTROL**（11/16）：GROUP BY 键影响分组/行存在。
- **projection 以 DATA 为主**（9/17）。
- **case 以 MIXED 为主**（5/11）：条件列既控制分支，也可能被投影。

---

## 3. 与机器 reference 盲区的关系

机器 reference 漏掉的 11 条 POSITIVE：

| 漏报类型 | 数量 | DATA/CONTROL |
|---|---|---|
| WHERE 过滤列 | 6 | CONTROL |
| CASE 派生输出 | 2 | CONTROL/MIXED |
| GROUP BY 键 | 2 | CONTROL |
| coercion join | 1 | CONTROL |

也就是说：**机器 reference 的盲区几乎全是 CONTROL 边**。  
这解释了为什么 literal probing（改变谓词值）能修复它们，而普通 `CELL_VALUE +100` 不能。

---

## 4. 对论文的意义

1. **值级血缘不是一个单一关系**  
   DATA 与 CONTROL 都是真实影响，但语义不同；论文必须分开报告，不能混成一个 F1。

2. **谓词列盲区不是边角问题**  
   在 30 条 gold 中，CONTROL 边占 56%；忽略 CONTROL 会漏掉大部分血缘。

3. **Literal probing 修复的是 CONTROL 依赖**  
   它通过 SQL 字面量/边界值跨过 WHERE/CASE/GROUP BY 阈值；对 DATA 边的贡献较小。

4. **评测应分型报告**  
   建议表：DATA P/R/F1、CONTROL P/R/F1、MIXED；至少把 CONTROL 单列，避免“投影列 coverage”冒充“血缘 coverage”。

---

## 5. 局限

- **启发式**：用 sqlglot 找 WHERE/HAVING/GROUP BY/ORDER BY/JOIN/CASE 中的列名；列名匹配可能受别名/嵌套影响。
- **不是人类逐条标注**：未计算 κ；应作为 exploratory，后续可让标注者补 `evidence_type`。
- **未区分“行存在性”与“分组/排序/分支”**：CONTROL 内部还可细分，当前只做一级分类。
- **INDIRECT 未细分**：当前启发式把部分多跳边归到 DATA/CONTROL；复杂 CTE 需要人工核。

---

## 6. 下一步

1. 在标注表中增加 `evidence_type ∈ {DATA, CONTROL, MIXED, INDIRECT}`，让下一轮标注者直接填。
2. 论文主表按 DATA/CONTROL 分型报告；至少把 CONTROL 单列。
3. 在 Literal probing 的分析中区分“修复 CONTROL 边”与“修复 DATA 边”的数量。
4. 对 join/aggregate 的 CONTROL 边做专门扰动（key perturbation、row deletion）作为后续工作。

---

## 7. 文件

- `results/gold_edge_types.json` — 逐边分类（含 note）
- `scripts/classify_gold_edges.py` — 启发式分类器
- `THEORY.md` — 定义
