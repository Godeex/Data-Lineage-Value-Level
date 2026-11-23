# 标注手册：Value-Level Lineage 独立确认集（v1）

**状态**：`READY_FOR_ANNOTATION`  
**目的**：为 literal-aware probing 提供一个**未参与方法设计**的人类 gold 确认集。  
**规模**：42 条 query（42 个唯一 SQL template），492 条候选边。  
**标注者**：3 人独立标注；5 条联合校准；分歧由第三人仲裁。  
**盲标**：标注者不得打开 `sealed/`，不得查看机器预测。

---

## 1. 任务

对每条 SQL 和每个候选三元组

```
(output_column, source_table, source_column)
```

判断源列是否对输出列存在**实例级反事实影响**。

### 1.1 定义

给定数据库实例 `D`、查询 `Q`、以及允许的列级扰动族：

- `CELL_VALUE`：把某单元格改成同类型的另一个值；
- `VALUE_TO_NULL`：把非 NULL 单元格改成 NULL；
- `NULL_TO_VALUE`：把 NULL 单元格改成默认非 NULL 值。

若存在**只改一个源列的一个单元格**的扰动，使输出列 `o` 的多重集发生变化，则
`(o, source_table, source_column)` 是一条 **POSITIVE** 边。

这是**给定实例上的反事实影响**，不是“所有可能实例都成立”的普遍语义依赖。

### 1.2 CONTROL 的边界

- **DATA**：源列的值直接进入输出值，例如 `amount*2`、`SUM(amount)`。
- **CONTROL**：源列影响输出行的存在、行数/多重性、分组、或 CASE 分支。例如
  `WHERE country='France'`、`GROUP BY country`、`JOIN ON ...`。
- **MIXED**：同一源列既有 DATA 又有 CONTROL 影响。
- **仅改变行顺序不算影响**。在 multiset 语义下，`ORDER BY` 只有在 `LIMIT`/`OFFSET`
  改变返回多重集时才可能产生 control 影响。
- `ROW_DELETE` / `ROW_DUPLICATE` 只用于辅助理解“这一行是否影响结果”，**不能**归因到某一列；
  不要把它们写成列级边。

---

## 2. 三种 decision

| decision | 含义 |
|---|---|
| `POSITIVE` | 你能构造/说明一个允许的单单元格扰动，使输出多重集改变 |
| `NEGATIVE` | 你判断该源列在允许扰动族下不会改变输出；仅在有把握时使用 |
| `UNKNOWN` | 无法判断、实例数据不足、类型/空值语义不清、或需要未支持的扰动 |

`UNKNOWN` 是合法答案；不要为了填满表格而猜 `NEGATIVE`。

---

## 3. 包内文件

```
annotations/confirmation/package/
  README.md
  ANNOTATION.md                 ← 本文件
  THEORY.md
  queries.jsonl                 ← 42 条 query（qid/db_id/category/sql/question/output_columns/tables）
  candidate_edges.csv           ← 492 条中性候选边（不含机器预测）
  annotation_sheet_A.csv        ← 标注者 A 的空白表
  annotation_sheet_B.csv
  annotation_sheet_C.csv
  dbs/<db_id>.sqlite            ← 只读 SQLite 实例
  schemas/<db_id>.json          ← 表与列
  inspect_db.py                 ← 只读查看 schema / 执行 SQL
  check_sheet.py                ← 检查漏填、非法 decision、重复行
  compute_agreement.py          ← 三人一致性 + majority + disputed
  score_confirmation.py         ← 冻结预测的 macro/micro F1 与 paired bootstrap
  freeze_config.json            ← 冻结参数与源码哈希
  sealed/                       ← 机器预测；标注完成前不要打开
    predictions.jsonl
    predictions.sha256
```

`candidate_edges.csv` 只由 SQL 中出现的列和 schema 枚举得到，不包含 machine reference、
static parser 或 literal probing 的预测。

---

## 4. 标注流程

1. **校准（5 条 query）**：三人一起逐条讨论，统一 POSITIVE/NEGATIVE/UNKNOWN 的边界。
   校准后不再讨论具体 query。
2. **独立盲标**：每人只填自己的 `annotation_sheet_X.csv`。不要看别人的表，不要打开 `sealed/`。
3. **自检**：运行
   ```bash
   python check_sheet.py --sheet annotation_sheet_A.csv
   ```
   确认没有空 decision、非法值或重复行。
4. **提交**：交回三个 CSV。协调人运行
   ```bash
   python compute_agreement.py \
     --a annotation_sheet_A.csv \
     --b annotation_sheet_B.csv \
     --c annotation_sheet_C.csv
   ```
   输出 `agreement_report.json`、`gold_majority.jsonl`、`disputed_edges.csv`。
5. **仲裁**：只对 `disputed_edges.csv` 中的边由第三人裁决；写回 `gold_final.jsonl`。
6. **评分**：协调人运行
   ```bash
   python score_confirmation.py --gold gold_final.jsonl
   ```
   `score_confirmation.py` 会读取 `sealed/predictions.jsonl`。

---

## 5. 填写规范

CSV 列：

| 列 | 取值 |
|---|---|
| `qid` | 已预填，不要改 |
| `annotator` | 已预填 A/B/C，不要改 |
| `output_column` | 已预填，不要改 |
| `source_table` | 已预填，不要改 |
| `source_column` | 已预填，不要改 |
| `decision` | `POSITIVE` / `NEGATIVE` / `UNKNOWN` |
| `confidence` | `1`（低）/ `2`（中）/ `3`（高） |
| `evidence_type` | `DATA` / `CONTROL` / `MIXED` / `INDIRECT` / 留空 |
| `note` | 可选，一句证据说明（例如 “WHERE 过滤列，改值改变行集合”） |

- 不要增删行；候选边的三元组是固定的。
- 如果候选边明显不成立，填 `NEGATIVE`；不确定填 `UNKNOWN`。
- `confidence` 必填；`evidence_type` 尽力填，不确定可留空。

---

## 6. 查看数据库

`inspect_db.py` 只读，不会修改数据库：

```bash
python inspect_db.py --db dbs/concert_singer.sqlite --schema
python inspect_db.py --db dbs/concert_singer.sqlite \
  --sql "SELECT * FROM singer LIMIT 5"
```

也可以用自己的 SQLite 客户端，但请保持只读。

---

## 7. 质量要求

- 三人独立标注；不要协商具体边。
- 目标：pairwise binary κ ≥ 0.80；低于该值时先检查定义理解，再决定是否重标。
- 所有 `POSITIVE` 应能用一句话说明“改哪个列、为什么输出多重集改变”。
- 所有 `NEGATIVE` 应能说明为什么允许的扰动族不会改变输出；否则用 `UNKNOWN`。
- 不要求标注者运行 literal probing 或 machine reference；只看 SQL、schema 和实例。

---

## 8. 重要边界

- 这 42 条 query 来自 non-gold strict pool，**没有参与 literal probing 的候选设计**。
- 其中部分 query 曾被 evolution policy 的训练/验证使用；literal probing 和 fixed hybrid 是确定性的，
  未在任何 query 上训练。因此本集可用于 **literal vs fixed 的人类确认**，不能用于确认 evolution。
- 本集只有 42 条 query；结论应按 paired query-level 统计报告，不宣称覆盖所有 SQL 形态。
