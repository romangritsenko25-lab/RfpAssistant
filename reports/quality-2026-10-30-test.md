# Quality report: test set, 2026-10-30

- Set: `test`, version (SHA-256 of gold.jsonl, first 12 chars): `58926e1cc8cd`
- Questions: 53 (42 answerable, 11 without an answer)
- Answer model: `gpt-4o-mini`; judge model: `gpt-4o`; embeddings: `text-embedding-3-small`
- Retrieval: top-k 8; confidence threshold 0.5

## Acceptance metrics

| Metric | Result | Threshold (terms of reference, section 9) |
|---|---|---|
| Correct answers | 81.0% | at least 75% |
| Partially correct | 11.9% | not specified |
| Incorrect answers | 7.1% | at most 10% |
| Not judged (judge reply invalid) | 0.0% | 0% |
| Answers with a source | 95.2% | at least 95% |
| Cited answers with a gold document as source | 95.0% | at least 90% |
| Citations pointing at a gold document | 77.5% | for reference |
| Refusal recall (`no_data` on unanswerable) | 100.0% (11/11) | at least 90% (18 of 20) |
| Refusal precision | 84.6% | for reference |
| Questions found when parsing the source files | 100.0% (53/53) | at least 95% |
| Time per question | 4.7 s | 100 questions in 15 min (9 s each) |
| Retrieval hit (gold document among retrieved) | 95.2% | for reference |

Accuracy is judged by an LLM against the reference answer; the sample below is for manual checking. A refusal on an answerable question counts as incorrect. Thresholds apply to the full 100-question test set; a dev set is smaller, so its figures are indicative.

## Cost and usage

- Tokens (answer generation, judge excluded): 85971 prompt, 7898 completion
- Cost: $0.0176 total, $0.0003 per question, $0.0333 per 100 questions
- Judge (separate, not part of the service cost): 18633 prompt, 1148 completion tokens, $0.0581
- Total time: 249 s
- Citations rejected by the quote check: 1
- Prices come from a constant table in `rfp/llm.py`; verify them with the provider before quoting.

## Parsing of source files

- `questionnaire.xlsx`: 40 of 40 questions found
- `rfp.docx`: 13 of 13 questions found

## Answers to review

- Q-008: verdict partial, status answered
- Q-010: verdict partial, status needs_review
- Q-018: verdict partial, status answered
- Q-022: verdict incorrect, status no_data
- Q-023: verdict incorrect, status no_data
- R-002: verdict partial, status answered
- R-006: verdict incorrect, status answered
- R-010: verdict partial, status answered

## Manual sample (10 random pairs, seed 20261028)

### Q-003 (kk)

- Question: Өндірістік жүйелерге әкімшілік қолжетімділік қалай беріледі?
- Answer (answered, confidence 0.90): Өндірістік жүйелерге әкімшілік қолжетімділік PAM (привилегиялық қолжетімділікті басқару) жүйесі арқылы шектеулі уақытқа беріледі. Барлық привилегиялық сессиялар жазылады, жазбалар 12 ай бойы сақталады [1]. Доступ принципі бойынша ең төменгі құқықтар негізінде және жұмыс қажеттілігіне байланысты беріледі. Құқықтар рөлдер (RBAC) арқылы тағайындалады; жеке ерекшеліктер жүйе иесінің шешімімен рұқсат етіледі және өтінімде тіркеледі [2]. Доступ өтінім арқылы, тікелей басшының және жүйе иесінің келісімімен сұралады. Қызметкер жұмыстан шыққан жағдайда, барлық қолжетімділіктер 4 сағат ішінде қайтарылады [4].
- Cited: SEC-001 / Привилегированный доступ, SEC-001 / Принципы, SEC-001 / Жизненный цикл учётных записей
- Reference: Әкімшілік қолжетімділік артықшылықты қолжетімділікті басқару жүйесі (PAM) арқылы шектеулі уақытқа беріледі. Барлық артықшылықты сессиялар жазылады.
- Judge: correct (The candidate includes all key facts from the reference and adds extra details without contradiction.)

### Q-014 (en)

- Question: How quickly does the incident response team start triage of an S1 incident?
- Answer (answered, confidence 1.00): Команда реагирования на инциденты (CSIRT) начинает триаж инцидента уровня S1 в течение 30 минут после его обнаружения [1].
- Cited: SEC-005 / Severity levels
- Reference: Triage of an S1 incident starts within 30 minutes after detection.
- Judge: correct (The candidate states that triage starts within 30 minutes after detection, matching the reference.)

### Q-036 (ru)

- Question: Сколько мер Приложения А включено в Положение о применимости ISO/IEC 27001 и сколько из них неприменимы?
- Answer (answered, confidence 0.90): В Положении о применимости ISO/IEC 27001 указано 93 меры Приложения А, из которых 3 меры отмечены как неприменимые (физическая доставка носителей, системы вещания и разработка аппаратного обеспечения на заказ) [4].
- Cited: CERT-002 / Statement of Applicability
- Reference: Текущая версия Положения о применимости (4.2) включает 93 меры Приложения А, из них 3 помечены как неприменимые.
- Judge: correct (The candidate correctly states that there are 93 measures and 3 are inapplicable.)

