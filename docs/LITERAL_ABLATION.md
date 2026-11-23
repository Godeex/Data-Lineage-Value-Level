# Literal Probing 消融（30 条人类 gold）

> 目的：回答“Literal probing 的增益究竟来自 SQL 字面量、边界值、结构触发，还是单纯增加了扰动次数？”

## 1. 消融设置

| 变体 | 候选值 | 说明 |
|---|---|---|
| Full | SQL literals + boundaries | 完整 literal probe |
| Literals only | 仅 SQL literals | 不含 ±1e6 等极值 |
| Boundary only | 仅 boundaries | ±1e6、0、1、空串、数字串 |
| Random | 随机类型匹配值 | 与 full 相同候选数量，排除“只是多跑” |
| Structural full | 有 WHERE/CASE/GROUP BY/ORDER BY 才用 full，否则 CELL_VALUE b3 | 结构触发 |
| Structural literals | 有结构时仅 literals，否则 CELL_VALUE b3 | 结构触发 + 仅字面量 |

评测：30 条人类 gold；micro P/R/F1、macro F1、执行次数。

## 2. 结果

| 变体 | Micro P | Micro R | Micro F1 | Macro F1 | 执行次数 |
|---|---|---|---|---|---|
| **Full** | 1.000 | **0.632** | **0.775** | **0.728** | 474 |
| Literals only | 1.000 | 0.287 | 0.446 | 0.399 | 195 |
| Boundary only | 1.000 | 0.552 | 0.711 | 0.594 | 321 |
| Random | 1.000 | 0.494 | 0.662 | 0.566 | 688 |
| Structural full | 1.000 | 0.621 | 0.766 | 0.717 | 412 |
| Structural literals | 1.000 | 0.391 | 0.562 | 0.541 | 209 |

## 3. 解读

1. **候选值选择本身有信息量，不只是“多跑”**  
   Random 的 recall 0.494，低于 Boundary 0.552 与 Full 0.632，但执行次数更高（688 vs 474）。  
   说明：**不是扰动次数越多越好；选对候选值域才有效。**

2. **Boundary 贡献最大，Literals 补充谓词阈值**  
   - Boundary only 恢复 0.552，是主要来源（极值能翻转 CASE/聚合）。  
   - Literals only 只有 0.287；单独不够（很多边需要跨过 `avg>0` 之类的边界）。  
   - Full 0.632 > Boundary 0.552：字面量补上了 `Year=2014`、`country='France'` 这类谓词。

3. **结构触发可以省成本**  
   Structural full：R 0.621、F1 0.766、成本 412，接近 Full（0.632/0.775/474），但便宜约 13%。  
   说明简单结构规则（WHERE/CASE/GROUP BY/ORDER BY）足以决定何时值得做 literal probe。

4. **对论文的含义**  
   Literal probing 的方法贡献应描述为：
   - **结构感知的候选值域**（SQL literals + boundaries），不是“更多扰动”；
   - 边界值是主要收益来源，字面量是补充；
   - 结构触发是成本优化，不是性能提升。

## 4. 局限

- n=30；部分类别（case/cte）只有 6 条。
- 候选值域仍是手工规则；没有学习“该给哪一列什么候选”。
- Random 控制使用固定种子；不同随机种子可能略有波动。
- 未测“只对谓词列做 literal、不对投影列做”的更细粒度策略。

## 5. 结论

消融支持：
- Literal probing 的增益来自**候选值域的结构选择**，不是单纯增加扰动次数；
- Boundary + literals 互补；
- Structural trigger 是性价比更高的部署方式。

这直接回应 comment02 的 P1-1，并加强论文对 Literal probing 的方法解释。
