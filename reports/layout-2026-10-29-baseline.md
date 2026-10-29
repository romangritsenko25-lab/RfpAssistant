# Layout map on public questionnaires, 2026-10-29 (baseline)

Model for the layout call: `gpt-4o-mini`. Reference: derived from each file by ID patterns and table shapes, checked against `truth.json` counts. Numbers and cell addresses only: no question texts.
Threshold from the specification: at least 95% of the reference questions found.

Columns: `extra` counts "questions" outside the reference, split into rows on sheets that must not hold questions (repeat sheets) and other rows (section titles, info rows, duplicates). The three target columns count questions (or sheets for short answer, values and choice columns) that match the reference.

| file | mode | layout used | found / reference | extra: repeat sheets / other | question column | answer text target | short answer column / values | choice columns | cost, USD |
|---|---|---|---|---|---|---|---|---|---|
| csa-caiq-v3-1 | llm | error: InvalidInputError: Cannot find the question column: no header such as 'Question', 'Вопрос' or 'Сұрақ' in the first 10 rows. Specify the columns manually. | | | | | | | |
| csa-caiq-v3-1 | rules | error: InvalidInputError: Cannot find the question column: no header such as 'Question', 'Вопрос' or 'Сұрақ' in the first 10 rows. Specify the columns manually. | | | | | | | |
| csa-caiq-v4-1 | llm | rules (fallback) | 283/283 (100.0%, ok) | 0 / 0 | 283/283 | 283/283 | 0/1 / 0/1 | n/a | 0.0008 |
| csa-caiq-v4-1 | rules | rules | 283/283 (100.0%, ok) | 0 / 0 | 283/283 | 283/283 | 0/1 / 0/1 | n/a | 0.0000 |
| hecvat-lite-iu-mirror | llm | error: InvalidInputError: Cannot find the question column: no header such as 'Question', 'Вопрос' or 'Сұрақ' in the first 10 rows. Specify the columns manually. | | | | | | | |
| hecvat-lite-iu-mirror | rules | error: InvalidInputError: Cannot find the question column: no header such as 'Question', 'Вопрос' or 'Сұрақ' in the first 10 rows. Specify the columns manually. | | | | | | | |
| hecvat-4-16-github-mirror | llm | rules (fallback) | 0/334 (0.0%, BELOW) | 332 / 0 | n/a | n/a | 0/8 / 0/8 | n/a | 0.0029 |
| hecvat-4-16-github-mirror | rules | rules | 0/334 (0.0%, BELOW) | 332 / 0 | n/a | n/a | 0/8 / 0/8 | n/a | 0.0000 |
| txdot-security-questionnaire | llm | rules (fallback) | 79/80 (98.8%, ok) | 0 / 29 | 79/79 | 0/79 | n/a / n/a | n/a | 0.0054 |
| txdot-security-questionnaire | rules | rules | 79/80 (98.8%, ok) | 0 / 29 | 79/79 | 0/79 | n/a / n/a | n/a | 0.0000 |
| ca-cdt-rfi-managed-security | llm | rules (fallback) | 11/11 (100.0%, ok) | 0 / 21 | 11/11 | 11/11 | n/a / n/a | n/a | 0.0106 |
| ca-cdt-rfi-managed-security | rules | rules | 11/11 (100.0%, ok) | 0 / 21 | 11/11 | 11/11 | n/a / n/a | n/a | 0.0000 |
| ut-system-3rd-party-intake | llm | rules (fallback) | 13/16 (81.2%, BELOW) | 0 / 1 | 13/13 | n/a | n/a / n/a | n/a | 0.0009 |
| ut-system-3rd-party-intake | rules | rules | 13/16 (81.2%, BELOW) | 0 / 1 | 13/13 | n/a | n/a / n/a | n/a | 0.0000 |

Total, mode `llm`: 386/724 (53.3%); files at or above 95%: 3 of 5.
Total, mode `rules`: 386/724 (53.3%); files at or above 95%: 3 of 5.

Model calls: 7, cost 0.0205 USD.
