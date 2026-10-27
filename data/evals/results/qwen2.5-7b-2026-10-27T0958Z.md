# Hồ Sơ AI evaluation: `qwen2.5:7b`

Run: 2026-10-27T0958Z

## routing

| metric | value |
|---|---|
| cases | 66 |
| accuracy_in_scope_pct | 95.8 |
| correct_not_found_pct | 92.9 |
| wrong_procedure_on_out_of_scope | 1 |
| missed_in_scope_as_not_found | 1 |
| adversarial_correct | 4/4 |
| model_invented_slugs | 1 |
| invented_slugs_shown_to_user | 0 |
| invalid_json_replies | 0 |
| by_category | {"adversarial": "4/4", "ambiguous": "4/4", "direct": "20/20", "off_topic": "3/3", "out_of_scope": "10/11", "paraphrase": "22/24"} |
| by_language_in_scope | {"en": "17/17", "fr": "5/5", "ko": "1/2", "vi": "22/23", "zh": "1/1"} |
| latency_median_s | 0.24 |
| latency_p95_s | 0.32 |

## fees_vs_plain_chatbot

| metric | value |
|---|---|
| procedures | 17 |
| chatbot_gave_an_amount | 13 |
| chatbot_amount_not_in_official_source | 13 |
| chatbot_unsupported_pct_of_answers_with_amount | 100.0 |
| hosoai_amounts_not_in_source | 0 |

## agent

| metric | value |
|---|---|
| conversations | 50 |
| ended_with_dossier | 49 |
| avg_questions | 0.76 |
| model_mistakes_caught_by_guardrails | 144 |
| mistakes_by_type | {"unsupported_exclusion": 108, "invented_answer_ref": 34, "invalid_status": 1, "invalid_json": 1} |
| documents_shown_verbatim_from_source_pct | 100.0 |
| avg_seconds_per_conversation | 3.7 |
