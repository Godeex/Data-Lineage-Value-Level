# 人类 Gold 结果与严格 Held-out 审计（30 条标注）

> **重要更正（2026-11-17）**：早先 “Evolving 显著优于 Fixed hybrid（+21.7 pp）” 来自 pilot split；审计发现 **30 条 gold query 全部落在 P2 的 train split**，属于训练/测试重叠。严格 held-out（gold 完全不参与策略学习）下，**Evolving ≈ Fixed hybrid（ΔF1 = −0.010，p = 0.909）**，Evolving 的增益不成立。  
> **仍然成立的是 Literal probing**：严格 held-out 下 Literal vs Fixed hybrid ΔF1 = +0.153（p = 0.010）。  
> 详见 `HELDOUT_AUDIT.md`、`STAT_AUDIT.md`、`SILVER_AUDIT.md`。

---

## 1. 标注质量与 gold 构成

| 项 | 结果 |
|---|---|
| 标注者 | 3 人（A 语义派 / B 实例探针派 / C 保守派） |
| 首轮二分类 κ | 0.219–0.897（均值 0.445）→ 5 条联合校准 |
| 终稿二分类 κ | A–B 0.942 / A–C 1.000 / B–C 0.942，**均值 0.961** |
| 终稿三分类 κ | 0.940–1.000 |
| gold 边数 | **96**：POSITIVE 87 / NEGATIVE 2 / UNKNOWN 7 |
| 确认无边 query | 3 条（`synth-cte-001`、`synth-case-000`、`synth-case-001`） |

> κ 只表示一致性；同时报告 raw agreement（0.990–1.000）与 PABAK（0.979–1.000），避免高患病率下的 κ 悖论。

---

## 2. 机器 reference vs 人类 gold

| 建议 | 条数 | 命中 POS | 误报 | Precision | Recall |
|---|---|---|---|---|---|
| machine reference | 76 | 76 | 0 | **1.000** | **0.874** |
| static | 25 | 25 | 0 | 1.000 | 0.287 |
| reference ∪ static | 79 | 79 | 0 | 1.000 | 0.908 |
| reference ∪ static ∪ literal | 86 | 86 | 0 | 1.000 | 0.989 |

**11 条 reference 漏报**：

| 类型 | 数量 | 例子 |
|---|---|---|
| WHERE 过滤列 | 6 | `validation-00020 count(*) ← concert.year`；`synth-cte-004 avg/min/max(age) ← singer.country` |
| CASE 派生输出 | 2 | `synth-case-010 bucket ← concert.year`；`synth-case-007 bucket ← stadium.capacity` |
| GROUP BY 键派生输出 | 2 | `synth-case-005 count(*) / bucket ← singer.country` |
| 类型强制（coercion） | 1 | `validation-00174 countryname ← car_makers.country` |

**结论**：盲区不是随机噪声，而是集中在**谓词列**（WHERE / GROUP BY / CASE）和类型强制。

---

## 3. 严格 held-out 结果（30 条人类 gold）

划分：移除 30 条 gold 及其同 SQL 模板；剩余 100 条按 SQL template 分 train 43 / val 16 / regression 19。  
策略只在 train 上学习、val 上选择，冻结后在 gold 上评估；学习过程不读取 gold/silver/test 标签。

| 方法 | Micro P | Micro R | Micro F1 | Macro F1 | 成本 |
|---|---|---|---|---|---|
| Static | 1.000 | 0.287 | 0.446 | 0.356 | 0 |
| Machine reference | 1.000 | 0.874 | 0.933 | 0.732 | 960 |
| Fixed hybrid | 1.000 | 0.552 | 0.711 | 0.574 | 60 |
| **Evolving（strict）** | **1.000** | **0.552** | **0.711** | **0.564** | 56 |
| Literal probe | 1.000 | 0.632 | 0.775 | 0.728 | 474 |
| **Literal ∪ Evolving（strict）** | **1.000** | **0.759** | **0.863** | **0.781** | 530 |
| Predicate-aware | 1.000 | 0.747 | 0.855 | 0.770 | 454 |

严格学到的策略：aggregate/case/cte → budget 1；join → budget 3；projection → budget 10。  
由于 train 中不再包含 gold，学习器没有找到能泛化到 gold 的更大预算策略，Evolving 退化为接近 Fixed hybrid。

---

## 4. 配对 bootstrap（严格 held-out，n=30，macro/query-level F1）

| 对比 | ΔF1 | 95% CI | p | 判读 |
|---|---|---|---|---|
| **Evolving − Fixed hybrid** | **−0.010** | [−0.110, 0.090] | **0.909** | **无增益** |
| **Literal − Fixed hybrid** | **+0.153** | [0.036, 0.286] | **0.010** | **稳健** |
| Literal∪Evolving − Fixed hybrid | +0.207 | [0.094, 0.337] | <0.001 | 主要来自 literal |
| Literal∪Evolving − Evolving | +0.217 | [0.104, 0.344] | <0.001 | 增益来自 literal |
| **Literal∪Evolving − Machine reference** | **+0.049** | [−0.105, 0.214] | **0.558** | **不显著** |
| Predicate-aware − Fixed hybrid | +0.195 | [0.083, 0.325] | <0.001 | 稳健 |

