# 确认集结果分析

## 1. gold 分布

| category | queries | POS | NEG | UNK |
|---|---|---|---|---|
| aggregate | 10 | 20 | 45 | 11 |
| case | 6 | 25 | 127 | 4 |
| cte | 5 | 14 | 76 | 0 |
| join | 11 | 54 | 31 | 19 |
| projection | 10 | 32 | 34 | 0 |

## 2. 按类别的 micro P/R/F1

| category | method | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|
| aggregate | fixed | 12 | 0 | 8 | 1.000 | 0.600 | 0.750 |
| aggregate | literal | 14 | 0 | 6 | 1.000 | 0.700 | 0.824 |
| aggregate | union | 15 | 0 | 5 | 1.000 | 0.750 | 0.857 |
| case | fixed | 19 | 4 | 6 | 0.826 | 0.760 | 0.792 |
| case | literal | 13 | 0 | 12 | 1.000 | 0.520 | 0.684 |
| case | union | 21 | 4 | 4 | 0.840 | 0.840 | 0.840 |
| cte | fixed | 11 | 0 | 3 | 1.000 | 0.786 | 0.880 |
| cte | literal | 10 | 0 | 4 | 1.000 | 0.714 | 0.833 |
| cte | union | 13 | 0 | 1 | 1.000 | 0.929 | 0.963 |
| join | fixed | 31 | 0 | 23 | 1.000 | 0.574 | 0.729 |
| join | literal | 34 | 0 | 20 | 1.000 | 0.630 | 0.773 |
| join | union | 40 | 0 | 14 | 1.000 | 0.741 | 0.851 |
| projection | fixed | 22 | 0 | 10 | 1.000 | 0.688 | 0.815 |
| projection | literal | 21 | 0 | 11 | 1.000 | 0.656 | 0.792 |
| projection | union | 28 | 0 | 4 | 1.000 | 0.875 | 0.933 |

## 3. 预测落在 UNKNOWN 边上的数量（不计入 P/R）

| method | pred on UNKNOWN |
|---|---|
| fixed | 4 |
| literal | 0 |
| union | 4 |

## 4. 敏感性：把 UNKNOWN 当作 NEGATIVE 重新计分

| method | TP | FP(含原 UNKNOWN) | P | R | F1 |
|---|---|---|---|---|---|
| fixed | 95 | 8 | 0.922 | 0.655 | 0.766 |
| literal | 92 | 0 | 1.000 | 0.634 | 0.776 |
| union | 117 | 8 | 0.936 | 0.807 | 0.867 |

## 5. gold POSITIVE 但两个方法都漏掉的边

| category | missed by both |
|---|---|
| aggregate | 5 |
| case | 4 |
| cte | 1 |
| join | 14 |
| projection | 4 |
| **total** | **28** |
