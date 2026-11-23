# 30 条试点：三人标注、一致性与仲裁报告

> 范围：`sample_30.jsonl` 的 30 条 query（aggregate / projection / join / cte / case 各 6 条），8 个 SQLite 库。
> 定义：`THEORY.md` §3 的实例级反事实值级血缘；输出按**行多重集**比较。
> 口径：Phase A 盲标（不看机器建议）→ Phase B 对照 → Phase C 合并；每条 POSITIVE 附单格扰动见证，UNKNOWN 附不可观测理由。
> **变更**：手册 §7/§8 写的是"双人 + 第三人仲裁"；本次按任务要求执行**三人**独立标注，κ 用两两计算并报告均值。

## 0. 结论摘要

| 指标 | 结果 |
|---|---|
| gold 边数 | **96**（POSITIVE 87 / NEGATIVE 2 / UNKNOWN 7），覆盖 30 条 query（其中 3 条确认无边） |
| 三人一致性（二分类 κ，终稿） | A–B 0.942、A–C 1.000、B–C 0.942，**均值 0.961**（门槛 ≥0.7） |
| 三分类 κ（共同边） | 0.940 – 1.000 |
| 原始一致率 / PABAK | 0.990–1.000 / 0.979–1.000 |
| 机器 `reference` precision / recall | **1.000 / 0.874**（76 条，0 条误报，11 条漏报） |
| 机器 `reference ∪ static` recall | 0.908（仍漏 8 条） |
| 首轮 κ（未校准） | A–B 0.219、A–C 0.219、B–C 0.897，均值 0.445 → 触发 5 条联合校准 |

一句话：**机器建议几乎不误报，但系统性漏报"谓词列"（WHERE / GROUP BY / CASE / 类型强制 join）；7 条边在匿名化实例上不可观测，只能给 UNKNOWN；统一口径后三人一致性达标。**

## 1. 交付物

| 文件 | 内容 |
|---|---|
| `annotation_A.csv` / `annotation_B.csv` / `annotation_C.csv` | 三人终稿（Phase A/B 合并后），每人 95–96 条判定 + 3 行 `NONE` |
| `round1/annotation_A_round1.csv` 等 | 首轮独立标注（校准前），供审计 |
| `round1/kappa_report_round1.json` | 首轮一致性（校准前，均值 0.445） |
| `notes_A.md` / `notes_B.md` / `notes_C.md` | 每人的策略、耗时、疑难、定义问题、建议 |
| `kappa_report.json` / `round1/kappa_report_round1.json` | `compute_kappa.py` 输出（两两 κ、混淆矩阵、分歧清单、PABAK） |
| `calibration.md` | 5 条联合校准的记录与重标结果 |
| `arbitration.md` | 13 条分歧的逐条裁决（A/B/C → 最终 + 理由） |
| `gold_edges.jsonl` | 仲裁后的三态 gold（按 qid 分组） |
| `machine_vs_gold.md` / `machine_reference_report.{md,json}` | 机器建议与 gold 的四类差异表与 P/R |
| `tools/perturb_oracle.py` + `tools/evidence.json` | 单格扰动见证库（哪张表、哪行、改成什么、哪个输出列变了） |

## 2. 三人分工与流程

| 标注者 | 策略 | 盲标时长 | 终稿条数 |
|---|---|---|---|
| A 语义派 | 先做语义推理，数据只作佐证；对"D 上不可观测"偏 POSITIVE | ~95 min | 96 |
| B 实例派 | 逐列逐行单格 `UPDATE`（±1/0/NULL/字面量）在 savepoint 内回滚找见证；无见证即 UNKNOWN | ~120 min | 95 |
| C 保守派 | 严格套手册三态细则；空结果/LIMIT/CASE 未触发一律 UNKNOWN | ~80 min | 96 |

流程：Phase A 独立盲标（不看 `reference_edges_suggestion`）→ Phase B 对照机器建议 → Phase C 合并；首轮 κ 不达标 → 5 条联合校准（`calibration.md`）→ 重标 → 仲裁（`arbitration.md`）。

## 3. 一致性