> 早先 pilot 的 “Evolving vs Fixed +0.181 / p<0.001” 与 “Literal∪Evolving vs Machine +0.150 / p=0.006” 都因 30/30 gold 落在 train 而不可用；本表是严格 held-out 结果。

---

## 5. 微/宏口径（回应 comment02 P0-1）

| 方法 | Micro F1 | Macro F1 |
|---|---|---|
| Machine reference | 0.933 | 0.732 |
| Reference ∪ static | 0.952 | 0.771 |
| Fixed hybrid（strict） | 0.711 | 0.574 |
| Evolving（strict） | 0.711 | 0.564 |
| Literal（strict） | 0.775 | 0.728 |
| Literal∪Evolving（strict） | 0.863 | 0.781 |

- 早先表格用 **micro** F1，统计用 **macro/query-level** F1；因此出现 “0.958−0.933=0.025” 与 “ΔF1=0.150” 的矛盾。
- 论文必须同时报告两者，并预先声明主指标（本项目为 macro query-level F1）。详见 `STAT_AUDIT.md`。

---

## 6. 五个发现（修正后）

1. **执行证据存在结构性盲区**  
   machine reference P=1.000/R=0.874；11 条漏报中 10 条是谓词列/CASE/GROUP BY。**稳健。**

2. **Literal probing 能补盲区**  
   严格 held-out：Literal vs Fixed ΔF1 +0.153（p=0.010）；`literal ∪ reference` 在 gold 上 R=0.977。**稳健。**

3. **Evolving 的 pilot 增益是训练/测试重叠**  
   30/30 gold 在 train；严格 held-out Evolving ≈ Fixed（−0.010，p=0.909）。**撤回 “Evolving 优于 Fixed”。**

4. **Literal∪Evolving 的增益主要来自 literal，不是 evolution**  
   Literal∪Evolving − Evolving = +0.217（p<0.001）；但 Evolving 本身无-held-out 增益。

5. **Literal∪Evolving 不再显著优于 machine reference**  
   严格 held-out：ΔF1 +0.049，CI [−0.105, 0.214]，p=0.558；micro F1 甚至更低（0.863 vs 0.933）。  
   只能说“接近 machine reference 且成本更低”，不能说“优于”。

---

## 7. Claim ↔ 证据（修正后）

| Claim | 证据 | 档 | 允许措辞 |
|---|---|---|---|
| G1 machine reference 精度高、召回中等 | 76/76，R=0.874 | strong | “precision 1.0，recall 0.874” |
| G2 谓词列是主要盲区 | 10/11 漏报 | strong（n=30） | “系统性漏报谓词列” |
| G3 Literal 显著优于 Fixed hybrid | +0.153，CI [0.036,0.286]，p=0.010 | strong | “显著提升” |
| G4 Literal∪Evolving 优于 Fixed hybrid | +0.207，p<0.001 | strong | “显著优于 Fixed” |
| **G5 Evolving 优于 Fixed hybrid** | **−0.010，p=0.909** | **none** | **只能写“未见显著差异”** |
| **G6 Literal∪Evolving 优于 machine reference** | **+0.049，p=0.558** | **none** | **只能写“接近；未达显著”** |

**不能写**：
- “Evolving 通过自进化显著优于 Fixed hybrid”（strict held-out 反证）。
- “Literal∪Evolving 显著优于 machine reference”（p=0.558）。
- “170 条都有人类 gold”（只有 30 条）。

---

## 8. 对论文叙事的影响

原叙事把“自进化”作为核心贡献；strict held-out 后不成立。建议改为：

> **Evidence-aware lineage probing**: execution evidence is structurally incomplete; **literal probing** repairs the predicate-column blind spot and significantly improves over a fixed hybrid baseline; **evidence-constrained evolution** showed a promising pilot gain but did not survive strict held-out — we report it as a cautionary negative result and analyze the leakage.

贡献收敛为：
1. **问题与测量**：执行证据的结构性盲区 + 30 条人类 gold 校准。
2. **方法**：Literal probing 显著优于 Fixed hybrid（strict held-out）。
3. **负结果/边界**：Evolving 在严格隔离下无增益；说明“证据约束进化”需要更大的独立训练集与更强的策略搜索，当前证据不支持其 superiority。

---

## 9. 局限

- 人类 gold 只有 30 条；严格 held-out 的 train 只有 43 条，策略搜索空间受限。
- 30 条 gold 的 SQL 与部分 pool query 可能共享模板；已按 SQL template 分组移除同模板，但样本仍小。
- 匿名化 Spider：7 条 UNKNOWN 与 1 条 coercion 边。
- Literal probe 成本 474 executions/query；Literal∪Evolving 530；Fixed 60。
- Evolving 的负结果不等于“自进化永远无效”；只说明在本数据/策略空间/隔离协议下未见增益。

---

## 10. 下一步

1. 用严格策略重跑大集 silver（`results/silver_eval_strict.json`）：Evolving R=0.593 vs Fixed 0.602，确认无增益；Literal∪Evolving R=0.807。
2. 若继续做 evolution：需要 ≥100 条独立 train、预注册策略搜索空间、按 DB/template 划分、在独立 gold 上评估。
3. Literal probing 作为主线：补 P1 消融（SQL literals vs boundary vs random），并在 dbt/Jinja 上扩展 20–30 条。
4. 论文按修正后的叙事写作，不再把 Evolving 作为主贡献。
