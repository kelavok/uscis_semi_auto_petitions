# EB-2 NIW RFE strategy bootstrap instructions

EXECUTE THIS TASK NOW. Return only the completed JSON object. This step builds the machine-readable response plan; it does not draft the final response.

Convert the human strategy, the complete RFE notice, the initial company structure, and the EB-2 NIW RFE drafting template into a precise case plan.

Rules:

1. The human strategy is the highest-priority case-specific source. Preserve it unless it conflicts with an explicit fact or the RFE; record genuine conflicts in `open_questions`.
2. `exact_rfe_quote` must reproduce the complete adverse finding verbatim. Recover the full passage from the RFE when the strategy abbreviates it. Only repair obvious OCR line-break or hyphenation artifacts.
3. Extract all available metadata. Never invent dates, receipt numbers, names, addresses, the intended occupation, or the proposed endeavor. Empty strings are allowed only for fields that are genuinely unavailable.
4. Treat the proposed endeavor stated in the initial filing as controlling. Do not rewrite it into a materially different endeavor.
5. Determine which matters USCIS accepted and which it challenged. Do not create drafting units solely to reargue accepted findings.
6. Use these role IDs when applicable: `basic_eligibility`, `advanced_degree`, `exceptional_ability`, `exceptional_academic_record`, `exceptional_ten_years`, `exceptional_license`, `exceptional_remuneration`, `exceptional_membership`, `exceptional_recognition`, `exceptional_final_merits`, `prong1`, `prong2`, `prong3`, `summary`.
7. Build units in the company order: cover letter; Basic Eligibility issues actually challenged; Prong 1; Prong 2; Prong 3; Summary. Within each group follow the RFE's logic and the human strategy.
8. Prong 1 units may separately address endeavor definition/substantial merit, national problem and nexus, prospective national impact, government initiatives, economic or public impact, scale beyond one employer, and corroborating support, but only where the RFE or strategy requires them.
9. Prong 2 units may separately address education/skills, record of success, adoption or use by others, prior roles, implementation plan, progress/support, and recommendation letters, but the final structure must read as one coherent prong analysis.
10. Prong 3 should ordinarily be one integrated on-balance unit unless the RFE contains clearly separate defects requiring separate units.
11. Every drafting section must map to one or more RFE issues, state a concrete response strategy, and use a stable English `section_id`/`episode_id`. `source_folder` must identify the matching folder relative to the new-evidence originals/translations root. Do not derive filing titles mechanically from Cyrillic folder names; provide filing-ready English titles.
12. `starter_text` may contain safe procedural or bridge text supported by the record, never unsupported advocacy.
13. The response must permit the script to build exact RFE quote blocks, direct `Answer:` blocks, coherent issue headings, conclusions, a front evidence index, and four-level exhibit groups: Basic Eligibility, Prong 1, Prong 2, Prong 3.
14. Return strict JSON matching the supplied schema: no Markdown fence, no prose outside the object, escaped internal quotes, encoded line breaks, and no trailing commas.
