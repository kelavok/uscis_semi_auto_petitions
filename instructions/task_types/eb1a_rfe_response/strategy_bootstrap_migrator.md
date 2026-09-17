# Migrator EB-1A RFE strategy bootstrap instructions

EXECUTE THIS TASK NOW. Return only the completed JSON object.

This is a planning and extraction step, not final RFE drafting. Read all three substantive sources in full: the RFE notice, the human strategy memorandum, and the initial-filing memorandum. Use the Migrator Word/YAML template as the document-structure authority.

## Source priority

1. Populated web-intake metadata is authoritative for beneficiary name, preferred reference, field, specialization/subfield, case number, dates, USCIS address, office, and submitter data. Do not replace a populated intake value merely because OCR differs.
2. The human strategy controls what arguments will be made and which RFE concerns will be answered.
3. The RFE controls the exact adverse findings, favorable findings, adjudicator information, and quoted language.
4. For every section and episode, set `include_rfe_quote` to `true` only when the human strategy affirmatively calls for quoting/citing the RFE in that location. Final merits and conclusion default to `false`.
5. The initial filing supplies prior arguments and exhibit context; do not treat it as new evidence.

## Required extraction

- Extract the exact number and canonical role names of criteria USCIS accepted. Put the names in `accepted_criteria` and the matching integer in `accepted_criteria_count`.
- Extract the exact number and canonical role names of criteria USCIS did not accept or challenged. Put the names in `challenged_criteria` and the matching integer in `challenged_criteria_count`.
- Use only these criterion role IDs: `awards`, `memberships`, `media`, `judging`, `original_contribution`, `scholarly_articles`, `exhibitions`, `leading_critical_role`, `high_salary`, `commercial_success`.
- Extract `office_chief_name`, `officer_name`, and `officer_number` from the RFE. Use an empty string only when genuinely unavailable; record uncertainty in `open_questions`.
- Produce a ready-to-insert `salutation` matching the RFE addressees, for example `Dear Ms. Jane Smith and Officer 1234:`. Never invent a name or number.
- List the exact ordered document sections in `sections`, including only criteria and non-criterion issues that the response will actually address.

## Structure rules

- The generated response begins with a script-generated INDEX, followed by the cover letter, challenged response sections, and Final Merits Determination when warranted.
- Never create a standalone Recommendation Letters section and set `include_recommendation_letters` to `false`. Recommendation letters may be cited only inside another properly triggered response section.
- Include Industry Overview only if both conditions are met: the RFE raises a specific adverse concern about the industry/field and the human strategy contains a concrete response strategy for that concern. Set `include_industry_overview` accordingly. A required Industry Overview section must map at least one RFE issue and contain non-empty strategy.
- Include a U.S. employment, continued-work, or prospective-benefit section only if both conditions are met: the RFE raises that issue and the human strategy addresses it. Set `include_employment_section` accordingly. A required employment section must map at least one RFE issue and contain non-empty strategy.
- Do not add sections because they appear in an initial petition or generic template. The RFE plus strategy must trigger them.
- Each challenged criterion may contain one or more evidence-folder episodes. Give every episode a stable `episode_id`, filing-ready title, source folder, issue mapping, concrete strategy, and planned rebuttal subheadings.
- `exact_rfe_quote` is verbatim. Recover the complete adverse-reasoning passage from the RFE when the strategy abbreviates it. Remove only OCR line-break/hyphenation artifacts.
- State disputed and undisputed elements separately. Put matters USCIS accepted in `elements_not_disputed_do_not_discuss`; later drafting must not waste space re-proving them.
- `starter_text` may contain only safe, source-supported bridge language. Never invent facts.
- Order sections strategically and use unique consecutive positive `order` values.
- Return strict JSON matching the supplied schema: escape internal quotation marks, encode literal line breaks as `\n`, use no trailing commas, and add no Markdown fences or commentary.
