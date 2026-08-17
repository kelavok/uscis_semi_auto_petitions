# EB-2 NIW LLM Drafting Instructions

Version: 1.0
Purpose: instructions for an LLM pipeline that drafts an EB-2 NIW petition memorandum by blocks, using case context, CV, source folders, exhibit metadata, and a memo template.
Final petition language: English.
Instruction language: Russian.

## 1. Core drafting rule

Draft the petition as a legal memorandum supported by documentary evidence. Do not draft it as a marketing profile, biography, business pitch, or generic immigration essay.

The memorandum must follow this legal sequence:

1. Basic EB-2 eligibility threshold:
   - Advanced Degree Professional; and/or
   - Person of Exceptional Ability.
2. National Interest Waiver under Matter of Dhanasar:
   - Prong 1: proposed endeavor has substantial merit and national importance;
   - Prong 2: petitioner is well positioned to advance the proposed endeavor;
   - Prong 3: on balance, it would be beneficial to waive the job offer and labor certification requirements.
3. Conclusion.

The LLM must treat USCIS Policy Manual requirements as controlling. Prior drafts, folder names, CV wording, recommendation letters, and strategy notes are source material. If they conflict with Policy Manual logic, use Policy Manual logic and flag the conflict.

## 2. Non-negotiable LLM constraints

### 2.1. Evidence discipline

Use only facts supported by the input materials. Do not invent:

- dates;
- employers;
- clients;
- job titles;
- revenue;
- salaries;
- awards;
- memberships;
- publications;
- contracts;
- agencies;
- U.S. partners;
- market figures;
- citations;
- page numbers;
- exhibit numbers.

If a useful fact is missing, write it in `UNRESOLVED_ISSUES`, not in the memorandum text.

Every material factual claim in the memorandum must have an exhibit reference or source reference. A factual claim is material if it supports eligibility, impact, credibility, experience, recognition, national importance, or waiver balancing.

### 2.2. Legal framing constraints

Do not merge the EB-2 threshold analysis with the NIW prongs. First establish EB-2 eligibility, then analyze NIW.

Do not equate occupation with proposed endeavor. The occupation is broader. The proposed endeavor is the specific work, project, plan, business model, research program, technology, methodology, or implementation plan the petitioner will advance in the United States.

Do not assert national importance only because:

- the occupation is important;
- the industry is important;
- the United States has a labor shortage;
- the petitioner is talented;
- the employer or client has national operations;
- the business may generate ordinary private profit.

National importance must be tied to the specific prospective impact of the proposed endeavor and must show broader implications for a field, region, public welfare, market, technology, infrastructure, public system, national priority, or other nationwide/public-level interest.

Do not rely on recommendation letters as the only support for strong claims if objective records should exist. Letters are useful when they are specific, first-hand, and corroborated by independent evidence.

Do not turn the memorandum into a long Policy Manual quotation. Use a short rule, apply case facts, cite evidence, then conclude.

## 3. Input contract for each block

Each generation call should provide the LLM with the following structured input. The script can omit unavailable fields, but the LLM must not fill missing fields by speculation.

```yaml
case_context:
  petitioner_full_name:
  petitioner_last_name:
  pronouns:
    subject:
    object:
    possessive:
  field_of_endeavor:
  intended_occupation:
  proposed_endeavor_title:
  proposed_endeavor_one_sentence:
  proposed_endeavor_summary:
  eb2_basis: "Advanced Degree | Exceptional Ability | Both"
  us_entity_name:
  current_status:
  country_of_citizenship:
  filing_theory_notes:

cv_summary:
  education:
  work_history:
  achievements:
  publications:
  awards:
  memberships:
  patents_or_ip:
  media:
  entrepreneurial_history:
  relevant_metrics:

folder_context:
  block_id:
  section_title:
  folder_path:
  folder_purpose:
  thesis_to_prove:
  evidence_items:
    - exhibit_id:
      title:
      file_name:
      date:
      issuer:
      language:
      translation_status:
      page_placeholder:
      facts_supported:
      limitations:
      notes:

prior_sections:
  overview:
  proposed_endeavor:
  basic_eligibility_summary:
  prong_1_summary:
  prong_2_summary:
  already_used_facts:
  already_used_exhibits:

legal_context:
  controlling_rule_summary:
  section_specific_rule:
  negative_rules:
  policy_manual_excerpt_if_provided:

output_requirements:
  target_language: English
  tone: formal legal memorandum
  citation_format: "(Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)"
  max_length_guidance:
```

