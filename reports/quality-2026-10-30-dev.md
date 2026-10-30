# Quality report: dev set, 2026-10-30

- Set: `dev`, version (SHA-256 of gold.jsonl, first 12 chars): `3a621ad4b6f2`
- Questions: 55 (44 answerable, 11 without an answer)
- Answer model: `gpt-4o-mini`; judge model: `gpt-4o`; embeddings: `text-embedding-3-small`
- Retrieval: top-k 8; confidence threshold 0.5

## Acceptance metrics

| Metric | Result | Threshold (terms of reference, section 9) |
|---|---|---|
| Correct answers | 75.0% | at least 75% |
| Partially correct | 22.7% | not specified |
| Incorrect answers | 2.3% | at most 10% |
| Not judged (judge reply invalid) | 0.0% | 0% |
| Answers with a source | 100.0% | at least 95% |
| Cited answers with a gold document as source | 95.5% | at least 90% |
| Citations pointing at a gold document | 77.5% | for reference |
| Refusal recall (`no_data` on unanswerable) | 90.9% (10/11) | at least 90% (18 of 20) |
| Refusal precision | 100.0% | for reference |
| Questions found when parsing the source files | 100.0% (55/55) | at least 95% |
| Time per question | 4.6 s | 100 questions in 15 min (9 s each) |
| Retrieval hit (gold document among retrieved) | 95.5% | for reference |

Accuracy is judged by an LLM against the reference answer; the sample below is for manual checking. A refusal on an answerable question counts as incorrect. Thresholds apply to the full 100-question test set; a dev set is smaller, so its figures are indicative.

## Cost and usage

- Tokens (answer generation, judge excluded): 90692 prompt, 8898 completion
- Cost: $0.0189 total, $0.0003 per question, $0.0344 per 100 questions
- Judge (separate, not part of the service cost): 20386 prompt, 1220 completion tokens, $0.0632
- Total time: 255 s
- Citations rejected by the quote check: 0
- Prices come from a constant table in `rfp/llm.py`; verify them with the provider before quoting.

## Parsing of source files

- `questionnaire.xlsx`: 40 of 40 questions found
- `rfp.docx`: 15 of 15 questions found

## Answers to review

- Q-011: verdict partial, status answered
- Q-017: no answer in the set, but status answered
- Q-024: verdict partial, status answered
- Q-025: verdict partial, status answered
- Q-026: verdict partial, status answered
- Q-030: verdict partial, status answered
- R-004: verdict partial, status answered
- R-005: verdict partial, status answered
- R-008: verdict partial, status answered
- R-009: verdict partial, status answered
- R-013: verdict partial, status answered
- R-014: verdict incorrect, status needs_review

## Manual sample (10 random pairs, seed 20261028)

### Q-003 (kk)

- Question: Қызметкер жұмыстан шыққанда оның қолжетімділігі қанша уақыт ішінде жойылады?
- Answer (answered, confidence 1.00): Қызметкер жұмыстан шыққанда оның қолжетімділігі 4 сағат ішінде жойылады [8].
- Cited: SEC-001 / Жизненный цикл учётных записей
- Reference: Бұйрық шыққан сәттен бастап 4 сағаттан кешіктірмей.
- Judge: correct (The candidate states the key fact that availability is removed within 4 hours.)

### Q-014 (kk)

- Question: Инциденттен кейінгі талдау қандай мерзімде өткізіледі?
- Answer (answered, confidence 0.90): Инциденттен кейінгі талдау әрбір S1 және S2 инцидентінің жабылуынан кейін 5 жұмыс күні ішінде өткізіледі. Талдау есебінде уақыт шкаласы, негізгі себеп, түзету шаралары және мерзімдерімен жауапты тұлғалар қамтылады [1].
- Cited: SEC-005 / Post-incident activities
- Reference: S1 және S2 инциденті жабылғаннан кейін 5 жұмыс күні ішінде.
- Judge: correct (The candidate correctly states the analysis is conducted within 5 business days after S1 and S2 incidents are closed.)

### Q-036 (ru)

- Question: Есть ли у компании сертификат ISO/IEC 27001 и каков срок его действия?
- Answer (answered, confidence 1.00): Компания имеет сертификат ISO/IEC 27001:2022, который был выдан 12 ноября 2024 года и действителен до 11 ноября 2027 года. Область применения сертификата включает разработку и сопровождение программного обеспечения [1][4].
- Cited: CERT-001 / Сертификаты / row 2, CERT-002 / Certification
- Reference: Да. Сертификат ISO/IEC 27001:2022 выдан 12.11.2024 и действует до 11.11.2027.
- Judge: correct (The candidate provides the correct certification details and validity period.)

### Q-038 (ru)

- Question: Какие сертификаты находятся в процессе получения?
- Answer (answered, confidence 0.90): В процессе получения находятся следующие сертификаты: ISO/IEC 20000-1:2018, аудит которого запланирован на 2 квартал 2027 года [1][3]; ISO/IEC 27701:2019, аудит которого запланирован на 4 квартал 2027 года [2][3].
- Cited: CERT-001 / Сертификаты / row 4, CERT-001 / Сертификаты / row 5, CERT-003 / Процесте тұрған сертификаттар
- Reference: ISO/IEC 20000-1:2018 (аудит запланирован на 2 квартал 2027 года) и ISO/IEC 27701:2019 (4 квартал 2027 года).
- Judge: correct (The candidate includes both certificates and their audit timelines as in the reference.)

### Q-040 (en)

