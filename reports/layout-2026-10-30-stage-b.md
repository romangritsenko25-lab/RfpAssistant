# Layout map on public questionnaires, 2026-10-30 (stage-b)

Model for the layout call: `gpt-4o-mini`. Reference: derived from each file by ID patterns and table shapes, checked against `truth.json` counts. Numbers and cell addresses only: no question texts.
Threshold from the specification: at least 95% of the reference questions found.

Columns: `extra` counts "questions" outside the reference, split into rows on sheets that must not hold questions (repeat sheets) and other rows (section titles, info rows, duplicates). The three target columns count questions (or sheets for short answer, values and choice columns) that match the reference.

| file | mode | layout used | found / reference | extra: repeat sheets / other | question column | answer text target | short answer column / values | choice columns | cost, USD |
|---|---|---|---|---|---|---|---|---|---|
| csa-caiq-v3-1 | llm | llm | 296/308 (96.1%, ok) | 0 / 2 | 296/296 | 296/296 | n/a / n/a | 0/1 | 0.0011 |
| csa-caiq-v4-1 | llm | llm | 283/283 (100.0%, ok) | 0 / 0 | 283/283 | 283/283 | 1/1 / 1/1 | n/a | 0.0010 |
| hecvat-lite-iu-mirror | llm | llm | 62/64 (96.9%, ok) | 0 / 16 | 62/62 | 0/62 | 1/1 / 0/1 | n/a | 0.0012 |
| hecvat-4-16-github-mirror | llm | llm | 235/334 (70.4%, BELOW) | 0 / 0 | 235/235 | 0/235 | 8/8 / 7/8 | n/a | 0.0033 |
| txdot-security-questionnaire | llm | rules (fallback) | 79/80 (98.8%, ok) | 0 / 29 | 79/79 | 0/79 | n/a / n/a | n/a | 0.0078 |
| ca-cdt-rfi-managed-security | llm | rules (fallback) | 11/11 (100.0%, ok) | 0 / 21 | 11/11 | 11/11 | n/a / n/a | n/a | 0.0011 |
| ut-system-3rd-party-intake | llm | rules (fallback) | 13/16 (81.2%, BELOW) | 0 / 1 | 13/13 | n/a | n/a / n/a | n/a | 0.0008 |

Total, mode `llm`: 979/1096 (89.3%); files at or above 95%: 5 of 7.

Model calls: 9, cost 0.0163 USD.
