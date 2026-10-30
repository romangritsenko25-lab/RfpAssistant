# Quality report: dev set, 2026-10-30

- Set: `dev`, version (SHA-256 of gold.jsonl, first 12 chars): `3a621ad4b6f2`
- Questions: 55 (44 answerable, 11 without an answer)
- Answer model: `gpt-4o-mini`; judge model: `gpt-4o`; embeddings: `text-embedding-3-small`
- Retrieval: top-k 8; confidence threshold 0.5

## Acceptance metrics

| Metric | Result | Threshold (terms of reference, section 9) |
|---|---|---|
| Correct answers | 77.3% | at least 75% |
| Partially correct | 18.2% | not specified |
| Incorrect answers | 4.5% | at most 10% |
| Not judged (judge reply invalid) | 0.0% | 0% |
| Answers with a source | 100.0% | at least 95% |
| Cited answers with a gold document as source | 95.5% | at least 90% |
| Citations pointing at a gold document | 78.5% | for reference |
| Refusal recall (`no_data` on unanswerable) | 90.9% (10/11) | at least 90% (18 of 20) |
| Refusal precision | 100.0% | for reference |
| Questions found when parsing the source files | 100.0% (55/55) | at least 95% |
| Time per question | 5.4 s | 100 questions in 15 min (9 s each) |
| Retrieval hit (gold document among retrieved) | 95.5% | for reference |

Accuracy is judged by an LLM against the reference answer; the sample below is for manual checking. A refusal on an answerable question counts as incorrect. Thresholds apply to the full 100-question test set; a dev set is smaller, so its figures are indicative.

## Cost and usage

- Tokens (answer generation, judge excluded): 88252 prompt, 8991 completion
- Cost: $0.0186 total, $0.0003 per question, $0.0339 per 100 questions
- Judge (separate, not part of the service cost): 20555 prompt, 1223 completion tokens, $0.0636
- Total time: 295 s
- Citations rejected by the quote check: 0
- Prices come from a constant table in `rfp/llm.py`; verify them with the provider before quoting.

## Parsing of source files

- `questionnaire.xlsx`: 40 of 40 questions found
- `rfp.docx`: 15 of 15 questions found

## Answers to review

- Q-017: no answer in the set, but status answered
- Q-024: verdict partial, status answered
- Q-026: verdict partial, status answered
- Q-030: verdict partial, status answered
- R-003: verdict incorrect, status needs_review
- R-004: verdict partial, status answered
- R-008: verdict partial, status answered
- R-009: verdict partial, status answered
- R-011: verdict incorrect, status answered
- R-013: verdict partial, status answered
- R-014: verdict partial, status needs_review

## Manual sample (10 random pairs, seed 20261028)

### Q-003 (kk)

- Question: Қызметкер жұмыстан шыққанда оның қолжетімділігі қанша уақыт ішінде жойылады?
- Answer (answered, confidence 1.00): Қызметкер жұмыстан шыққанда оның қолжетімділігі 4 сағат ішінде жойылады [8].
- Cited: SEC-001 / Жизненный цикл учётных записей
- Reference: Бұйрық шыққан сәттен бастап 4 сағаттан кешіктірмей.
- Judge: correct (The candidate states the key fact that access is removed within 4 hours, which matches the reference.)

### Q-014 (kk)

- Question: Инциденттен кейінгі талдау қандай мерзімде өткізіледі?
- Answer (answered, confidence 0.90): Анализ инцидента проводится в течение 5 рабочих дней после закрытия каждого инцидента уровня S1 и S2. Отчет об анализе включает временные рамки, коренные причины, корректирующие действия и ответственных с установленными сроками [1].
- Cited: SEC-005 / Post-incident activities
- Reference: S1 және S2 инциденті жабылғаннан кейін 5 жұмыс күні ішінде.
- Judge: correct (The candidate correctly states the analysis is conducted within 5 working days after closing S1 and S2 incidents.)

### Q-036 (ru)

- Question: Есть ли у компании сертификат ISO/IEC 27001 и каков срок его действия?
- Answer (answered, confidence 1.00): Да, у компании есть сертификат ISO/IEC 27001:2022, который был выдан 12 ноября 2024 года и действителен до 11 ноября 2027 года. Область применения сертификата включает разработку и сопровождение программного обеспечения [1][4].
- Cited: CERT-001 / Сертификаты / row 2, CERT-002 / Certification
- Reference: Да. Сертификат ISO/IEC 27001:2022 выдан 12.11.2024 и действует до 11.11.2027.
- Judge: correct (The candidate provides the correct certification details and validity period.)

### Q-038 (ru)

- Question: Какие сертификаты находятся в процессе получения?
- Answer (answered, confidence 0.90): В процессе получения находятся следующие сертификаты: ISO/IEC 20000-1:2018, аудит которого запланирован на 2 квартал 2027 года [1][3]; ISO/IEC 27701:2019, аудит которого запланирован на 4 квартал 2027 года [2][3]. Эти сертификаты пока не получены [3].
- Cited: CERT-001 / Сертификаты / row 4, CERT-001 / Сертификаты / row 5, CERT-003 / Процесте тұрған сертификаттар
- Reference: ISO/IEC 20000-1:2018 (аудит запланирован на 2 квартал 2027 года) и ISO/IEC 27701:2019 (4 квартал 2027 года).
- Judge: correct (The candidate includes all key facts about the certificates and audit timelines.)

### Q-040 (en)

- Question: What service credit applies if monthly availability is between 95.0% and 99.0%?
- Answer (answered, confidence 0.90): Если месячная доступность составляет от 95,0% до 99,0%, применяется сервисный кредит в размере 15% от месячного платежа. Максимальный размер кредита за один месяц не может превышать 30% от месячного платежа [1].
- Cited: SLA-004 / Кредит мөлшері
- Reference: A credit of 15% of the monthly fee; the credit is capped at 30% of the monthly fee.
- Judge: correct (The candidate correctly states the 15% credit and the 30% cap.)