- Question: What service credit applies if monthly availability is between 95.0% and 99.0%?
- Answer (answered, confidence 0.90): If the monthly availability is between 95.0% and 99.0%, the service credit applies as 15% of the monthly payment [1]. The maximum amount of the credit for one month does not exceed 30% of the monthly payment [1].
- Cited: SLA-004 / Кредит мөлшері, SLA-004 / Кредит мөлшері
- Reference: A credit of 15% of the monthly fee; the credit is capped at 30% of the monthly fee.
- Judge: correct (The candidate matches the reference on the service credit details.)

### R-004 (ru)

- Question: Укажите гарантированный уровень доступности для тарифа Premium и порядок компенсаций за его нарушение.
- Answer (answered, confidence 0.70): Гарантированный уровень доступности для тарифа Premium составляет 99,9% в месяц [1]. Порядок компенсаций за нарушение этого уровня доступности не указан в предоставленных фрагментах, поэтому информация о компенсациях отсутствует [1].
- Cited: SLA-001 / Доступность
- Reference: 99,9% в месяц. При нарушении предоставляются сервисные кредиты (5%, 15% или 30% месячного платежа в зависимости от фактической доступности), не более 30%.
- Judge: partial (The candidate correctly states the availability level but misses the compensation details.)

### R-005 (ru)

- Question: Опишите организацию технической поддержки: линии, часы работы, языки обращения.
- Answer (answered, confidence 1.00): Организация технической поддержки включает три линии: первая линия (L1) — сервисный центр с 9 специалистами, работающий с понедельника по пятницу с 9:00 до 18:00 (UTC+5) [1][2]; вторая линия (L2) — инженеры сопровождения с 7 специалистами, работающие в те же часы, с дежурством 24x7 для тарифов Premium и Enterprise [3][6]; третья линия (L3) — разработчики и архитекторы проекта с 4 специалистами, работающие по графику проекта и дежурящие по P1 для Premium и Enterprise [7]. Обращения принимаются через портал поддержки, по электронной почте и по телефону, при этом обращения приоритета P1 принимаются только по телефону и через портал [4][5]. Языки общения — русский, казахский или английский по выбору заказчика [4].
- Cited: SUP-004 / Уровни поддержки / row 2, SUP-001 / Уровни поддержки, SUP-004 / Уровни поддержки / row 3, SUP-001 / Каналы обращения, SUP-001 / Часы работы, SUP-004 / Уровни поддержки / row 4, SUP-001 / Каналы обращения
- Reference: Три линии (L1–L3), 20 специалистов. Стандартная поддержка пн–пт 9:00–18:00 (UTC+5); для Premium и Enterprise 24x7 по P1 и P2. Языки — русский, казахский, английский.
- Judge: partial (The candidate provides detailed information about the support lines and languages but is vague about the 24x7 support for P1 and P2 issues.)

### R-007 (ru)

- Question: Приведите почасовые ставки специалистов по ролям (разработчик, тестировщик, DevOps-инженер).
- Answer (no_data, confidence 0.00): В предоставленных фрагментах отсутствуют почасовые ставки специалистов по ролям (разработчик, тестировщик, DevOps-инженер).
- Cited: none
- Reference: no answer in the knowledge base
- Judge: unjudged

### R-010 (en)

- Question: Describe the measures protecting data in transit and at rest.
- Answer (answered, confidence 0.90): Data in transit is protected using TLS protocols, with a minimum version of 1.2 and a preferred version of 1.3. Outdated protocols such as SSL 3.0, TLS 1.0, and TLS 1.1 are disabled. Internal traffic between services in Kubernetes is secured with mutual TLS authentication (mTLS) [2]. Data at rest is encrypted using the AES-256 algorithm in production databases, file storage, and backups. Transparent encryption is utilized at the storage level for PostgreSQL and Oracle databases. Disk encryption is mandatory on all employee laptops [1]. Additionally, all backups are encrypted with AES-256 and are stored securely, with daily full backups and hourly incremental backups [8]. The encryption keys are managed in a key management service (KMS) with hardware security modules (HSM), and master keys are rotated every 12 months [4].
- Cited: SEC-002 / Шифрование данных при передаче, SEC-002 / Шифрование данных при хранении, SEC-003 / Расписание и хранение, SEC-002 / Управление ключами
- Reference: At rest: AES-256 encryption with keys in a KMS/HSM. In transit: TLS 1.2 or higher (TLS 1.3 preferred), mTLS between internal services.
- Judge: correct (The candidate includes all key facts about data protection in transit and at rest.)

### R-011 (en)

- Question: State the total number of employees and their distribution by role.
- Answer (answered, confidence 1.00): The total number of employees at StepLight Technologies is 160 developers, 30 QA engineers, 28 DevOps and SRE engineers, 22 data and AI specialists, 20 support staff, and 20 management, sales, and administrative personnel, totaling 280 employees. The distribution by role is as follows: Developers: 160 [2], QA Engineers: 30 [5], DevOps and SRE Engineers: 28 [1], Data and AI Specialists: 22 [2], Support Staff: 20 [7], Management, Sales, and Administrative Personnel: 20 [2].
- Cited: ORG-001 / Состав команды, SVC-003 / Қызмет бағыттары, SVC-004 / Состав направления, SUP-001 / Уровни поддержки
- Reference: 280 employees as of 1 January 2026: 160 developers, 30 QA, 28 DevOps/SRE, 22 data and AI, 20 support, 20 management and administration.
- Judge: correct (The candidate provides the correct total number of employees and their distribution by role.)
