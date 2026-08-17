# RFE strategy bootstrap instructions

EXECUTE THIS TASK NOW. Do not describe the uploaded prompt, ask what the user wants, offer options, or wait for another instruction. Your only response must be the completed JSON object.

You are not drafting the final RFE response in this step. You are converting a human strategy memo, the full RFE notice, the company Word template, and the company YAML instructions into a durable machine-readable case plan that the script will immediately use to build a substantially populated working response.

Rules:

1. Preserve the substance of the human strategy. Do not silently weaken, generalize, or replace it.
2. `exact_rfe_quote` is a verbatim field, not a summary. If the human strategy quotes an RFE passage, reproduce that passage in full, word for word, including all sentences quoted in the strategy. Never shorten it to one sentence. If the strategy visibly abbreviates a passage but identifies it clearly, recover the complete corresponding adverse-reasoning passage from the full RFE. Do not paraphrase, silently correct, or modernize quoted wording; only remove obvious OCR line-break/hyphenation artifacts.
3. Extract all available case metadata from the RFE, including the signer/officer or office chief. Use an empty string only when a field is genuinely unavailable. Set `salutation` to a ready-to-insert company-style salutation such as `Dear Ms. Carrie M. Selby and Officer:` when supported, otherwise `Dear Officer:`. Do not invent dates, receipt numbers, names, addresses, or petition facts; put genuine uncertainty in `open_questions`.
4. Decide the response structure from the actual RFE and strategy. Do not add continued-work, substantial-benefit, general-response, or final-merits sections mechanically when they are not needed.
5. Use these criterion role IDs when applicable: `awards`, `memberships`, `media`, `judging`, `original_contribution`, `scholarly_articles`, `exhibitions`, `leading_critical_role`, `high_salary`, `commercial_success`.
6. One criterion can have several episodes. Give each episode a stable unique `episode_id`, a filing-ready descriptive title, the expected evidence folder in `source_folder`, and concrete `planned_subheadings` that directly answer the disputed elements. For example: `2. Associations/IEEE` or `8. Leading Critical Role/Retriever`.
7. A non-criterion section may have no episodes. The script will turn it into one drafting unit using its `section_id`.
8. `starter_text` must contain the maximum safe, useful pre-draft content that can already be inserted under the company template: procedural boilerplate, factual bridge text, or a concise criterion-specific setup supported by the RFE and strategy. Do not put unsupported advocacy there.
9. Every drafting section must identify its RFE issues and its specific response strategy. General strategy belongs in `global_strategy`; section/episode tactics belong in their respective fields.
10. Order sections strategically, not mechanically. Use consecutive positive integer `order` values.
11. Use the human Word template as the visual/structural authority and the YAML template as the drafting/assembly authority. The resulting sections must permit the script to build: a completed cover letter, exact RFE quote blocks, `Answer:` blocks, criterion headings, episode headings, planned rebuttal subheadings, final-merits/conclusion sections when triggered, and placeholders only where later evidence drafting is unavoidable.
12. Return only one valid JSON object matching the supplied schema. No Markdown fences and no commentary outside JSON. Begin with `{` and end with `}`. Before responding, verify strict JSON syntax: every double quote occurring inside a string (especially inside `exact_rfe_quote`) must be escaped as `\"`; literal line breaks inside strings must be encoded as `\n`; no trailing commas are permitted.
