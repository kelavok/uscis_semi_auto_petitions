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


---

# EB-2 NIW General Petition Memorandum Template

Version: 1.0
Purpose: reusable block-based memorandum template for EB-2 NIW petitions.
Final language: English.

Use this template as the skeleton into which script-generated LLM blocks are inserted. Optional sections should be removed from the final filing version when unsupported by folder structure or evidence.

## Formatting settings for Word/PDF assembly

- Body font: Times New Roman or Arial.
- Line spacing: 1.5.
- Paragraphs: clear paragraph separation; no space before paragraph; consistent space after paragraph.
- Alignment: justified.
- Page numbering: footer, right side.
- Main section headings: Heading 1, 16 pt, bold.
- Episode/subsection headings: Heading 2, 14 pt, bold.
- Exhibit numbering: keep a consistent exhibit system across the packet.

## Global placeholders

```text
{{DATE}}
{{PETITIONER_FULL_NAME}}
{{PETITIONER_LAST_NAME}}
{{PETITIONER_ADDRESS}}
{{COUNTRY_OF_CITIZENSHIP}}
{{PRONOUN_SUBJECT}}
{{PRONOUN_OBJECT}}
{{PRONOUN_POSSESSIVE}}
{{PRONOUN_SUBJECT_CAP}}
{{PRONOUN_POSSESSIVE_CAP}}
{{FIELD_OF_ENDEAVOR}}
{{INTENDED_OCCUPATION}}
{{PROPOSED_ENDEAVOR_TITLE}}
{{PROPOSED_ENDEAVOR_DESCRIPTION_1_SENTENCE}}
{{EB2_BASIS}}
{{US_ENTITY_NAME}}
{{PAGE_XX}}
{{EXHIBIT_ID}}
{{DOCUMENT_TITLE}}
```

Preferred exhibit reference:

```text
(Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

For translated records:

```text
(Please refer to Exhibit {{EXHIBIT_ID}}, pp. {{PAGE_XX}}-{{PAGE_YY}}: {{DOCUMENT_TITLE}}, with certified English translation.)
```

---

# Petition Memorandum

## Overview

[[BLOCK:OVERVIEW_PROFESSIONAL_BIOGRAPHY]]

Required content for this block:

```text
{{PETITIONER_FULL_NAME}} is {{PROFESSIONAL_IDENTIFIER}} with {{YEARS_OF_EXPERIENCE}} years of experience in {{FIELD_OR_INDUSTRY}}. {{PRONOUN_SUBJECT_CAP}} has {{KEY_CREDENTIALS}} and a record of {{KEY_RECORD_OF_SUCCESS}}.

{{PETITIONER_LAST_NAME}} proposes to advance {{PROPOSED_ENDEAVOR_TITLE}} in the United States. The proposed endeavor is {{PROPOSED_ENDEAVOR_DESCRIPTION_1_SENTENCE}}. It addresses {{SPECIFIC_PROBLEM}}, which affects {{BROADER_FIELD_REGION_PUBLIC_OR_MARKET}}.

The evidence shows that the endeavor is supported by {{EXISTING_PROGRESS_OR_SUPPORT}}, including {{METRIC_OR_FACT_1}}, {{METRIC_OR_FACT_2}}, and {{METRIC_OR_FACT_3}}. These facts demonstrate that the petition is based on a specific endeavor rather than a general intention to work in an important occupation.

{{PETITIONER_LAST_NAME}} qualifies for EB-2 classification as {{EB2_BASIS}}. The proposed endeavor has substantial merit and national importance because {{PRONG_1_SUMMARY}}. {{PETITIONER_LAST_NAME}} is well positioned to advance it because {{PRONG_2_SUMMARY}}. On balance, waiving the job offer and labor certification requirements would benefit the United States because {{PRONG_3_SUMMARY}}.

For these reasons, {{PETITIONER_FULL_NAME}} satisfies the requirements for EB-2 classification and the national interest waiver.
```

---

# A. Basic Eligibility for EB-2

[[BLOCK:A0_BASIC_ELIGIBILITY_INTRO]]

Template text:

```text
To qualify for a national interest waiver, {{PETITIONER_FULL_NAME}} must first establish eligibility for the underlying EB-2 classification as either a member of the professions holding an advanced degree or as a person of exceptional ability in the sciences, arts, or business.