| 对 | 首轮 κ₂ | 终稿 κ₂ | 终稿 κ₃ | 终稿 raw / PABAK | 剩余分歧 |
|---|---|---|---|---|---|
| A–B | 0.219 | **0.942** | 1.000 | 0.990 / 0.979 | 1 条缺席（`validation-00174 car_makers.Country`） |
| A–C | 0.219 | **1.000** | 0.940 | 1.000 / 1.000 | 1 条 NEG/UNKNOWN（`synth-case-018 bucket ← pet_age`） |
| B–C | 0.897 | **0.942** | 0.940 | 0.990 / 0.979 | 同上 + 缺席 |

**为什么首轮 κ 只有 0.22 而一致率仍有 88.5%**：96 条边里 87 条是 POSITIVE，二分类的期望一致率 `p_e ≈ 0.89`，8 条分歧就足以把 κ 压到 0.2 附近（高患病率下的 κ 悖论，Byrt 1993 / Feinstein & Cicchetti 1990）。所以：

- 首轮 PABAK = 0.771，远高于 κ = 0.219，说明"分歧少但类别极不平衡"。
- 论文里建议**同时报 raw agreement、PABAK 和 κ**，并单列 UNKNOWN（THEORY §6 已要求 UNKNOWN 不进 P/R）。
- 本次的 κ 主要靠"统一口径"提升，不是靠删分歧：终稿仍保留 2 处真实分歧。

## 4. gold 构成

- **POSITIVE 87**：投影列（含 `ORDER BY ... LIMIT` 的排序键与 join 键）为主。
- **NEGATIVE 2**（均为机器没有提、标注者主动否定的候选）：
  - `validation-00262 name ← employee.age`：只有 `ORDER BY`、没有 `LIMIT`，行序不属于多重集 → 结构可证不变。
  - `synth-case-018 bucket ← pets.pet_age`：`bucket = CASE WHEN weight>0`，D 上 `min(weight)=1`，选哪一行都是 `'pos'` → 结构可证不变。
- **UNKNOWN 7**（全部由匿名化实例造成，语义上成立）：
  - `validation-00031` ×3（`stadium.Stadium_ID`、`concert.Stadium_ID`、`concert.Year`）
  - `validation-00174 countryname ← countries.countryid`
  - `synth-cte-004` ×3（`avg/min/max(age) ← singer.age`）
- **确认无边 3 条**：`synth-cte-001`、`synth-case-000`、`synth-case-001`（整表 `COUNT(*)` 及其派生 CASE：没有任何单元格能改变行数）。

## 5. 机器建议 vs gold

| 建议来源 | 条数 | 命中 POS | 命中 UNKNOWN | 误报（gold NEG） | precision | recall |
|---|---|---|---|---|---|---|
| `reference_edges_suggestion` | 76 | 76 | 0 | 0 | **1.000** | **0.874** |
| `static_edges_suggestion`（列名可对齐的 21 条） | 21 | 21 | 0 | 0 | 1.000 | 0.241 |
| 两者并集 | 79 | 79 | 0 | 0 | 1.000 | 0.908 |
| `static` 的位置式列名（`_col_0/_col_1`） | 7 | — | — | — | 无法对齐 | — |

- **零误报**符合 THEORY §5 的预期：`reference` 只报"观测到见证"的边，precision 理论上为 1。
- **漏报 11 条**（reference），按列的语义角色分：
  - `WHERE` 过滤列 6 条：`validation-00020`、`synth-cte-018`、`synth-case-010 count(*)`、`synth-cte-004 country`×3。
  - `CASE` 派生输出 2 条：`synth-case-010 bucket`、`synth-case-007 bucket`。
  - `GROUP BY` 键派生输出 2 条：`synth-case-005 count(*)`、`synth-case-005 bucket`。
  - 类型强制（coercion-only）join 1 条：`validation-00174 car_makers.Country`。
- **两个机器建议都漏的 POSITIVE 有 8 条**（见 `machine_reference_report.md`），说明 reference 与 static 是互补的：static 补了 `CASE`/`GROUP BY` 的两条，但覆盖仍不到 0.91。

## 6. 值得写进论文的六个发现

