# Opening case context

Task type: EB-1A petition memorandum.

Case ID: `{{ case.case_id }}`

Beneficiary: `{{ case.beneficiary.full_name }}`

Field: `{{ case.field }}`

Specialization: `{{ case.specialization }}`

Procedural context: `{{ case.procedural_context }}`

Drafting objective: `{{ case.drafting_objective }}`

## Instructions

Use only the documents, extracted text, templates, and instructions included in this prompt. Do not invent facts, dates, credentials, quotations, document contents, exhibit numbers, page numbers, or authorities. Put missing or unsupported matters into the structured `unsupported_claims` and `questions_for_user` fields.

<!-- Exact language, required background, and tone awaiting user approval. -->

Return only JSON matching the supplied output schema.
