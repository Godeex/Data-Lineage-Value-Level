# 标注手册：Value-Level Lineage（30 条试点，v3·已完成）

> **状态**：`COMPLETED`（2026-11-17）—— 三人独立标注 + 5 条联合校准 + 仲裁。  
> 终稿 gold：**96 条**（POSITIVE 87 / NEGATIVE 2 / UNKNOWN 7）；三人二分类 κ **0.961**（A–B 0.942 / A–C 1.000 / B–C 0.942）。  
> 结果与后续实验见 `RESULTS_HUMAN_GOLD.md`；原始交付在 `annotations/discovery/results/`。  
> 本文件仍作为标注口径与复标手册保留；机器 `reference_edges_suggestion` **不是 gold**。

---

## 1. 任务与定义

对每条 SQL，判断“哪些源列真正影响了哪个输出列”。

**实例级反事实定义**（与 `THEORY.md` 一致）：

> 给定数据库实例 `D` 与查询 `Q`。若存在一个**只改列 c 某一单元格**的扰动，使输出列 o 的多重集发生变化，则 `(o, t, c)` 是一条 value-level 边。

- 这是**给定实例上的反事实影响**，不是“所有可能实例都成立”的普遍语义依赖。
- 列级边只使用三类**列级扰动族**：
  - `CELL_VALUE`：把某单元格换成同类型另一个值
  - `VALUE_TO_NULL`：把非 NULL 值置为 NULL
  - `NULL_TO_VALUE`：把 NULL 置为默认非 NULL 值
- `ROW_DELETE` / `ROW_DUPLICATE` 只用于“这一行是否影响结果”的辅助分析，**不能归因到某一列**，不要写进列级边。

---

## 2. 包内文件与路径

标注包：

```
annotation_package/
  README.md
  ANNOTATION.md          ← 本文件
  THEORY.md
  sample_30.jsonl        ← 30 条 query
  annotation_sheet.csv   ← 预填机器建议边
  annotation_sheet_blank.csv
  dbs/<db_id>.sqlite     ← 8 个 SQLite 数据库
  inspect_db.py
  compute_kappa.py
  manifest.json
```

- 数据库用 `dbs/<db_id>.sqlite`

---

## 3. 边的格式

每条边写成三元组：

```
(output_column, source_table, source_column)
```

规则：

1. `output_column`：SQL 输出列名（`SELECT ... AS alias` 用 alias；没有 alias 用表达式列名）。
2. `source_table`：**真实表名**，不是别名。例如 `FROM singer AS s` 写 `singer`，不写 `s`。
3. `source_column`：真实列名。
4. 比较时**大小写不敏感**；填表时保留数据库/ SQL 中的写法即可，评测会 casefold。
5. 如果输出有重名列，在 `note` 里写输出列位置（第几个），例如 `dup output #2`；不要靠重名列猜测。
6. 不要写常量、字面量、CTE 名、子查询别名作为 `source_table`；只写最终基表。

---

## 4. 标注流程（避免被机器建议锚定）

### Phase A：独立盲标（必须先做）

1. 读 SQL，用 `python inspect_db.py dbs/<db_id>.sqlite` 看 schema 与前几行。
2. 不看 `reference_edges_suggestion`，先在 `annotation_sheet_blank.csv` 写出你认为的边。
3. 每条边给 `decision=POSITIVE`，`confidence=high/medium/low`，`note` 写理由。

### Phase B：对照机器建议

4. 打开 `annotation_sheet.csv`（预填机器建议），逐条对照：
   - 你已写过的边：确认或修改。
   - 机器有、你没有：判断 `POSITIVE` / `NEGATIVE` / `UNKNOWN`。
   - 你有、机器没有：保留在 blank 表，`note` 写 `machine missed`。
5. 不要因为“机器说了”就改判；机器只是提示。

### Phase C：合并与提交

6. 把 Phase A/B 的最终判断合并到一份 `annotation_sheet.csv`（每人一份）。
7. 提交时文件名：`annotation_<annotator>.csv`；另附 `notes_<annotator>.md` 记录耗时、疑难、定义问题。

---

## 5. 三态判定细则

| 判定 | 含义 | 例子 |
|---|---|---|
| `POSITIVE` | 我认为该边真实存在 | `SELECT amount*2 AS d` → `(d, t, amount)` |
| `NEGATIVE` | 我认为该边不存在（机器误报） | JOIN 键不影响某输出列，但机器报了 |
| `UNKNOWN` | 数据/语义不足，无法判断 | 空结果、LIMIT 截断、值被匿名化导致无法触发 |

