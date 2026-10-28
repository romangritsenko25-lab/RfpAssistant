# Tuning log (dev set `3a621ad4b6f2`, answer model gpt-4o-mini, judge gpt-4o)

Tuning uses the dev set only. Columns: C = correct, P = partial, I = incorrect (% of judged-or-refused answerable
questions, 44 of 55), Src = answers with a source, Conf = cited answers with a gold document, RR/RP = refusal
recall/precision, Hit = retrieval hit, s/q = time per question, $/100 = answer cost per 100 questions
(the translation call is not included; see Notes).

| # | Date | Change | C | P | I | Src | Conf | RR | RP | Hit | s/q | $/100 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-10-28 | Baseline: top-k 5, 20 candidates per search, no translation | 31.8 | 25.0 | 43.2 | 75.0 | 81.8 | 90.9 | 47.6 | 63.6 | 2.2 | 0.023 |
| 1 | 2026-10-28 | Question translated to ru/kk/en (one gpt-4o-mini call), FTS + vector search per variant, all merged by RRF; top-k 8; 30 candidates per search | 63.6 | 29.5 | 6.8 | 97.7 | 95.3 | 90.9 | 90.9 | 95.5 | 4.7 | 0.027 |
| 2 | 2026-10-28 | Prompt: answer in question language, completeness (caps, exceptions, conditions), partial data answered instead of refused, conflicts to needs_review | 77.3 | 18.2 | 4.5 | 97.7 | 95.3 | 72.7 | 88.9 | 95.5 | 5.7 | 0.031 |
| 3 | 2026-10-28 | Prompt: refusal decided by the central fact asked for; no negative claims from silence (final configuration) | 75.0 | 18.2 | 6.8 | 97.7 | 95.3 | 90.9 | 90.9 | 95.5 | 5.3 | 0.031 |
| 4 | 2026-10-28 | Same as 3 with top-k 10 (RETRIEVAL_TOP_K=10), not adopted: no gain, higher cost | 75.0 | 18.2 | 6.8 | 97.7 | 95.3 | 90.9 | 90.9 | 95.5 | 4.9 | 0.034 |

## Notes

- Run 1: the baseline failures were almost all kk and en questions whose answer lives in a ru document (full-text
  search with the 'simple' configuration cannot match across languages; embeddings were weak on kk). Translating the
  question and searching every variant lifted the retrieval hit from 63.6% to 95.5% and nearly everything with it.
- Run 2: raised correct answers but broke refusal recall (72.7%, below the 90% threshold): the partial-data rule made
  the model answer questions whose central fact is absent, once with a negative claim inferred from silence. Reverted
  to a central-fact criterion in run 3.
- Run 3 is the final configuration. Correct answers sit exactly on the 75% threshold (33 of 44): a margin of zero
  on a 44-question sample. Remaining non-correct answers are incomplete answers (an omitted secondary detail),
  two conflicts reported with several values (judged incorrect), one refusal on a compound question, and one
  unanswerable question (named-organisation) answered from a related fragment.
- Run 4 changed only the environment variable; the reports in `reports/` are from run 3.
- Translation cost is not in the report totals; estimated at about $0.007 per 100 questions (about 200 tokens per call).