### Q-038 (ru)

- Question: Какая месячная доступность гарантирована для тарифа Enterprise?
- Answer (answered, confidence 0.90): Гарантированная месячная доступность для тарифа Enterprise составляет 99,95% [3]. Плановые работы не учитываются при расчёте доступности, если о них заказчик уведомлён не менее чем за 5 дней и их суммарная длительность не превышает 4 часов в месяц для тарифа Enterprise [2].
- Cited: SLA-002 / Service tiers / row 2, SLA-003 / Жоспарлы жұмыстар
- Reference: Для тарифа Enterprise гарантирована месячная доступность 99,95%.
- Judge: correct (The candidate correctly states the guaranteed monthly availability of 99.95% for the Enterprise plan.)

### Q-040 (ru)

- Question: Используется ли система управления мобильными устройствами (MDM) для сотрудников?
- Answer (no_data, confidence 0.00): В предоставленных фрагментах нет информации о том, используется ли система управления мобильными устройствами (MDM) для сотрудников. Таким образом, база знаний не содержит данных по этому вопросу.
- Cited: none
- Reference: no answer in the knowledge base
- Judge: unjudged

### R-004 (ru)

- Question: Опишите порядок эскалации инцидента приоритета P1.
- Answer (answered, confidence 1.00): Порядок эскалации инцидента приоритета P1 следующий: если в течение 30 минут не достигнут прогресс, инцидент эскалируется от первой линии к инженерам второй линии [1]. Если в течение 1 часа не найдено обходное решение, к инциденту присоединяется руководитель доставки [1]. Через 2 часа информируется главный технический директор (CTO), который берет на себя ответственность за коммуникацию с клиентом [1]. Во время инцидента P1 клиент получает обновления статуса каждые 30 минут до тех пор, пока не будет найдено обходное решение, и каждые 2 часа после этого [2]. Первая реакция на обращение приоритета P1 должна быть предоставлена в течение 15 минут [3], а для тарифа Premium время реакции на P1 отсчитывается круглосуточно [4]. Обращения приоритета P1 принимаются только по телефону и через портал поддержки [8].
- Cited: SUP-002 / Escalation path for P1, SUP-002 / Escalation path for P1, SUP-002 / Escalation path for P1, SUP-002 / Customer communication, SUP-002 / Response targets, SLA-001 / Время реакции, SUP-001 / Каналы обращения
- Reference: Если за 30 минут нет прогресса, инцидент передаётся с первой линии инженерам второй линии. Через 1 час без обходного решения подключается руководитель поставки, через 2 часа информируется технический директор (CTO) и берёт на себя коммуникацию с заказчиком.
- Judge: correct (The candidate includes all key facts about the escalation process and does not contradict the reference.)

### R-005 (ru)

- Question: Укажите годовую выручку компании за последние три года.
- Answer (no_data, confidence 0.00): В базе знаний нет данных о годовой выручке компании за последние три года.
- Cited: none
- Reference: no answer in the knowledge base
- Judge: unjudged

### R-007 (en)

- Question: List the collaboration models you offer and the minimum size and term of a dedicated team.
- Answer (answered, confidence 1.00): Мы предлагаем три модели сотрудничества: фиксированная стоимость (Fixed Price) для проектов с чёткими требованиями, время и материалы (Time & Materials) для развивающихся продуктов и выделенная команда (Dedicated Team) для долгосрочного сотрудничества. Минимальный размер выделенной команды — 3 специалиста, минимальный срок — 6 месяцев [1].
- Cited: SVC-001 / Модели сотрудничества
- Reference: Three models: Fixed Price, Time & Materials and Dedicated Team. A dedicated team has at least 3 specialists and a minimum term of 6 months.
- Judge: correct (The candidate lists the same three models and the same minimum size and term for a dedicated team.)

### R-008 (en)

- Question: Provide the CVs of the proposed project manager and technical lead.
- Answer (no_data, confidence 0.00): В предоставленных фрагментах нет информации о резюме (CV) предложенного руководителя проекта и технического лидера. Таким образом, статус запроса: нет данных.
- Cited: none
- Reference: no answer in the knowledge base
- Judge: unjudged

### R-009 (kk)

- Question: Қазақстан азаматтарының жеке деректері қандай заңнамаға сәйкес өңделеді және жеке деректерді қорғауға жауапты тұлға тағайындалған ба?
- Answer (answered, confidence 1.00): Қазақстан азаматтарының жеке деректері Қазақстан Республикасының аумағындағы серверлерде сақталады [1]. Компания жеке деректерді Қазақстан Республикасының «О персональных данных и их защите» заңына сәйкес өңдейді [4]. Жеке деректерді қорғауға жауапты тұлға (DPO) тағайындалған [4].
- Cited: SLA-003 / Орналастыру, CERT-004 / Нормативная основа
- Reference: Деректер «Дербес деректер және оларды қорғау туралы» Қазақстан Республикасының Заңына сәйкес өңделеді. Жеке деректерді өңдеуді ұйымдастыруға жауапты тұлға (DPO) бас директордың бұйрығымен тағайындалған.
- Judge: correct (The candidate states the same law and confirms a DPO is appointed.)
