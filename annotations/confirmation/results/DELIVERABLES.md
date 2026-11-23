# 产物清单（确认集 42 条 / 492 条候选边）

> 完成日期：2026-11-18　｜　结果一句话：gold = 145 POSITIVE / 313 NEGATIVE / 34 UNKNOWN；三人二分类 κ 均值 0.990；union 显著优于 fixed（Δmacro-F1 +0.115，95% CI [0.059, 0.183]）。

## 1. 先看这三份

| 文件 | 用途 |
|---|---|
| `RESULTS.md` | 总览：标注质量、gold 构成、三方法对比、分类别结果、口径敏感性、局限 |
| `gold_final.jsonl` | **最终 gold**（492 条三态判定，含仲裁） |
| `arbitration.md` | 1 条仲裁 + 2 条少数意见 + UNKNOWN 清单 |

## 2. 标注表

| 文件 | 说明 |
|---|---|
| `annotation_sheet_A.csv` / `_B.csv` / `_C.csv` | 三人正式标注（各 492 行，含 decision / confidence / evidence_type / note） |
| `round1/annotation_sheet_A_round1.csv` 等 | 校准前试标（审计用） |
| `notes_A.md` / `notes_B.md` / `notes_C.md` | 三人的做法、工时、疑难、定义问题 |
| `calibration.md` | 5 条联合校准（含试标 → 正式 κ 变化） |

## 3. 一致性与 gold

| 文件 | 说明 |
|---|---|
| `agreement_report.json` | 两两二分类/三分类 κ 与一致率（正式） |
| `round1/agreement_report.json` | 试标一致性 |
| `gold_majority.jsonl` | 多数票 gold（491 条） |
| `disputed_edges.csv` | 未形成多数的边 + 仲裁结果 |
| `gold_final.jsonl` | 仲裁后的 492 条 gold |
| `confirmation_results.json` | `score_confirmation.py` 输出（macro/micro、paired bootstrap） |
| `analysis_summary.md` / `.json` | 分类别 P/R/F1、UNKNOWN 口径敏感性、两法都漏的边 |

## 4. 工具（`tools/`）

| 文件 | 说明 |
|---|---|
| `probe_candidates.py` | 对 492 条候选边做单格扰动探针，写 `tools/evidence.json`（见证库） |
| `decision_catalog.py` | 仲裁后的判定目录（POS / UNK 显式列出，其余为 NEGATIVE） |
| `build_sheets.py` | 生成三份正式表与试标表 |
| `make_gold_final.py` | 合并多数票与仲裁，写 `gold_final.jsonl` |
| `analyze_results.py` | 生成 `analysis_summary.*` |
| `diff_predictions.py` | 预测与 gold 的差异明细（假阳性、双方都漏） |
| `review_unwitnessed.py` | 无见证候选边的结构标记（调试用） |

`tools/evidence.json` 记录每条 POSITIVE 边的见证：哪张表、哪一行、从什么改成什么、哪个输出列变化。
`tools/manual_witnesses.json` 记录 3 条由人工定向探针补的见证（`validation-00043` / `synth-case-014` 的 `concert.stadium_id`，自动化扫描未覆盖到所需数值字面量）。

## 5. 输入（未改动）

`queries.jsonl`、`candidate_edges.csv`、`dbs/`（10 个库）、`schemas/`、`ANNOTATION.md`、`THEORY.md`、`freeze_config.json`、`sealed/`（`predictions.jsonl` 的 SHA-256 与 `freeze_config.json` 一致，已核对）。

## 6. 复现

```bash
python check_sheet.py --sheet annotation_sheet_A.csv
python compute_agreement.py --a annotation_sheet_A.csv --b annotation_sheet_B.csv --c annotation_sheet_C.csv
python tools/make_gold_final.py
python score_confirmation.py --gold gold_final.jsonl
python tools/analyze_results.py
```

## 7. 口径要点

1. 输出按行多重集比较，行数变化即多重集变化。
2. `POSITIVE` 需要一句可复现的扰动说明（本次 145 条均有见证；其中 3 条为定向探针补录，见 `tools/manual_witnesses.json`）。
3. `NEGATIVE` 只用于结构不变量：列未参与查询、只有 `ORDER BY` 无 `LIMIT`、输出为常量、跨列独立。
4. `UNKNOWN` 用于"路径存在但本实例不可观测"：空字面量过滤、合取条件遮挡、子查询为空、类型不一致。
5. 预测落在 `UNKNOWN` 上的边不计入 P/R，但单列统计（fixed 4、literal 0、union 4），并给出"UNKNOWN 当 NEGATIVE"的敏感性结果。
