# 失败案例集（P1/P2/P3）

> 每条都给出证据路径；用于论文 failure analysis，不掩盖负面结果。

## F1. LIMIT 截断：预算增加也救不了

- **现象**：stress `limit` 8 条，b3_cell 与 b10_allcell coverage 都是 **0.125**。
- **原因**：LIMIT 只让被选中的行影响输出；扰动其它行不改变结果，oracle 无法观测。
- **证据**：`results/p1_coverage.summary.json` → `stress_type.limit`。
- **含义**：必须 abstain 或改用 row-delete/排序相关扰动；不能靠加预算。

## F2. 空结果：没有输出边，属于 abstain

- **现象**：stress `empty` 14 条，reference 边数 = 0。
- **原因**：查询结果为空，任何输入扰动都不改变输出；无法定义 value-level 边。
- **证据**：`results/p1_coverage.jsonl` 中 `stress_type=empty`，`n_ref=0`。
- **含义**：空结果是 abstention 的正例，不是“方法失败”；评测时应单列。

## F3. Fan-out：多 join 传导，覆盖仍然低

- **现象**：stress `fanout` 4 条，b3_cell 0.275 → b10_allcell 0.400。
- **原因**：多表 join 的键/行匹配会放大扰动影响，也会让部分边被其他路径掩盖。
- **证据**：`results/p1_coverage.summary.json` → `stress_type.fanout`。
- **含义**：需要 join-aware 扰动（键替换、行删除）与专门的 failure taxonomy。

## F4. CTE：覆盖提升不显著

- **现象**：CTE 14 条，+9.5 pp，95% CI [0.0, 20.2]，BH q=0.070。
- **原因**：CTE 变体多由投影 query 派生，base coverage 已较高（0.762），提升空间小；n=14。
- **证据**：`results/stats_summary.json` → `p1_by_category.cte`；`results/bh_qvalues.json`。
- **含义**：不能写“CTE 显著提升”；只能说“方向为正、样本不足”。

## F5. dbt/Jinja：原始模板不可解析

- **现象**：8 条 dbt-style 记录中 **4 条 raw static ParseError**（含 `ref()`、宏、`{% if %}`）。
- **原因**：Jinja 语法不是 SQL；sqlglot 在 `FROM {{ ref(...) }}` 处失败。
- **证据**：`results/p3_dbt.json` → `raw_static_status`。
- **含义**：宏展开是必要前置；论文应把“raw template → expanded SQL”作为方法的一部分。

## F6. 展开后静态仍不完整（join+aggregate）

- **现象**：`revenue_by_customer` 展开后 static F1 = 0.615（include_refunds=False）/ 0.421（True）。
- **原因**：join 键、聚合、宏生成 CASE 的边，静态 parser 只能给部分语法边；value-level reference 更多。
- **证据**：`results/p3_dbt.json` 对应记录 `expanded_static_f1`。
- **含义**：即使展开，静态血缘仍不足；oracle allcell coverage = 1.0 说明需要执行证据。

## F7. P2 held-out test 不显著

- **现象**：Evolving vs Fixed Hybrid 在 test 上 +13.7 pp，95% CI [0.0, 31.4]，p=0.070，BH q=0.070。
- **原因**：test n=17，功效不足；方向为正但 CI 含 0。
- **证据**：`results/stats_summary.json` → `p2_evolving_vs_fixed.test`；`results/bh_qvalues.json`。
- **含义**：只能写“方向为正、未达显著”；不能写 confirmatory superiority。需要 ≥50 条独立 test。

## F8. 成本 5.5×：进化不是免费的

- **现象**：Evolving 325 executions vs Fixed Hybrid 59（约 5.5×）。
- **原因**：按类别增加 budget 与扰动族；没有 early-stop/缓存。
- **证据**：`results/p2_evolution.json` 的 `mean_executions`。
- **含义**：必须报告 F1–cost Pareto；否则“进化”可能只是“多跑”。

## F9. 大集 reference 仍是机器穷举；人类 gold 只有 30 条

- **现象**：130/170 条 P1/P2 大集用机器 reference；30 条有人类 gold（三人，κ 0.961）。
- **原因**：人工标注成本高；本次只标了 30 条试点。
- **证据**：`RESULTS_HUMAN_GOLD.md`；`annotations/discovery/results/gold_edges.jsonl`。
- **含义**：论文必须区分“machine-verified 大集”与“human-gold 30 条”；不能把 30 条 gold 的结论外推到全部 170 条。

