# Universal quality control

Before returning the JSON, silently verify:

- beneficiary identifiers, honorifics, pronouns, organization names, and abbreviations are consistent;
- no prompt/workflow/AI language, jokes, diagnostic notes, OCR commentary, or the word "episode" remains in `draft_text`;
- no negative evidence-sufficiency analysis appears in petition text;
- every relied-on document ID exists in the supplied index and every `document_title` is concise English;
- exhibit numbers and item prefixes match the current criterion;
- the exhibit document list is present and complete for the drafted material;
- measurable facts and available numbers have not been replaced by vague summaries;
- media outlets are enumerated with concrete metadata when media evidence is relevant;
- internal concerns appear only in the structured internal arrays.
