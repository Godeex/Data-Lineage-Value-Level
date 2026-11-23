# machine reference vs adjudicated gold

## counts

| bucket | edges |
|---|---|
| machine POS & gold POSITIVE | 76 |
| machine POS & gold NEGATIVE | 0 |
| machine POS & gold UNKNOWN | 0 |
| machine absent & gold POSITIVE | 11 |
| machine absent & gold NEGATIVE | 2 |
| machine absent & gold UNKNOWN | 7 |

machine reference edges: 76; gold edges: 96

## edge-level diff

### machine POS & gold UNKNOWN

| qid | output | source | note |
|---|---|---|---|

### machine absent & gold POSITIVE

| qid | output | source | note |
|---|---|---|---|
| validation-00020 | count(*) | concert.year | machine missed；WHERE Year=2014/2015；探针：concert.Year 'v10_0'->'2014' 使 count 0->1 |
| validation-00174 | countryname | car_makers.country | machine missed；探针：Country->'5' 经 NUMERIC 亲和被强制成 5，右侧非空使 EXCEPT 缩小 |
| synth-cte-018 | count(*) | concert.year | machine missed；validation-00020 的 CTE 包装 |
| synth-cte-004 | avg(age) | singer.country | machine missed；Country->'France' 放进一行，聚合由 NULL 变 20 |
| synth-cte-004 | min(age) | singer.country | machine missed；同一过滤列 |
| synth-cte-004 | max(age) | singer.country | machine missed；同一过滤列 |
| synth-case-010 | count(*) | concert.year | machine missed；Year 过滤决定标量 count |
| synth-case-010 | bucket | concert.year | machine missed（仅静态建议）；count 0->1 使 nonpos->pos |
| synth-case-007 | bucket | stadium.capacity | machine missed（仅静态建议）；把一格压到 -1e6 拉低 AVG<0，bucket 翻转 |
| synth-case-005 | count(*) | singer.country | machine missed；组合并/拆分改变各组计数 |
| synth-case-005 | bucket | singer.country | 参考建议漏掉（仅静态建议有）；单成员组消失时该 bucket 行消失，多重集改变 |

### machine absent & gold NEGATIVE

| qid | output | source | note |
|---|---|---|---|
| validation-00262 | name | employee.age | 只有 ORDER BY、没有 LIMIT：行序不在多重集里，输出不变 |
| synth-case-018 | bucket | pets.pet_age | pet_age 只改选哪一行，而 D 上所有权重>0，bucket 恒为 'pos' |

### machine absent & gold UNKNOWN

| qid | output | source | note |
|---|---|---|---|
| validation-00174 | countryname | countries.countryid | machine missed；D 上 REAL 的 countryId 与 TEXT 的 Car_Makers.Country 永不相等，无见证；语义上该边成立 |
| validation-00031 | name | stadium.stadium_id | machine missed；D 上 REAL 的 Stadium_ID 与 TEXT 的 concert.Stadium_ID 恒不匹配，单格扰动无见证 |
| validation-00031 | name | concert.stadium_id | machine missed；要同时满足“id 匹配”和 Year=2014，单格扰动在 D 上做不到 |
| validation-00031 | name | concert.year | machine missed；Year=2014 在 D 上无匹配且连接类型失效，不可观测 |
| synth-cte-004 | avg(age) | singer.age | machine missed（仅静态建议）；D 上 country='France' 无匹配，Age 怎么改聚合都保持 NULL |
| synth-cte-004 | min(age) | singer.age | machine missed（仅静态建议）；空过滤上的聚合 |
| synth-cte-004 | max(age) | singer.age | machine missed（仅静态建议）；空过滤上的聚合 |
