# Quality report: dev set, 2026-10-28

- Set: `dev`, version (SHA-256 of gold.jsonl, first 12 chars): `3a621ad4b6f2`
- Questions: 55 (44 answerable, 11 without an answer)
- Answer model: `gpt-4o-mini`; judge model: `gpt-4o`; embeddings: `text-embedding-3-small`
- Retrieval: top-k 8; confidence threshold 0.5

## Acceptance metrics

| Metric | Result | Threshold (terms of reference, section 9) |
|---|---|---|
| Correct answers | 75.0% | at least 75% |
| Partially correct | 18.2% | not specified |
| Incorrect answers | 6.8% | at most 10% |
| Not judged (judge reply invalid) | 0.0% | 0% |
| Answers with a source | 97.7% | at least 95% |
| Cited answers with a gold document as source | 95.3% | at least 90% |
| Citations pointing at a gold document | 79.5% | for reference |
| Refusal recall (`no_data` on unanswerable) | 90.9% (10/11) | at least 90% (18 of 20) |
| Refusal precision | 90.9% | for reference |
| Questions found when parsing the source files | 100.0% (55/55) | at least 95% |
| Time per question | 5.3 s | 100 questions in 15 min (9 s each) |
| Retrieval hit (gold document among retrieved) | 95.5% | for reference |

Accuracy is judged by an LLM against the reference answer; the sample below is for manual checking. A refusal on an answerable question counts as incorrect. Thresholds apply to the full 100-question test set; a dev set is smaller, so its figures are indicative.

## Cost and usage

- Tokens (answer generation, judge excluded): 80025 prompt, 8691 completion
- Cost: $0.0172 total, $0.0003 per question, $0.0313 per 100 questions
- Judge (separate, not part of the service cost): 20150 prompt, 1188 completion tokens, $0.0623
- Total time: 289 s
- Citations rejected by the quote check: 1
- Prices come from a constant table in `rfp/llm.py`; verify them with the provider before quoting.

## Parsing of source files

- `questionnaire.xlsx`: 40 of 40 questions found
- `rfp.docx`: 15 of 15 questions found

## Answers to review

- Q-017: no answer in the set, but status answered
- Q-024: verdict partial, status answered
- Q-025: verdict partial, status answered
- Q-026: verdict partial, status answered
- Q-030: verdict partial, status answered
- R-003: verdict incorrect, status needs_review
- R-004: verdict incorrect, status no_data
- R-008: verdict partial, status answered
- R-009: verdict partial, status answered
- R-011: verdict partial, status answered
- R-013: verdict partial, status answered
- R-014: verdict incorrect, status needs_review

## Manual sample (10 random pairs, seed 20261028)

### Q-003 (kk)

- Question: Қызметкер жұмыстан шыққанда оның қолжетімділігі қанша уақыт ішінде жойылады?
- Answer (answered, confidence 1.00): Қызметкер жұмыстан шыққанда оның қолжетімділігі 4 сағат ішінде жойылады [8].
- Cited: SEC-001 / Жизненный цикл учётных записей
- Reference: Бұйрық шыққан сәттен бастап 4 сағаттан кешіктірмей.
- Judge: correct (The candidate states the key fact that availability is removed within 4 hours, which matches the reference.)

### Q-014 (kk)

- Question: Инциденттен кейінгі талдау қандай мерзімде өткізіледі?
- Answer (answered, confidence 0.90): Анализ инцидента проводится в течение 5 рабочих дней после закрытия каждого инцидента уровня S1 и S2. Отчет об анализе включает временные рамки, коренные причины, корректирующие действия и ответственных с установленными сроками [1].
- Cited: SEC-005 / Post-incident activities
- Reference: S1 және S2 инциденті жабылғаннан кейін 5 жұмыс күні ішінде.
- Judge: correct (The candidate states the analysis is conducted within 5 working days after closing S1 and S2 incidents, matching the reference.)

### Q-036 (ru)

- Question: Есть ли у компании сертификат ISO/IEC 27001 и каков срок его действия?
- Answer (answered, confidence 1.00): Да, у компании есть сертификат ISO/IEC 27001:2022, который был выдан 12 ноября 2024 года и действителен до 11 ноября 2027 года [1][4].
- Cited: CERT-001 / Сертификаты / row 2, CERT-002 / Certification
- Reference: Да. Сертификат ISO/IEC 27001:2022 выдан 12.11.2024 и действует до 11.11.2027.
- Judge: correct (The candidate provides the same certification details and validity period as the reference.)

### Q-038 (ru)

- Question: Какие сертификаты находятся в процессе получения?
- Answer (answered, confidence 0.90): В процессе получения находятся следующие сертификаты: ISO/IEC 20000-1:2018, аудит запланирован на 2 квартал 2027 года [1]; ISO/IEC 27701:2019, аудит запланирован на 4 квартал 2027 года [2]. Эти сертификаты пока не получены [3].
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
- Answer (no_data, confidence 0.50): Гарантированный уровень доступности для тарифа Premium составляет 99,9% в месяц [1]. Порядок компенсаций за нарушение этого уровня доступности не указан в предоставленных фрагментах, поэтому информация о компенсациях отсутствует.
- Cited: none
- Reference: 99,9% в месяц. При нарушении предоставляются сервисные кредиты (5%, 15% или 30% месячного платежа в зависимости от фактической доступности), не более 30%.
- Judge: incorrect (refused with no_data)