1. **谓词列是穷举 reference 的系统盲区**：11 条漏报里 10 条是 WHERE/GROUP BY/CASE 上的列，只有 1 条是 join 键。裸覆盖率会把"投影列覆盖率"误当成"血缘覆盖率"。
2. **实例级 ≠ 语义级，且差异可归因**：7 条 UNKNOWN 全部来自匿名化（REAL/TEXT 类型错配 4 条、空过滤 3 条）。如果换成自然 Spider 实例，这 7 条会变 POSITIVE —— 直接支撑 THEORY §7 的"实例质量预测 coverage"研究问题。
3. **`ORDER BY` 只在有 `LIMIT` 时才产生边**：`validation-00262`（无 LIMIT）是 NEGATIVE，`validation-00048` / `00487` / `synth-cte-016` / `synth-case-018`（有 LIMIT）是 POSITIVE。这是多重集语义最干净的一组对照。
4. **"常量输出"要区分两种**：`synth-case-018 bucket` 在 D 上恒为 `'pos'`（值不变、行数也不变）→ NEGATIVE；`synth-case-005 bucket` 虽恒为 `'pos'`，但单成员组消失会**少一行** → POSITIVE。只看"值是否变化"会把后者判错（C 首轮就是这么错的）。
5. **类型亲和会造出 coercion-only 边**：`validation-00174` 里只有把 TEXT 改成 `'5'` 才会被 NUMERIC 亲和匹配上 REAL id。这类边在原始 schema 上不存在，建议 gold 增列 `evidence_type ∈ {witness, structural, coercion, unobservable}`。
6. **值域/预算直接决定 coverage**：`synth-case-007 bucket` 需要 `-1e6` 量级的扰动才能触发（`avg<0`）；只试 ±1 的标注者（B/C 首轮）观测不到。同一 SQL 在"邻域扰动"与"任意值扰动"两种 P′ 下答案不同，必须在论文里写清扰动族。

## 7. 复现

```bash
cd annotation_package

# 1) 单格扰动见证（约 12 分钟，写 tools/evidence.json）
python tools/perturb_oracle.py --out tools/evidence.json

# 2) 生成三份标注表 + gold + 差异表
python tools/build_annotation_sheets.py

# 3) 一致性
python compute_kappa.py --a annotation_A.csv --b annotation_B.csv --c annotation_C.csv \
    --json-out kappa_report.json
python compute_kappa.py --a round1/annotation_A_round1.csv --b round1/annotation_B_round1.csv \
    --c round1/annotation_C_round1.csv --json-out round1/kappa_report_round1.json

# 4) 机器建议 vs gold
python tools/machine_report.py
```

## 8. 局限

- **样本小**：30 条、8 个库（每表 25–40 行），5 类各 6 条；类别内重复度高（`validation-00069` 与 `00070` 同 SQL）。
- **实例被匿名化**：值被替换为 `v*_*`、部分列类型被改（REAL ↔ TEXT），7 条 UNKNOWN 与 1 条 coercion 边由此而来；不能外推到原始 Spider 分布。
- **候选扰动集不完备**：POSITIVE 都有可复现见证，可信度高；NEGATIVE 只在"结构可证"时给出（2 条）；其余未观测到的一律 UNKNOWN。不存在"穷举证明"。
- **κ 的患病率问题**：见 §3；不要只报 κ。
- **列名规范化**：`static` 用 `_col_*`，`reference` 用表达式名（`avg(capacity)`），评测必须 casefold + 规范化，否则会凭空多出 7 条"未对齐"。

## 9. 建议的下一步

1. 把 §6 的 5 条口径写回 `ANNOTATION.md`（行多重集、扰动值域、UNKNOWN vs NEGATIVE 判据、NONE 语义、κ 口径）。
2. `gold_edges.jsonl` 增加 `evidence_type` 与 `witness` 字段（本包 `tools/evidence.json` 已有原始见证，可直接回填）。
3. reference 生成器补齐：`WHERE`/`GROUP BY`/`CASE` 列 + SQL 字面量候选 + 字符串列的数字形态候选。
4. 扩到 100+ 条，并加入**未匿名化**的自然实例对照，量化"实例质量 → coverage"。
5. 若要对外发表，对 7 条 UNKNOWN 与 2 条 NEGATIVE 再做一轮复核（约 1 小时/人）。