{{PETITIONER_LAST_NAME}}’s intended occupation is {{INTENDED_OCCUPATION}}. Through this occupation, {{PRONOUN_SUBJECT}} will advance {{PROPOSED_ENDEAVOR_TITLE}}, specifically defined as {{PROPOSED_ENDEAVOR_DESCRIPTION_1_SENTENCE}}.

The evidence establishes EB-2 eligibility because {{PETITIONER_LAST_NAME}} qualifies as {{EB2_BASIS}}.
```

## A.1. Advanced Degree Professional [optional]

[[BLOCK:A1_ADVANCED_DEGREE]]

Use when the petitioner relies on a U.S. master’s degree or higher, foreign equivalent, or bachelor’s degree plus at least five years of progressive post-baccalaureate experience in the specialty.

Template text:

```text
{{PETITIONER_FULL_NAME}} qualifies for EB-2 classification as a member of the professions holding an advanced degree because {{PRONOUN_SUBJECT}} possesses {{DEGREE_OR_EQUIVALENT}}, and {{PRONOUN_POSSESSIVE}} intended occupation, {{INTENDED_OCCUPATION}}, is a profession requiring at least a U.S. bachelor’s degree or foreign equivalent for entry.

{{PETITIONER_LAST_NAME}} earned {{DEGREE_NAME}} in {{FIELD_OF_STUDY}} from {{INSTITUTION_NAME}} in {{YEAR}}. The credential evaluation confirms that this degree is equivalent to {{US_EQUIVALENT_DEGREE}}. {{RELEVANCE_TO_ENDEAVOR}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

[If bachelor plus five years is used:] After earning {{PRONOUN_POSSESSIVE}} bachelor’s degree, {{PETITIONER_LAST_NAME}} accumulated more than five years of progressive post-baccalaureate experience in {{SPECIALTY}}. This experience included {{PROGRESSIVE_EXPERIENCE_SUMMARY}}, directly related to {{PROPOSED_ENDEAVOR_TITLE}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

Accordingly, {{PETITIONER_LAST_NAME}} satisfies the EB-2 advanced degree professional requirement.
```

## A.2. Person of Exceptional Ability [optional]

[[BLOCK:A2_EXCEPTIONAL_ABILITY_INTRO]]

Template text:

```text
In the alternative, or independently if applicable, {{PETITIONER_FULL_NAME}} qualifies as a person of exceptional ability in {{FIELD_OF_EXCEPTIONAL_ABILITY}}. The evidence satisfies at least three of the six regulatory criteria and, when evaluated in the aggregate, demonstrates expertise significantly above that ordinarily encountered in the field.

The area of exceptional ability is directly related to {{PROPOSED_ENDEAVOR_TITLE}} because {{CONNECTION_BETWEEN_FIELD_AND_ENDEAVOR}}.
```

### A.2.R1. Official Academic Record [optional]

[[BLOCK:A2_R1_ACADEMIC_RECORD]]

```text
The record satisfies this criterion because {{PETITIONER_LAST_NAME}} holds {{DEGREE_DIPLOMA_CERTIFICATE}} in {{FIELD}}, issued by {{INSTITUTION_NAME}}. This academic record relates to {{FIELD_OF_EXCEPTIONAL_ABILITY}} and supports {{PRONOUN_POSSESSIVE}} qualification in the field. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

### A.2.R2. At Least Ten Years of Full-Time Experience [optional]

[[BLOCK:A2_R2_TEN_YEARS_EXPERIENCE]]

```text
The evidence establishes that {{PETITIONER_LAST_NAME}} has at least ten years of full-time experience in {{OCCUPATION}}. From {{START_YEAR}} to {{END_YEAR_OR_PRESENT}}, {{PRONOUN_SUBJECT}} worked in roles including {{ROLE_SUMMARY}}, with responsibilities involving {{RELEVANT_RESPONSIBILITIES}}. These records document sustained full-time experience in the occupation. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

### A.2.R3. License or Certification [optional]

[[BLOCK:A2_R3_LICENSE_CERTIFICATION]]

```text
The record satisfies this criterion because {{PETITIONER_LAST_NAME}} holds {{LICENSE_OR_CERTIFICATION}}, issued by {{ISSUING_AUTHORITY}}. The certification is relevant to {{PROFESSION_OR_OCCUPATION}} because {{REQUIREMENTS_AND_RELEVANCE}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

### A.2.R4. Salary or Other Remuneration Demonstrating Exceptional Ability [optional]

[[BLOCK:A2_R4_REMUNERATION]]

```text
The evidence shows that {{PETITIONER_LAST_NAME}} commanded remuneration indicative of exceptional ability in {{FIELD_OR_OCCUPATION}}. In {{YEAR_OR_PERIOD}}, {{PRONOUN_SUBJECT}} received {{COMPENSATION_AMOUNT}} for services as {{ROLE}}, while relevant benchmark data for comparable professionals in {{GEOGRAPHY_AND_OCCUPATION}} shows {{BENCHMARK_AMOUNT}}. This comparison supports the conclusion that {{PRONOUN_POSSESSIVE}} remuneration exceeded ordinary compensation for comparable work. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

### A.2.R5. Membership in Professional Associations [optional]

[[BLOCK:A2_R5_MEMBERSHIP]]

```text
The record satisfies this criterion because {{PETITIONER_LAST_NAME}} is a member of {{ASSOCIATION_NAME}}, a professional association in {{FIELD}}. The association is relevant to {{FIELD_OF_EXCEPTIONAL_ABILITY}} because {{ASSOCIATION_RELEVANCE}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

### A.2.R6. Recognition for Achievements and Significant Contributions [optional]

[[BLOCK:A2_R6_RECOGNITION]]

```text
The evidence demonstrates recognition of {{PETITIONER_LAST_NAME}}’s achievements and significant contributions in {{FIELD}}. Specifically, {{RECOGNITION_SOURCE}} recognized {{PRONOUN_OBJECT}} for {{ACHIEVEMENT_OR_CONTRIBUTION}}. The significance of this contribution is corroborated by {{OBJECTIVE_CORROBORATION}}, which shows {{IMPACT_OR_RESULT}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

### A.2.FM. Final Merits Determination for Exceptional Ability [optional]

[[BLOCK:A2_FM_FINAL_MERITS]]

```text
After satisfying at least three regulatory criteria, the evidence must be evaluated in the aggregate to determine whether {{PETITIONER_FULL_NAME}} has expertise significantly above that ordinarily encountered in {{FIELD_OF_EXCEPTIONAL_ABILITY}}.

The totality of the record supports this determination. {{PETITIONER_LAST_NAME}}’s strongest evidence includes {{STRONGEST_EVIDENCE_1}}, {{STRONGEST_EVIDENCE_2}}, and {{STRONGEST_EVIDENCE_3}}. These facts show more than possession of ordinary qualifications because {{WHY_ABOVE_ORDINARY}}.

The record also establishes that {{PETITIONER_LAST_NAME}}’s exceptional ability is directly related to {{PROPOSED_ENDEAVOR_TITLE}}. {{CONNECTION_TO_ENDEAVOR}}.

Accordingly, the evidence establishes by a preponderance of the evidence that {{PETITIONER_FULL_NAME}} qualifies as a person of exceptional ability under the EB-2 classification.
```

---

# B. National Interest Waiver

[[BLOCK:B0_NIW_INTRO]]

```text
Having established eligibility for the underlying EB-2 classification, {{PETITIONER_FULL_NAME}} respectfully requests a waiver of the job offer and labor certification requirements in the national interest. The evidence satisfies all three prongs of the Matter of Dhanasar framework.
```

## B.0. Proposed Endeavor

[[BLOCK:B0_PROPOSED_ENDEAVOR_DESCRIPTION]]

```text
{{PETITIONER_LAST_NAME}}’s proposed endeavor is {{PROPOSED_ENDEAVOR_DESCRIPTION_1_SENTENCE}}.

The endeavor will be advanced through {{IMPLEMENTATION_VEHICLE}}, including {{MAIN_ACTIVITIES}}. Its intended beneficiaries include {{BENEFICIARIES_USERS_CUSTOMERS_OR_PUBLIC}}. The endeavor addresses {{PROBLEM}}, a problem that affects {{AFFECTED_FIELD_REGION_PUBLIC_OR_MARKET}}.

The mechanism of impact is {{MECHANISM_OF_IMPACT}}. {{PETITIONER_LAST_NAME}} plans to implement the endeavor through {{PLAN_MILESTONES_RESOURCES_PARTNERS}}, supported by {{CURRENT_PROGRESS}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

## B.1. Prong 1: The Proposed Endeavor Has Substantial Merit and National Importance

[[BLOCK:B1_PRONG_1_INTRO]]

```text
The proposed endeavor satisfies the first prong of Matter of Dhanasar because it has substantial merit in {{MERIT_AREA}} and national importance through its potential prospective impact on {{FIELD_REGION_PUBLIC_MARKET_OR_NATIONAL_PRIORITY}}.
```

### B.1.1. Substantial Merit

[[BLOCK:B1_1_SUBSTANTIAL_MERIT]]

```text
{{PROPOSED_ENDEAVOR_TITLE}} has substantial merit because it addresses {{PROBLEM}} in {{AREA}}, a field involving {{BUSINESS_SCIENCE_TECHNOLOGY_HEALTH_CULTURE_EDUCATION_PUBLIC_SAFETY_INFRASTRUCTURE_OR_OTHER}}.

The record demonstrates substantial merit for several reasons. First, {{MERIT_REASON_1}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.) Second, {{MERIT_REASON_2}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.) Third, {{MERIT_REASON_3}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

The endeavor’s merit is not dependent solely on immediate economic impact. It is meritorious because {{NON_ECONOMIC_OR_PUBLIC_INTEREST_REASON}}, and, where applicable, it may also produce economic benefits through {{ECONOMIC_REASON_IF_APPLICABLE}}.
```

### B.1.2. National Importance

[[BLOCK:B1_2_NATIONAL_IMPORTANCE]]

```text
The proposed endeavor has national importance because its prospective impact extends beyond {{ONE_EMPLOYER_ONE_CLIENT_OR_LOCAL_JOB}} and has broader implications for {{FIELD_REGION_PUBLIC_AT_LARGE_OR_NATIONAL_SYSTEM}}.

USCIS evaluates national importance by focusing on the nature of the specific endeavor and its potential prospective impact. Here, {{PETITIONER_LAST_NAME}}’s endeavor is nationally important for the following reasons.

First, {{NATIONAL_IMPORTANCE_REASON_1}}. This is supported by {{EVIDENCE_1}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

Second, {{NATIONAL_IMPORTANCE_REASON_2}}. This is supported by {{EVIDENCE_2}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

Third, {{NATIONAL_IMPORTANCE_REASON_3}}. This is supported by {{EVIDENCE_3}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

The endeavor is not presented as nationally important simply because {{FIELD_OR_OCCUPATION}} is important. Rather, {{PETITIONER_LAST_NAME}}’s specific endeavor will {{SPECIFIC_MECHANISM_OF_BROADER_IMPACT}}.

Accordingly, the proposed endeavor satisfies the national importance component of Prong 1.
```

### B.1.3. Broader Implications Beyond One Employer or Local Benefit [optional]

[[BLOCK:B1_3_BROADER_IMPLICATIONS]]

```text
Although {{US_ENTITY_NAME_OR_EMPLOYER}} may be one vehicle through which {{PETITIONER_LAST_NAME}} advances the endeavor, the evidence shows that the endeavor has broader implications because {{BROADER_IMPLICATIONS_MECHANISM}}.

Specifically, the endeavor may {{BROADER_IMPACT_1}}, {{BROADER_IMPACT_2}}, and {{BROADER_IMPACT_3}}. The projected benefit therefore extends beyond {{PRIVATE_BENEFIT_DESCRIPTION}} and supports {{FIELD_REGION_PUBLIC_OR_NATIONAL_BENEFIT}}.
```

---

# B.2. Prong 2: The Petitioner Is Well Positioned to Advance the Proposed Endeavor

[[BLOCK:B2_PRONG_2_INTRO]]

```text
The second prong focuses on {{PETITIONER_LAST_NAME}}’s ability to advance the proposed endeavor. The record shows that {{PRONOUN_SUBJECT}} is well positioned based on {{EDUCATION_SKILLS_KNOWLEDGE_RECORD_PLAN_PROGRESS_SUPPORT_SUMMARY}}.
```

## B.2.1. Education, Skills, Knowledge, and Record of Success

[[BLOCK:B2_1_EDUCATION_SKILLS_RECORD]]

```text
{{PETITIONER_LAST_NAME}}’s education, skills, and record of success directly relate to {{PROPOSED_ENDEAVOR_TITLE}}. {{PRONOUN_SUBJECT_CAP}} has {{RELEVANT_EDUCATION_OR_TRAINING}}, experience in {{RELEVANT_EXPERIENCE}}, and documented success in {{SIMILAR_EFFORTS}}.

The record shows {{SPECIFIC_FACT_OR_PROJECT}}. This demonstrates {{RELEVANCE_TO_ENDEAVOR}} because {{CONNECTION_TO_PROPOSED_WORK}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

## B.2.2. Detailed Proposal or Plan for Future Activities

[[BLOCK:B2_2_DETAILED_PLAN]]

```text
The record includes a detailed plan for advancing {{PROPOSED_ENDEAVOR_TITLE}} in the United States. The plan identifies {{PLAN_ELEMENTS}}, including {{TIMELINE}}, {{MILESTONES}}, {{RESOURCES}}, and {{IMPLEMENTATION_STEPS}}.

This plan is credible because it is tied to {{PETITIONER_LAST_NAME}}’s prior experience in {{RELEVANT_PRIOR_EXPERIENCE}} and is supported by {{INDEPENDENT_SUPPORT_OR_PROGRESS}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

## B.2.3. Progress, Use by Others, Customers, Partners, Investors, and Support

[[BLOCK:B2_3_PROGRESS_SUPPORT]]

Use this heading as a container. The script may insert multiple folder-generated sub-blocks below.

### B.2.3.x. {{FOLDER_BASED_EPISODE_TITLE}}

[[BLOCK:B2_FOLDER_EPISODE_REPEATABLE]]

```text
The record further shows {{CATEGORY_OF_PROGRESS_OR_SUPPORT}}. In {{DATE_OR_PERIOD}}, {{PETITIONER_LAST_NAME}} {{SPECIFIC_ACTION_OR_ROLE}} in connection with {{PROJECT_OR_ENTITY}}. This resulted in {{CONCRETE_RESULT_OR_PROGRESS}}.

This evidence is relevant to Prong 2 because it shows {{WHY_WELL_POSITIONED}}. It is also directly connected to the proposed endeavor because {{DIRECT_CONNECTION_TO_ENDEAVOR}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)
```

Possible repeatable episode types:

```text
- completed projects / deployments;
- work used by others;
- customer or user interest;
- partner letters;
- investor interest;
- U.S. company formation and operations;
- contracts, agreements, licenses;
- financial support;
- publications or media;
- patents, software, methodologies, models;
- grants, awards, incubators, accelerators;
- government or quasi-government support;
- conference speaking, judging, expert activity;
- recommendation letters with first-hand detail.
```

## B.2.4. Totality of Circumstances Under Prong 2

[[BLOCK:B2_4_TOTALITY]]

```text
Taken together, the evidence establishes that {{PETITIONER_FULL_NAME}} is well positioned to advance {{PROPOSED_ENDEAVOR_TITLE}}. The record combines {{EVIDENCE_CATEGORY_1}}, {{EVIDENCE_CATEGORY_2}}, {{EVIDENCE_CATEGORY_3}}, and {{EVIDENCE_CATEGORY_4}}.

This combination is persuasive because {{SYNTHESIS_OF_WHY_CAPABLE}}. The evidence does not rest on an unsupported prediction of success. It shows a credible connection between {{PETITIONER_LAST_NAME}}’s past achievements, current progress, and proposed future work in the United States.

Accordingly, {{PETITIONER_LAST_NAME}} satisfies Prong 2.
```

---

# B.3. Prong 3: On Balance, It Would Be Beneficial to the United States to Waive the Job Offer and Labor Certification Requirements

[[BLOCK:B3_PRONG_3_BALANCE]]

```text
The third prong requires a balance analysis. Considering the substantial merit and national importance of {{PETITIONER_LAST_NAME}}’s proposed endeavor and {{PRONOUN_POSSESSIVE}} demonstrated ability to advance it, the evidence shows that waiving the job offer and labor certification requirements would benefit the United States.

First, requiring labor certification would be impractical in light of {{NATURE_OF_ENDEAVOR_OR_QUALIFICATIONS}}. The proposed endeavor involves {{ENTREPRENEURIAL_SELF_DIRECTED_MULTI_CLIENT_PROJECT_BASED_RESEARCH_OR_OTHER_FEATURE}}, which is not readily captured by a single permanent job offer requiring only minimum occupational qualifications. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

Second, the United States would benefit from {{PETITIONER_LAST_NAME}}’s prospective contributions even if other U.S. workers are available because {{BENEFIT_EVEN_IF_WORKERS_AVAILABLE}}. This benefit follows from {{SPECIFIC_CONTRIBUTION_MECHANISM}}, not from a general assertion that the occupation is important.

Third, where supported by the record, the waiver is justified by {{URGENCY_PUBLIC_BENEFIT_ECONOMIC_IMPACT_JOB_CREATION_OR_OTHER_FACTOR}}. The evidence shows {{SUPPORTING_FACTS}}. (Please refer to Exhibit {{EXHIBIT_ID}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

Finally, {{PETITIONER_LAST_NAME}}’s qualifications exceed the minimum credentials that the labor certification process is designed to test. The record shows {{UNIQUE_KNOWLEDGE_SKILLS_OR_ROLE}}, directly tied to {{PROPOSED_ENDEAVOR_TITLE}}. Requiring a job offer and labor certification would therefore provide limited additional protection while delaying or constraining work that the evidence shows would benefit the United States.

On balance, the national benefits of permitting {{PETITIONER_LAST_NAME}} to advance the proposed endeavor outweigh the benefits of requiring a job offer and labor certification. Accordingly, {{PETITIONER_LAST_NAME}} satisfies Prong 3.
```

---

# Conclusion

[[BLOCK:CONCLUSION]]

```text
For the reasons set forth above, {{PETITIONER_FULL_NAME}} satisfies the requirements for EB-2 classification as {{EB2_BASIS}}. The evidence further establishes that {{PRONOUN_POSSESSIVE}} proposed endeavor has substantial merit and national importance, that {{PRONOUN_SUBJECT}} is well positioned to advance the endeavor, and that, on balance, it would be beneficial to the United States to waive the job offer and labor certification requirements.

Accordingly, {{PETITIONER_FULL_NAME}} respectfully requests that USCIS approve the Form I-140 petition under the EB-2 classification with a National Interest Waiver.
```

---

# List of Exhibits placeholder

The script should generate this section from exhibit metadata after all blocks are drafted.

```text
List of Exhibits

General Documents. Exhibits from {{RANGE}}; Pages from {{PAGE_XX}} to {{PAGE_YY}}
Exhibit {{EXHIBIT_ID}}. {{DOCUMENT_TITLE}}

Basic Eligibility for EB-2. Exhibits from {{RANGE}}; Pages from {{PAGE_XX}} to {{PAGE_YY}}
Exhibit {{EXHIBIT_ID}}. {{DOCUMENT_TITLE}}

Prong 1: Evidence That the Proposed Endeavor Has Substantial Merit and National Importance. Exhibits from {{RANGE}}; Pages from {{PAGE_XX}} to {{PAGE_YY}}
Exhibit {{EXHIBIT_ID}}. {{DOCUMENT_TITLE}}

Prong 2: Evidence That the Petitioner Is Well Positioned to Advance the Proposed Endeavor. Exhibits from {{RANGE}}; Pages from {{PAGE_XX}} to {{PAGE_YY}}
Exhibit {{EXHIBIT_ID}}. {{DOCUMENT_TITLE}}

Prong 3: On Balance, It Would Be Beneficial to the United States to Waive the Job Offer and Labor Certification Requirements. Exhibits from {{RANGE}}; Pages from {{PAGE_XX}} to {{PAGE_YY}}
Exhibit {{EXHIBIT_ID}}. {{DOCUMENT_TITLE}}
```