### R-004 (ru)

- Question: Укажите гарантированный уровень доступности для тарифа Premium и порядок компенсаций за его нарушение.
- Answer (answered, confidence 0.60): Гарантированный уровень доступности для тарифа Premium составляет 99,9% в месяц [1]. В случае нарушения этого уровня доступности, порядок компенсаций не указан в предоставленных фрагментах, поэтому информация о компенсациях отсутствует [2].
- Cited: SLA-001 / Доступность, SLA-001 / Предмет соглашения
- Reference: 99,9% в месяц. При нарушении предоставляются сервисные кредиты (5%, 15% или 30% месячного платежа в зависимости от фактической доступности), не более 30%.
- Judge: partial (The candidate correctly states the availability level but misses the compensation details.)

### R-005 (ru)

- Question: Опишите организацию технической поддержки: линии, часы работы, языки обращения.
- Answer (answered, confidence 1.00): Организация технической поддержки включает три линии: первая линия (L1) — сервисный центр с 9 специалистами, работающий с понедельника по пятницу с 9:00 до 18:00 (UTC+5) [1][2]; вторая линия (L2) — инженеры сопровождения с 7 специалистами, работающие в те же часы, с дежурством 24x7 для Premium и Enterprise [3][6]; третья линия (L3) — разработчики и архитекторы проекта с 4 специалистами, работающие по графику проекта, с дежурством по P1 для Premium и Enterprise [7]. Обращения принимаются через портал поддержки, по электронной почте и по телефону [4][5]. Языки общения — русский, казахский или английский по выбору заказчика [4]. Стандартная поддержка предоставляется с понедельника по пятницу с 9:00 до 18:00, кроме праздничных дней Республики Казахстан, а для тарифов Premium и Enterprise доступна расширенная поддержка 24x7 для обращений приоритета P1 и P2 [6].
- Cited: SUP-004 / Уровни поддержки / row 2, SUP-001 / Уровни поддержки, SUP-004 / Уровни поддержки / row 3, SUP-001 / Каналы обращения, SUP-001 / Каналы обращения, SUP-001 / Часы работы, SUP-004 / Уровни поддержки / row 4
- Reference: Три линии (L1–L3), 20 специалистов. Стандартная поддержка пн–пт 9:00–18:00 (UTC+5); для Premium и Enterprise 24x7 по P1 и P2. Языки — русский, казахский, английский.
- Judge: correct (The candidate includes all key facts about support lines, hours, and languages.)

### R-007 (ru)

- Question: Приведите почасовые ставки специалистов по ролям (разработчик, тестировщик, DevOps-инженер).
- Answer (no_data, confidence 0.00): В предоставленных фрагментах отсутствуют конкретные почасовые ставки специалистов по ролям (разработчик, тестировщик, DevOps-инженер). Однако указаны роли и количество специалистов в различных проектах. Например, в проекте для «КазАгроЛогист» работали 2 разработчика, 1 инженер по тестированию и 3 DevOps-инженера [1]. В проекте для «Сарыарка Финанс» участвовали 9 разработчиков, 4 инженера по тестированию и 2 DevOps-инженера [2]. В других фрагментах также упоминаются различные роли, но ставки не указаны. Таким образом, в базе знаний нет данных о почасовых ставках специалистов.
- Cited: none
- Reference: no answer in the knowledge base
- Judge: unjudged

### R-010 (en)

- Question: Describe the measures protecting data in transit and at rest.
- Answer (answered, confidence 0.90): Защита данных в состоянии покоя осуществляется с помощью шифрования алгоритмом AES-256 для данных в производственных базах данных, на файловых хранилищах и в резервных копиях [1]. Вся информация, включая резервные копии, также шифруется этим же алгоритмом [8]. Шифрование дисков обязательно на всех ноутбуках сотрудников [1].

Защита данных в процессе передачи реализуется с использованием TLS не ниже версии 1.2, предпочтительно версии TLS 1.3 для всех внешних подключений [2]. Устаревшие протоколы SSL 3.0, TLS 1.0 и TLS 1.1 отключены [2]. Внутренний трафик между сервисами в Kubernetes защищён взаимной аутентификацией TLS (mTLS) [2].
- Cited: SEC-002 / Шифрование данных при хранении, SEC-002 / Шифрование данных при передаче, SEC-002 / Шифрование данных при передаче, SEC-002 / Шифрование данных при передаче, SEC-003 / Расписание и хранение
- Reference: At rest: AES-256 encryption with keys in a KMS/HSM. In transit: TLS 1.2 or higher (TLS 1.3 preferred), mTLS between internal services.
- Judge: correct (The candidate includes all key facts about data protection in transit and at rest.)

### R-011 (en)

- Question: State the total number of employees and their distribution by role.
- Answer (answered, confidence 1.00): Общее количество сотрудников компании Степлайт Технолоджиз составляет 160 человек. Распределение по ролям следующее: Разработчики: 160 человек, Инженеры по тестированию (QA): 30 человек, DevOps и SRE-инженеры: 28 человек, Специалисты по данным и ИИ: 22 человека, Служба поддержки: 20 человек, Руководство, продажи и административный персонал: 20 человек [2].
- Cited: ORG-001 / Состав команды
- Reference: 280 employees as of 1 January 2026: 160 developers, 30 QA, 28 DevOps/SRE, 22 data and AI, 20 support, 20 management and administration.
- Judge: incorrect (The candidate states the total number of employees as 160, contradicting the reference's 280.)