### R-005 (ru)

- Question: Опишите организацию технической поддержки: линии, часы работы, языки обращения.
- Answer (answered, confidence 1.00): Техническая поддержка организована в три линии. Первая линия (L1) — сервисный центр, работающий с понедельника по пятницу с 9:00 до 18:00 (UTC+5) и состоящий из 9 специалистов. Основные задачи L1: приём, регистрация и классификация обращений, решение типовых вопросов [1][2]. Вторая линия (L2) — инженеры сопровождения, также работающие с понедельника по пятницу с 9:00 до 18:00, с дежурством 24x7 для тарифов Premium и Enterprise. В L2 7 специалистов, которые занимаются диагностикой и устранением инцидентов [3][2]. Третья линия (L3) — разработчики и архитекторы системы, работающие по графику проекта и дежурящие по P1 для Premium и Enterprise, всего 4 специалиста, занимающихся исправлением дефектов и доработками [7][2]. Обращения принимаются через портал поддержки, по электронной почте и по телефону. Язык общения — русский, казахский или английский по выбору заказчика [4]. Стандартная поддержка предоставляется с понедельника по пятницу с 9:00 до 18:00, кроме праздничных дней Республики Казахстан. Для тарифов Premium и Enterprise доступна расширенная поддержка 24x7 для обращений приоритета P1 и P2 [6].
- Cited: SUP-004 / Уровни поддержки / row 2, SUP-001 / Уровни поддержки, SUP-004 / Уровни поддержки / row 3, SUP-004 / Уровни поддержки / row 4, SUP-001 / Каналы обращения, SUP-001 / Часы работы
- Reference: Три линии (L1–L3), 20 специалистов. Стандартная поддержка пн–пт 9:00–18:00 (UTC+5); для Premium и Enterprise 24x7 по P1 и P2. Языки — русский, казахский, английский.
- Judge: correct (The candidate includes all key facts about support lines, hours, and languages.)

### R-007 (ru)

- Question: Приведите почасовые ставки специалистов по ролям (разработчик, тестировщик, DevOps-инженер).
- Answer (no_data, confidence 0.00): В предоставленных фрагментах отсутствуют почасовые ставки специалистов по ролям (разработчик, тестировщик, DevOps-инженер).
- Cited: none
- Reference: no answer in the knowledge base
- Judge: unjudged

### R-010 (en)

- Question: Describe the measures protecting data in transit and at rest.
- Answer (answered, confidence 0.90): Защита данных в состоянии покоя осуществляется с помощью шифрования алгоритмом AES-256 для данных в производственных базах данных, на файловых хранилищах и в резервных копиях [1]. Вся информация шифруется, включая резервные копии, которые хранятся в центре обработки данных в Астане и дублируются на съёмные носители, вывозимые в защищённое хранилище [6]. Полное резервное копирование выполняется ежедневно, а инкрементное — каждый час, с хранением ежедневных копий в течение 35 дней и ежемесячных — 12 месяцев [8]. Для защиты данных при передаче используется TLS не ниже версии 1.2, с предпочтением к версии TLS 1.3, при этом устаревшие протоколы отключены [2]. Внутренний трафик между сервисами в Kubernetes защищён взаимной аутентификацией TLS (mTLS) [2]. Ключи шифрования хранятся в сервисе управления ключами (KMS) с аппаратным модулем безопасности (HSM), и мастер-ключи ротируются один раз в 12 месяцев [4].
- Cited: SEC-002 / Шифрование данных при хранении, SEC-002 / Шифрование данных при передаче, SEC-004 / Место хранения, SEC-003 / Расписание и хранение, SEC-002 / Управление ключами
- Reference: At rest: AES-256 encryption with keys in a KMS/HSM. In transit: TLS 1.2 or higher (TLS 1.3 preferred), mTLS between internal services.
- Judge: correct (The candidate includes all key facts from the reference about data protection measures.)

### R-011 (en)

- Question: State the total number of employees and their distribution by role.
- Answer (answered, confidence 1.00): Общее количество сотрудников компании Степлайт Технолоджиз составляет 160 разработчиков, 30 инженеров по тестированию (QA), 28 DevOps и SRE-инженеров, 22 специалиста по данным и ИИ, 20 сотрудников службы поддержки и 20 человек руководства, продаж и административного персонала. Распределение по ролям: Разработчики: 160 человек [2]; Инженеры по тестированию (QA): 30 человек [2]; DevOps и SRE-инженеры: 28 человек [2]; Специалисты по данным и ИИ: 22 человека [2]; Служба поддержки: 20 человек [2]; Руководство, продажи и административный персонал: 20 человек [2].
- Cited: ORG-001 / Состав команды
- Reference: 280 employees as of 1 January 2026: 160 developers, 30 QA, 28 DevOps/SRE, 22 data and AI, 20 support, 20 management and administration.
- Judge: partial (The candidate lists the distribution by role correctly but omits the total number of employees.)