## F10. Spider 匿名化值导致大量空结果

- **现象**：自然 Spider query 中不少过滤条件（如 `country='France'`）在匿名化数据中没有匹配行。
- **原因**：本地 Spider 变体的值被替换为 `v5_0` 等占位符。
- **证据**：`results/p1_coverage.jsonl` 中 `n_ref=0` 的 query；`data/spider_stress.jsonl` 的 empty 组。
- **含义**：主集选非空 query 控制偏差；压力集保留空结果并单列，不静默删除。

## F11. 谓词列是机器 reference 的系统盲区

- **现象**：人类 gold 中 11 条 reference 漏报，10 条是 WHERE / GROUP BY / CASE 上的列。
- **原因**：`CELL_VALUE` 的 +100 扰动不跨过滤阈值（如 `Year=2014`、`country='France'`）；LIMIT/空结果让部分值不可观测。
- **证据**：`RESULTS_HUMAN_GOLD.md` §2；`machine_vs_gold.md`。
- **含义**：裸 coverage 会把“投影列覆盖率”误当“血缘覆盖率”；必须把谓词列单列，并用 literal probe 补。

## F12. Literal probe 仍漏 coercion-only / 多条件边

- **现象**：Literal∪reference 仍漏 2 条；Literal∪reference∪static 漏 1 条。
- **原因**：`validation-00174` 需要把 TEXT 改成 `'5'` 触发 NUMERIC 亲和；`validation-00031` 需要同时满足“id 匹配”和 `Year=2014`，单格扰动做不到。
- **证据**：`RESULTS_HUMAN_GOLD.md` §4；`results/gold_eval.json`。
- **含义**：需要类型亲和候选 + 多条件联合扰动；这是下一版 literal policy 的明确缺口。

## F13. Literal∪Evolving 的成本约 13× Fixed

- **现象**：782 executions/query vs Fixed hybrid 58。
- **原因**：字面量 + 极值候选 × 多行探测。
- **证据**：`results/gold_eval.json`。
- **含义**：必须报告 F1–cost Pareto；需要候选剪枝与 early-stop，否则“提升”可能只是多跑。

## F14. P2 的 train/test 重叠（已修正）

- **现象**：原 P2 split 中 30 条人类 gold query **全部**落在 train（30/30）；Evolving 在 gold 上看似 +21.7 pp。
- **原因**：按类别随机分层，未把 gold 作为 held-out 集合剔除；策略在 train 上通过 machine reference 看到了这些 query 的反馈。
- **证据**：`HELDOUT_AUDIT.md` §1。
- **修正**：严格 held-out 移除 30 条 gold 及其同 SQL 模板；train 43 / val 16 / regression 19；Evolving vs Fixed ΔF1 −0.010（p=0.909）。
- **含义**：这是典型的“评测集泄漏”；论文必须报告严格 held-out，不得保留 pilot 的 +21.7 pp。

## F15. Evolving 的增益未复现（负结果）

- **现象**：严格 held-out 下 Evolving ≈ Fixed hybrid（micro R 0.552 vs 0.552；ΔF1 −0.010，p=0.909）；大集 silver 上 Evolving 0.593 vs Fixed 0.602。
- **原因**：在非 gold train 上，学习器选择的策略退化为 budget 1；没有找到可泛化的更大预算/扰动族。
- **证据**：`results/heldout_gold.json`、`results/heldout_stats.json`、`results/silver_eval_strict.json`。
- **含义**：不能把“自进化”作为主贡献；论文应把它写成负结果/边界，并讨论训练集规模与策略搜索空间的限制。

## F16. Literal∪Evolving 的优势主要来自 Literal

- **现象**：严格 held-out 下 Literal∪Evolving − Evolving = +0.217 F1（p<0.001）；但 Evolving 本身无增益。
- **原因**：literal probing 是实际有效的组件；evolution 只是把 static 与 oracle 组合起来。
- **证据**：`results/heldout_gold.json`。
- **含义**：贡献应归给 Literal probing；Evolving 不能单独作为创新点。