重要规则：

- **空结果**：`WHERE` 过滤后没有行 → 没有输出值可被影响；“没有边”本身是正确结果，但**不要伪造边**。若无法判断结构依赖，标 `UNKNOWN`。
- **LIMIT**：只有被选中的行影响输出；未选中行不可观测。若 SQL 有 `LIMIT`，在 `note` 写 `LIMIT: unobservable rows`。
- **聚合**：`SUM/AVG/COUNT` 的输出受输入列影响；`GROUP BY` 键也可能影响输出分组。逐条判断，不要一概而论。
- **CASE**：未触发的分支不可观测；如果数据里没有触发，标 `UNKNOWN` 或只标可观测部分，并在 `note` 说明。
- **UNKNOWN 不参与 P/R**：评测时单列，不能强行二值化。

---

## 6. 填表格式

`annotation_sheet.csv` 列：

| 列 | 填法 |
|---|---|
| `qid` | 来自 `sample_30.jsonl` |
| `annotator` | 你的名字/代号 |
| `output_column` | 输出列名 |
| `source_table` | 真实表名 |
| `source_column` | 源列名 |
| `decision` | `POSITIVE` / `NEGATIVE` / `UNKNOWN` |
| `confidence` | `high` / `medium` / `low` |
| `note` | 理由；与机器不一致时必填 |

**整条 query 没有边**时，加一行：

```
qid,annotator,NONE,NONE,NONE,NONE,high,no value-level edges
```

**机器漏掉的边**：追加到表里，`decision=POSITIVE`，`note` 写 `machine missed`。

---

## 7. 一致性与 Cohen's κ

两人独立完成后：

1. 用 `python compute_kappa.py --a annotation_A.csv --b annotation_B.csv`。
2. 脚本输出：
   - 共同边数、各自边数、并集边数
   - 二分类 κ（`POSITIVE` vs 非 `POSITIVE`）
   - 三分类 κ（`POSITIVE` / `NEGATIVE` / `UNKNOWN`）
   - 混淆矩阵
3. 目标：**二分类 κ ≥ 0.7**；低于 0.6 先做 5 条联合校准，再重标。
4. κ 只是一致性，不代表 ground truth 正确；κ 低时先修定义/手册，不要硬标。

---

## 8. 仲裁

- 分歧边由第三人（或两人讨论）裁决，记录理由。
- 无法裁决的标 `UNKNOWN`，不得强行二值化。
- 最终 gold 三态：`POSITIVE` / `NEGATIVE` / `UNKNOWN`。
- 仲裁记录写入 `arbitration.md`：qid、边、A 判定、B 判定、最终判定、理由。

---

## 9. 报告格式

每人提交：

- `annotation_<annotator>.csv`
- `notes_<annotator>.md`：耗时、疑难、定义问题、建议
- `arbitration.md`（合并后）
- `kappa_report.json`（`compute_kappa.py` 的输出）
- 机器 reference 与人工 gold 的差异表：
  - machine POSITIVE & human POSITIVE
  - machine POSITIVE & human NEGATIVE（机器误报）
  - machine NEGATIVE & human POSITIVE（机器漏报）
  - human UNKNOWN

---

## 10. 当前状态

- 样本与表：30 条，5 类各 6 条。
- 人工标注：**未执行**（没有可用标注者）。
- 当前所有“reference”结果都是**机器穷举参考**，不得写成 “human-verified gold”。

---

## 11. 数据说明（重要）

本地 Spider 数据库的值被匿名化（如 `v5_0`、`v10_0`），部分过滤条件（例如 `country='France'`）可能返回空结果。  
如果数据不足以判断某条边，请标 `UNKNOWN`，不要硬判；`UNKNOWN` 在评测中单列，不计入 P/R。

---

## 附录：一个完整例子

SQL：

```sql
SELECT id, amount * 2 AS doubled FROM src_a
```

表 `src_a(id INT, amount INT)`，数据 `[(1,10),(2,20)]`。

标注：

| qid | output_column | source_table | source_column | decision | confidence | note |
|---|---|---|---|---|---|---|
| demo | id | src_a | id | POSITIVE | high | 改 id 输出变 |
| demo | doubled | src_a | amount | POSITIVE | high | 改 amount 输出变 |
| demo | doubled | src_a | id | NEGATIVE | high | 改 id 不影响 doubled |

如果 `src_a` 为空：两条边都标 `UNKNOWN`，`note=empty table: unobservable`。