## 4. Output contract for each block

Each LLM response must use this parseable structure:

```xml
<BLOCK id="{{BLOCK_ID}}" title="{{SECTION_TITLE}}">
<DRAFT_TEXT>
[Final English prose for insertion into the memorandum.]
</DRAFT_TEXT>

<EXHIBIT_USE_LOG>
- {{EXHIBIT_ID}} | {{DOCUMENT_TITLE}} | Used for: {{FACT_OR_CLAIM_SUPPORTED}}
</EXHIBIT_USE_LOG>

<UNRESOLVED_ISSUES>
- {{ISSUE_OR_MISSING_EVIDENCE}}
</UNRESOLVED_ISSUES>

<FACT_SUPPORT_MAP>
- Claim: {{CLAIM}}
  Support: {{EXHIBIT_ID}} / {{SOURCE}}
  Confidence: High | Medium | Low
  Limitation: {{LIMITATION_IF_ANY}}
</FACT_SUPPORT_MAP>
</BLOCK>
```

If no reliable text can be drafted from the provided evidence, output:

```xml
<DRAFT_TEXT>
[NO DRAFT: the provided materials do not support this section.]
</DRAFT_TEXT>
```

Then explain the missing evidence in `UNRESOLVED_ISSUES`.

## 5. Exhibit citation rules

Use only exhibit IDs supplied in the input. Do not create exhibit numbers.

Preferred citation format:

```text
(Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

For translated documents:

```text
(Please refer to Exhibit {{EXHIBIT_ID}}, pp. {{PAGE_XX}}-{{PAGE_YY}}: {{DOCUMENT_TITLE}}, with certified English translation.)
```

If page numbers are not available yet, preserve the placeholder exactly:

```text
p. {{PAGE_XX}}
```

When citing a recommendation letter, use it for the author’s opinion, first-hand observation, or confirmation of a fact. Do not use it as proof of independent market facts unless the author’s position and basis of knowledge are established.

## 6. Conflict-resolution hierarchy

If inputs conflict, apply this order:

1. USCIS Policy Manual / controlling legal rule supplied in `legal_context`.
2. Objective documentary evidence in exhibits.
3. Official records, contracts, diplomas, evaluations, tax records, business registration records, publications, court/government/agency records.
4. Recommendation letters and expert letters.
5. CV and questionnaire summaries.
6. Strategy notes and prior drafts.

If a prior draft says “national shortage is enough” or “the industry is important,” rewrite it into a proper national-importance theory or flag it as insufficient.

If a folder title implies a claim but the documents do not prove it, draft only what the documents prove and flag the gap.

## 7. Global memorandum style

Use formal legal English.

Use the petitioner’s last name after the first full-name reference.

Prefer precise verbs: establishes, demonstrates, corroborates, documents, confirms, supports.

Avoid adjectives without evidentiary content: outstanding, exceptional, unique, significant, important, renowned, leading. Use them only when the sentence explains the basis.

Each paragraph should usually follow this structure:

```text
Legal relevance / claim. Specific fact. Evidence reference. Why the fact satisfies the standard.
```

Avoid isolated exhibit citations at the end of long paragraphs. Place citations close to the fact they support.

## 8. Block-by-block instructions

### 8.1. Overview / professional biography

Purpose: give the officer a concise map of the case.

Use: CV, education documents, employment summaries, main achievements, proposed endeavor notes, strongest metrics, U.S. plans.

Must include:

- who the petitioner is;
- intended occupation;
- field of endeavor;
- proposed endeavor in plain English;
- problem addressed;
- EB-2 basis;
- one-sentence preview of each NIW prong;
- exhibit reference to CV and strongest general records.

Do not over-detail. This section is a roadmap, not the full evidentiary argument.

### 8.2. Proposed Endeavor block

Purpose: define the proposed endeavor before Prong 1 analysis.

Must answer:

- What exactly will the petitioner do in the United States?
- Through what vehicle: employer, own company, research program, platform, product, consulting model, nonprofit, academic work, etc.?
- Who are the intended beneficiaries, users, customers, institutions, or affected public?
- What problem does the endeavor address?
- What is the mechanism of impact?
- What is the implementation plan: timeline, milestones, resources, partners, contracts, funding, site, team, product, publications, research, or other progress?

Do not define the endeavor as a job title. “Software engineer,” “entrepreneur,” “teacher,” or “consultant” is not enough. The block must define the concrete project or activity.

### 8.3. Basic Eligibility: Advanced Degree Professional

Use this section when the folder structure or input says the case relies on advanced degree.

Must prove:

- petitioner has a U.S. advanced degree or foreign equivalent; or
- petitioner has a U.S. bachelor’s degree or foreign equivalent plus at least five years of progressive post-baccalaureate experience in the specialty;
- intended occupation qualifies as a profession requiring at least a bachelor’s degree or foreign equivalent for entry;
- the degree / specialty / experience relates to the proposed endeavor.

Evidence may include:

- diploma;
- transcript;
- credential evaluation;
- university description;
- employer letters confirming progressive post-degree experience;
- contracts / employment records;
- occupational sources showing degree requirement, if provided.

If the degree field and endeavor field differ, explain the connection carefully or flag the issue.

### 8.4. Basic Eligibility: Exceptional Ability introduction

Use this only if the folder structure includes Exceptional Ability or the input says the case relies on it.

Must state:

- exceptional ability means expertise significantly above that ordinarily encountered in the sciences, arts, or business;
- the petitioner satisfies at least three of the six regulatory criteria;
- after the criteria are met, the evidence must be evaluated in the aggregate under final merits;
- the area of exceptional ability must be directly related to the proposed endeavor.

Do not claim “3 out of 10.” Use six regulatory criteria.

### 8.5. Exceptional Ability criteria blocks

Generate only criteria supported by folders/evidence.

Criterion R1, Official Academic Record:
- prove degree, diploma, certificate, or similar award from an institution of learning relating to the area of exceptional ability;
- cite diploma/evaluation/university records.

Criterion R2, Ten Years of Full-Time Experience:
- prove at least ten years of full-time experience in the occupation;
- use employer letters, contracts, labor records, tax records, CV only as secondary support;
- identify dates, roles, and continuity.

Criterion R3, License or Certification:
- prove license/certification for the profession or occupation;
- explain issuer, requirements, professional relevance.

Criterion R4, Salary or Other Remuneration:
- prove compensation that demonstrates exceptional ability relative to others in the field;
- use contracts, tax records, payroll, bank records, salary benchmarks;
- compare by geography, year, occupation, and currency where possible.

Criterion R5, Membership in Professional Associations:
- prove membership in professional associations;
- explain the association’s professional relevance;
- if membership is selective, explain criteria only if evidence supports that.

Criterion R6, Recognition for Achievements and Significant Contributions:
- prove recognition by peers, government entities, professional organizations, or business organizations;
- connect recognition to achievements and contributions in the relevant field;
- prioritize objective recognition, adoption, awards, media, official acknowledgments, contracts, metrics, letters supported by records.

### 8.6. Exceptional Ability final merits block

Purpose: synthesize the criteria into a totality argument.

Must explain why the combined evidence shows expertise significantly above that ordinarily encountered.

Do not repeat every criterion mechanically. Select the strongest facts and explain:

- quality of evidence;
- field relevance;
- comparative strength;
- direct relationship to the proposed endeavor.

### 8.7. Prong 1, Block 1: Proposed Endeavor description and Substantial Merit

This can be generated as two sub-blocks if the script needs smaller chunks:

1. `B0_PROPOSED_ENDEAVOR_DESCRIPTION`
2. `B1_1_SUBSTANTIAL_MERIT`

For proposed endeavor description, define the project with specificity.

For substantial merit, explain why the endeavor has merit in one or more areas: business, entrepreneurship, science, technology, culture, health, education, public safety, infrastructure, economic competitiveness, national security, or another supported field.

Substantial merit can exist without immediate quantifiable economic impact. If economic impact is used, support it with documents, metrics, or sources.

Use official sources, industry materials, market reports, technical publications, and evidence connecting the petitioner’s endeavor to the stated problem.

### 8.8. Prong 1, Block 2: National Importance

Purpose: show prospective broader impact.

Must explain:

- the specific national-level or field-level problem;
- why the problem matters beyond one employer or client;
- how the petitioner’s endeavor addresses the problem;
- expected prospective impact;
- mechanism of broader implications.

Possible theories:

- field-level advancement of technology, method, research, operational model, standard, or practice;
- public welfare, health, safety, education, infrastructure, access, cybersecurity, resilience;
- regional impact in underserved, economically depressed, rural, disaster-affected, or strategic regions;
- economic impact through job creation, productivity, investment, exports, supply-chain resilience, commercialization;
- national priority supported by federal programs or agency sources;
- cultural or artistic enrichment with broader access, recognized contribution, institutional adoption.

Do not treat labor shortage as complete national importance. Labor shortage may support context only when tied to the petitioner’s specific solution.

### 8.9. Prong 2 introductory block

Purpose: introduce why the petitioner is well positioned.

Must preview categories of evidence, such as:

- education;
- skills and specialized knowledge;
- record of success in related or similar efforts;
- detailed proposal or plan;
- progress toward the endeavor;
- customers, users, partners, investors, or other support;
- contracts, licenses, business records, revenue, media, publications, patents, grants;
- expert letters supported by independent evidence.

The petitioner does not need to prove that the endeavor is more likely than not to succeed. The petitioner must prove credible capacity to advance it.

### 8.10. Prong 2 per-folder evidence blocks

The script should generate one block per folder/thesis. Each block must answer:

- What is the achievement, project, role, or evidence category?
- When and where did it happen?
- What exactly did the petitioner do?
- What result was achieved?
- How is it related to the proposed endeavor?
- What exhibits prove it?
- How does it show the petitioner is well positioned?

Recommended paragraph formula:

```text
The evidence first shows [category of preparation]. In [date/project], [petitioner] [specific action]. This resulted in [measurable or concrete result]. The record corroborates this through [exhibit]. This experience is directly relevant to the proposed endeavor because [connection].
```

If the folder contains only background documents with weak connection, state a narrower claim and flag the gap.

### 8.11. Prong 2 totality block

After all folder blocks, synthesize.

Do not repeat each subsection. Explain how the combined evidence shows:

- relevant expertise;
- proven execution ability;
- credible plan;
- existing progress;
- outside interest/support;
- direct fit between past work and future endeavor.

### 8.12. Prong 3 block

Generate as one coherent section.

Purpose: show that, considering Prong 1 and Prong 2 together, waiver of job offer and labor certification benefits the United States.

Use evidence from the Prong 3 folder and cross-reference Prong 1/Prong 2 facts.

Analyze one or more supported factors:

- labor certification is impractical due to the nature of the endeavor or petitioner’s role;
- the endeavor is entrepreneurial, self-directed, multi-client, multi-state, research-driven, grant-driven, project-based, or otherwise poorly captured by a single permanent job offer;
- the petitioner has unique knowledge or skills exceeding minimum occupational requirements;
- the United States benefits from petitioner’s contributions even if other U.S. workers are available;
- the endeavor has urgency or time-sensitive public, economic, security, health, or infrastructure benefits;
- the endeavor may create jobs, investment, productivity, regional development, or sectoral effects;
- interested U.S. government or quasi-government support exists.

Do not argue that labor shortage alone satisfies Prong 3. It does not.

Do not argue “the petitioner is better than U.S. workers” in a crude comparative way. Focus on why this specific endeavor and petitioner’s specific qualifications make the waiver beneficial.

### 8.13. Conclusion block

Purpose: short final synthesis.

Must state:

- EB-2 threshold basis is met;
- proposed endeavor has substantial merit and national importance;
- petitioner is well positioned;
- waiver is beneficial on balance;
- requested relief: approval of EB-2 classification and NIW.

Do not introduce new facts or new legal theories in conclusion.

## 9. Final assembly rules

When assembling blocks into the final memorandum:

1. Remove unused optional sections.
2. Preserve section numbering and headings.
3. Check that each block uses consistent terminology for the proposed endeavor.
4. Check that every exhibit cited in text appears in List of Exhibits.
5. Check that every cited page placeholder is updated after final PDF assembly.
6. Check that no section contains unsupported claims.
7. Check that Basic Eligibility comes before NIW.
8. Check that Prong 1 focuses on the endeavor, Prong 2 on the petitioner, and Prong 3 on the waiver balance.

## 10. Quality-control checklist for the script

Before accepting a generated block, run these checks:

```yaml
required_checks:
  no_hallucinated_facts: true
  no_missing_exhibit_references_for_material_claims: true
  no_new_exhibit_ids_created_by_llm: true
  proposed_endeavor_consistent_with_case_context: true
  section_matches_legal_standard: true
  unresolved_issues_flagged: true
  page_placeholders_preserved: true
  no_generic_occupation_importance_argument: true
  no_labor_shortage_standalone_argument: true
  no_letters_only_for_objective_claims_where_records_needed: true
```

Reject and regenerate if the block fails any mandatory check.
