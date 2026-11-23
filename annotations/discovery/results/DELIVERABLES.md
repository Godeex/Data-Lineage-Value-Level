# 产物清单（30 条试点 · 三人标注）

> 生成日期：2026-11-17　｜　状态：完成（三人独立标注 + 5 条联合校准 + 仲裁）
> 一句话结果：gold 96 条（POSITIVE 87 / NEGATIVE 2 / UNKNOWN 7）；三人二分类 κ 0.942–1.000（均值 0.961）；机器 `reference` precision 1.000 / recall 0.874。

## 1. 先看这三份

| 文件 | 用途 |
|---|---|
| `annotation_report.md` | 总览：一致性、gold 构成、机器对比、6 个发现、局限、复现步骤 |
| `gold_edges.jsonl` | **最终 gold**（按 qid 分组，三态 + confidence + note） |
| `arbitration.md` | 13 条分歧的逐条裁决（A/B/C → 最终 + 理由） |

## 2. 标注表

| 文件 | 说明 |
|---|---|
| `annotation_A.csv` / `annotation_B.csv` / `annotation_C.csv` | 三人终稿；`qid,annotator,output_column,source_table,source_column,decision,confidence,note`；无边 query 用 `NONE` 行 |
| `round1/annotation_A_round1.csv` 等 | 首轮独立标注（校准前），供审计 |
| `notes_A.md` / `notes_B.md` / `notes_C.md` | 每人的策略、耗时、疑难、定义问题、建议 |

## 3. 一致性与校准

| 文件 | 说明 |
|---|---|
| `compute_kappa.py` | 两两 κ（二分类 / 三分类 / 四分类含 ABSENT）、混淆矩阵、raw agreement、PABAK |
| `kappa_report.json` | 终稿一致性（门槛 ≥0.7，已通过） |
| `round1/kappa_report_round1.json` | 首轮一致性（均值 0.445，触发校准） |
| `calibration.md` | 5 条联合校准的口径与重标结果 |

## 4. 机器建议对比

| 文件 | 说明 |
|---|---|
| `machine_vs_gold.md` | 四类差异表：machine POS & gold POS / gold UNKNOWN；machine absent & gold POS / NEG / UNKNOWN |
| `machine_reference_report.md` / `.json` | `reference`、`static`、并集的 precision / recall；两个建议都漏的 8 条边 |

## 5. 工具与证据

| 文件 | 说明 |
|---|---|
| `tools/perturb_oracle.py` | 单格扰动 oracle（CELL_VALUE / VALUE_TO_NULL / NULL_TO_VALUE），输出见证 |
| `tools/evidence.json` | 见证库：每条边对应哪张表、哪一行、改成什么、哪个输出列变了 |
| `tools/verify_gold.py` | gold ↔ 见证交叉核对（POSITIVE 必须有见证；UNKNOWN/NEGATIVE 不得有见证） |
| `tools/gold_catalog.py` | 仲裁后的 gold 目录（显式决策表，可审计） |
| `tools/build_annotation_sheets.py` | 由 gold 目录 + 三人口径差异生成三份 CSV、gold、差异表 |
| `tools/machine_report.py` | 生成第 4 节的两份对比报告 |
| `tools/refresh_manifest.py` | 重算 `manifest.json` 的 SHA256 |
| `inspect_db.py` | 查看库结构（原包自带） |

## 6. 输入（未改动）

`sample_30.jsonl`、`dbs/*.sqlite`（8 个）、`annotation_sheet.csv`（预填机器建议）、`annotation_sheet_blank.csv`、`THEORY.md`、`ANNOTATION.md`、`README.md`。

## 7. 快速核对（3 条命令）

```bash
cd annotation_package
python compute_kappa.py --a annotation_A.csv --b annotation_B.csv --c annotation_C.csv  # 均值 κ 0.961
python tools/verify_gold.py                                                            # 0 处矛盾
python tools/machine_report.py                                                         # reference P=1.000 R=0.874
```

期望输出：`mean binary kappa = 0.9611`；`witnessed edges in probe: 87`；`POSITIVE without witness: 0` / `UNKNOWN/NEGATIVE with witness: 0`。

## 8. 口径要点

1. 输出按**行多重集**比较，行数变化即多重集变化。
2. `CELL_VALUE` 的候选值域：列内值、SQL 字面量、±1、极端哨兵、文本列的数字形态。
3. 可证不变 → `NEGATIVE`；仅在 D 上不可观测（空过滤 / 类型错配 / LIMIT / CASE 遮蔽）→ `UNKNOWN`。
4. `NONE` 行 = 已证明无边，与"全部 UNKNOWN"不同。
5. 类型强制才成立的边（coercion-only）单独在 note 标注。
