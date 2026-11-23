# AgentDB 人工标注包（30 条）

## 内容

- `ANNOTATION.md`：完整标注手册（定义、流程、κ、仲裁）。
- `THEORY.md`：value-level lineage 的形式定义（L_sem / L_obs / coverage / abstention）。
- `sample_30.jsonl`：30 条 query，5 类各 6 条。
- `annotation_sheet.csv`：预填了机器 reference 边，供逐条判定。
- `annotation_sheet_blank.csv`：空白表，供标注者补充机器漏掉的边。
- `dbs/`：这 30 条 query 对应的 8 个 SQLite 数据库。
- `inspect_db.py`：查看某个库的表、列、前几行。
- `manifest.json`：文件 SHA256 与生成时间。

## 重要说明

`sample_30.jsonl` 里的 `reference_edges_suggestion` 是**机器穷举扰动**的结果，**不是人类 gold**。  
标注者必须独立判断，不能直接照抄；如果认为机器建议有误，请在 `note` 里写理由。

## 怎么标

1. 读 SQL + 用 `inspect_db.py` 看 schema/数据。
2. 独立写出你认为的 value-level 边（哪些源列真正影响哪个输出列）。
3. 对照 `reference_edges_suggestion` 和 `static_edges_suggestion`，逐条填 `annotation_sheet.csv`：
   - `decision`: POSITIVE / NEGATIVE / UNKNOWN
   - `confidence`: high / medium / low
   - `note`: 理由（尤其与机器建议不一致时）
4. 机器漏掉但你认为存在的边，追加到 `annotation_sheet_blank.csv`。
5. 两人独立完成后，按 `ANNOTATION.md` 算 Cohen's κ 并仲裁。

## 数据说明\n\n本地 Spider 数据库的值被匿名化（如 `v5_0`），部分过滤条件可能返回空；数据不足时请标 `UNKNOWN`，不要硬判。\n\n## 快速开始

```bash
python inspect_db.py dbs/concert_singer.sqlite
```

## 定义速记

> 在给定数据库实例上，若存在一个只改列 c 某一单元格的扰动，使输出列 o 的多重集发生变化，则 `(o, t, c)` 是一条 value-level 边。

这是**实例级反事实影响**，不是"所有可能实例都成立"的普遍语义依赖。

## 标注结果（2026-11-17 已完成）

- 三人标注（A 语义派 / B 实例探针派 / C 保守派）+ 5 条联合校准 + 仲裁。
- 终稿二分类 κ：A–B 0.942、A–C 1.000、B–C 0.942（均值 0.961）；三分类 κ 0.940–1.000。
- gold：`gold_edges.jsonl`，96 条（POSITIVE 87 / NEGATIVE 2 / UNKNOWN 7），30 条 query 全覆盖。
- 机器建议：`reference` precision 1.000 / recall 0.874；`reference ∪ static` recall 0.908。
- 详见 `annotation_report.md`；逐条裁决见 `arbitration.md`；口径校准见 `calibration.md`；产物清单见 `DELIVERABLES.md`。
