# EB-2 NIW petition task rules

The controlling substantive rules are in `templates/EB2NIW/EB2_NIW_LLM_instructions.md`; the memorandum block order is in `templates/EB2NIW/EB2_NIW_general_memo_template.md`. Apply them together with the current step objective and supplied case instructions.

## System output contract overrides examples in source templates

- Return only valid JSON matching `schemas/llm_section_output.schema.json`.
- The XML/YAML examples in the source drafting instructions describe substance and block structure only. Do not return XML or YAML.
- Put filing-ready English prose only in `draft_text`.
- Put the complete ordered evidence list in `used_documents` and internal issues only in `unsupported_claims`, `questions_for_user`, `quality_flags`, and `revision_notes`.
- Never include drafting directions, source-processing notes, OCR comments, placeholders other than the permitted `PAGE`, or discussion of the LLM in `draft_text`.

## Scope and evidence

- Use only the supplied case context, indexed evidence, auxiliary folder context, and prior validated drafts. Do not browse or search the Internet unless the prompt expressly authorizes external research.
- Every document in the Technical document selection is mandatory: include it exactly once in `used_documents`, in the logical order in which it belongs in the memorandum and exhibit. Never sort by DOC number or raw filename.
- Use exactly the supplied `DOC####` identifiers. Auxiliary `extract`, `info`, and `readme` files and the free-form case-context file are prompt-only context and may never be cited or placed in `used_documents`.
- Preserve names, dates, figures, organization names, and document titles accurately. Give each used document a concise stable English filing title.

## Legal structure

- First establish the EB-2 threshold as advanced degree professional, exceptional ability, or both, based on populated evidence folders.
- Keep the threshold analysis separate from Matter of Dhanasar.
- Define the proposed endeavor as specific prospective work, not merely the occupation or industry.
- Analyze Prong 1 as substantial merit plus national importance of that specific endeavor.
- Analyze Prong 2 through education, skills, record of success, concrete plan, progress, and interest or support relevant to the endeavor.
- Analyze Prong 3 as the evidence-based on-balance benefit of waiving the job-offer and labor-certification requirements. Do not argue that the beneficiary is irreplaceable or compare them crudely with U.S. workers.
- Conclusions must apply the governing test to established facts and must not be empty placeholders.
