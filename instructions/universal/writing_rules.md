# Universal writing rules

The `draft_text` field is final petition text and is inserted into the working memorandum verbatim.

- Write polished, human-facing USCIS petition prose: factual, affirmative, evidence-based, and professionally restrained.
- Never mention prompts, an LLM/model, evidence extraction, OCR, machine readability, parsing, the drafting workflow, the selected folder, or an "episode" in petition text.
- Never insert drafting advice, diagnostic notes, jokes, sarcasm, asides, or comments to the legal team in `draft_text`.
- Put all internal cautions and evidence gaps only in `unsupported_claims`, `questions_for_user`, `quality_flags`, or `revision_notes`.
- Do not tell USCIS that the evidence is weak, incomplete, contextual only, or does not prove the criterion. Draft the strongest accurate affirmative argument supported by the available record without inventing facts.
- Do not use doubtful framing such as "claimed specialization." Prefer the beneficiary's specialization, field of expertise, or stated specialization as appropriate.
- Use one consistent English name and abbreviation for each organization. Define a source-language acronym once only if it materially helps identify the evidence.
- Avoid unsupported prestige adjectives. Prefer concrete document-grounded statements.
- Avoid formulaic phrases such as "states that he has" when a direct professional description is clearer.

Before returning JSON, silently remove every trace of internal work product from `draft_text`.
