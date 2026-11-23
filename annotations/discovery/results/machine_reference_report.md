# machine suggestions vs gold (POSITIVE 口径)

| suggestion | 建议数 | 命中 POS | 命中 UNKNOWN | 命中 NEG | 不在 gold | precision | recall |
|---|---|---|---|---|---|---|---|
| reference_edges_suggestion | 76 | 76 | 0 | 0 | 0 | 1.0 | 0.8736 |
| static_edges_suggestion | 21 | 21 | 0 | 0 | 0 | 1.0 | 0.2414 |
| union(reference, static) | 79 | 79 | 0 | 0 | 0 | 1.0 | 0.908 |

gold POSITIVE 总数：87

## 两个机器建议都没给出的 POSITIVE 边

- synth-case-005: count(*) <- singer.country
- synth-case-010: count(*) <- concert.year
- synth-cte-004: avg(age) <- singer.country
- synth-cte-004: max(age) <- singer.country
- synth-cte-004: min(age) <- singer.country
- synth-cte-018: count(*) <- concert.year
- validation-00020: count(*) <- concert.year
- validation-00174: countryname <- car_makers.country
