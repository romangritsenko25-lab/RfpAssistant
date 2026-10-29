# Layout map on public questionnaires, 2026-10-29 (final)

Model for the layout call: `gpt-4o-mini`. Reference: derived from each file by ID patterns and table shapes, checked against `truth.json` counts. Numbers and cell addresses only: no question texts.
Threshold from the specification: at least 95% of the reference questions found.

Columns: `extra` counts "questions" outside the reference, split into rows on sheets that must not hold questions (repeat sheets) and other rows (section titles, info rows, duplicates). The three target columns count questions (or sheets for short answer, values and choice columns) that match the reference.

| file | mode | layout used | found / reference | extra: repeat sheets / other | question column | answer text target | short answer column / values | choice columns | cost, USD |
|---|---|---|---|---|---|---|---|---|---|
| csa-caiq-v3-1 | llm | llm | 296/308 (96.1%, ok) | 0 / 2 | 296/296 | 0/296 | n/a / n/a | 1/1 | 0.0009 |
| csa-caiq-v3-1 | rules | error: InvalidInputError: Cannot find the question column: no header such as 'Question', 'Вопрос' or 'Сұрақ' in the first 10 rows. Specify the columns manually. | | | | | | | |
| csa-caiq-v4-1 | llm | llm | 283/283 (100.0%, ok) | 0 / 0 | 283/283 | 283/283 | 1/1 / 1/1 | n/a | 0.0008 |
| csa-caiq-v4-1 | rules | rules | 283/283 (100.0%, ok) | 0 / 0 | 283/283 | 283/283 | 0/1 / 0/1 | n/a | 0.0000 |
| hecvat-lite-iu-mirror | llm | llm | 62/64 (96.9%, ok) | 0 / 16 | 62/62 | 0/62 | 1/1 / 0/1 | n/a | 0.0012 |
| hecvat-lite-iu-mirror | rules | error: InvalidInputError: Cannot find the question column: no header such as 'Question', 'Вопрос' or 'Сұрақ' in the first 10 rows. Specify the columns manually. | | | | | | | |
| hecvat-4-16-github-mirror | llm | llm | 222/334 (66.5%, BELOW) | 0 / 0 | 222/222 | 0/222 | 7/8 / 0/8 | n/a | 0.0031 |
| hecvat-4-16-github-mirror | rules | rules | 0/334 (0.0%, BELOW) | 332 / 0 | n/a | n/a | 0/8 / 0/8 | n/a | 0.0000 |
| txdot-security-questionnaire | llm | rules (fallback) | 79/80 (98.8%, ok) | 0 / 29 | 79/79 | 0/79 | n/a / n/a | n/a | 0.0060 |
| txdot-security-questionnaire | rules | rules | 79/80 (98.8%, ok) | 0 / 29 | 79/79 | 0/79 | n/a / n/a | n/a | 0.0000 |
| ca-cdt-rfi-managed-security | llm | rules (fallback) | 11/11 (100.0%, ok) | 0 / 21 | 11/11 | 11/11 | n/a / n/a | n/a | 0.0033 |
| ca-cdt-rfi-managed-security | rules | rules | 11/11 (100.0%, ok) | 0 / 21 | 11/11 | 11/11 | n/a / n/a | n/a | 0.0000 |
| ut-system-3rd-party-intake | llm | rules (fallback) | 13/16 (81.2%, BELOW) | 0 / 1 | 13/13 | n/a | n/a / n/a | n/a | 0.0009 |
| ut-system-3rd-party-intake | rules | rules | 13/16 (81.2%, BELOW) | 0 / 1 | 13/13 | n/a | n/a / n/a | n/a | 0.0000 |

Total, mode `llm`: 966/1096 (88.1%); files at or above 95%: 5 of 7.
Total, mode `rules`: 386/724 (53.3%); files at or above 95%: 3 of 5.

Model calls: 9, cost 0.0163 USD.

## Against the baseline

| file | mode | found before | found after | extra before | extra after |
|---|---|---|---|---|---|
| csa-caiq-v3-1 | llm | no result (error) | 296/308 | - | 2 |
| csa-caiq-v3-1 | rules | no result (error) | no result (error) | - | - |
| csa-caiq-v4-1 | llm | 283/283 | 283/283 | 0 | 0 |
| csa-caiq-v4-1 | rules | 283/283 | 283/283 | 0 | 0 |
| hecvat-lite-iu-mirror | llm | no result (error) | 62/64 | - | 16 |
| hecvat-lite-iu-mirror | rules | no result (error) | no result (error) | - | - |
| hecvat-4-16-github-mirror | llm | 0/334 | 222/334 | 332 | 0 |
| hecvat-4-16-github-mirror | rules | 0/334 | 0/334 | 332 | 332 |
| txdot-security-questionnaire | llm | 79/80 | 79/80 | 29 | 29 |
| txdot-security-questionnaire | rules | 79/80 | 79/80 | 29 | 29 |
| ca-cdt-rfi-managed-security | llm | 11/11 | 11/11 | 21 | 21 |
| ca-cdt-rfi-managed-security | rules | 11/11 | 11/11 | 21 | 21 |
| ut-system-3rd-party-intake | llm | 13/16 | 13/16 | 1 | 1 |
| ut-system-3rd-party-intake | rules | 13/16 | 13/16 | 1 | 1 |
