# EB-2 NIW Master Petition Template

Версия: 2026-06-23  
Назначение: мастер-шаблон для подготовки EB-2 NIW petition memorandum, cover letter, exhibit list и технических страниц-разделителей.  
Язык итоговой петиции: английский.  
Язык служебных инструкций: русский.  
Основа структуры: разобранный кейс EB-2 NIW по Mr. Sergei Iltiakov и предоставленный текст USCIS Policy Manual, Vol. 6, Part F, Chapter 5.

---

## 0. Как пользоваться этим шаблоном

Этот шаблон построен как рабочая архитектура петиции, а не как один длинный пример, где надо механически заменить имя. Его можно использовать человеком или LLM-агентом.

Главная логика:

1. Сначала доказывается threshold eligibility for EB-2: заявитель должен пройти как advanced degree professional и/или как person of exceptional ability.
2. Только после этого доказывается National Interest Waiver по Matter of Dhanasar: Prong 1, Prong 2, Prong 3.
3. Каждый фактический тезис в memorandum должен иметь exhibit reference.
4. Каждый exhibit должен быть отражен в List of Exhibits и иметь техническую страницу-разделитель.
5. Если критерий или раздел не используется в конкретном кейсе, он остается в мастер-шаблоне как optional, но удаляется из финальной filing version.

LLM-запреты, потому что иначе машина начнет писать красивую юридическую кашу:

- Не придумывать факты, должности, суммы, даты, источники, клиентов, awards, memberships, contracts.
- Не утверждать national importance только через “the occupation is important” или “there is a national shortage.” USCIS Policy Manual прямо указывает, что этого недостаточно.
- Не смешивать occupation и proposed endeavor. Occupation шире, proposed endeavor конкретнее.
- Не строить Prong 1 на выгоде одному работодателю или одному клиенту без broader implications.
- Не использовать letters как единственную опору для сильных claims, если нужны independent evidence, business records, contracts, invoices, media, official sources, metrics.
- Не оставлять page placeholders без последующего обновления.
- Не хардкодить USCIS fees, lockbox address, edition dates of forms, premium processing availability. Эти данные проверяются перед подачей.

Обозначения placeholders:

- `{{PETITIONER_FULL_NAME}}` — полное имя заявителя.
- `{{PETITIONER_ADDRESS}}` — адрес заявителя.
- `{{DATE}}` — дата письма/петиции.
- `{{PRONOUN_SUBJECT}}`, `{{PRONOUN_OBJECT}}`, `{{PRONOUN_POSSESSIVE}}` — he/she/they, him/her/them, his/her/their.
- `{{FIELD_OF_ENDEAVOR}}` — область endeavor, например telecommunications infrastructure operations.
- `{{INTENDED_OCCUPATION}}` — intended occupation, например telecommunications operations executive.
- `{{PROPOSED_ENDEAVOR_TITLE}}` — краткое название конкретного endeavor.
- `{{PROPOSED_ENDEAVOR_DESCRIPTION_1_SENTENCE}}` — endeavor в одном предложении.
- `{{US_ENTITY_NAME}}` — компания/организация в США, если есть.
- `{{EB2_BASIS}}` — Advanced Degree / Exceptional Ability / Both.
- `{{EXHIBIT_CODE}}` — код приложения, например A.2.R4-1.
- `{{PAGE_XX}}` — номер страницы после финальной сборки.
- `{{SOURCE_NAME}}` — официальный или независимый источник.
- `{{CLAIM}}` — тезис, который нужно доказать.
- `{{EVIDENCE_SUMMARY}}` — краткое описание доказательства.

Рекомендуемый формат ссылок внутри petition memorandum:

`(Please refer to Exhibit {{EXHIBIT_CODE}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)`

Если документ содержит оригинал и перевод:

`(Please refer to Exhibit {{EXHIBIT_CODE}}, pp. {{PAGE_XX}}-{{PAGE_YY}}: {{DOCUMENT_TITLE}}, with certified English translation.)`

---

## 1. Master Table of Contents

Использовать как структуру для финальной петиции. Номера страниц обновляются после верстки.

```text
{{PETITIONER_FULL_NAME}}
{{PETITIONER_ADDRESS}}
Petition for Classification Under the EB-2 Category with a Request for a National Interest Waiver

Table of Contents

1. Forms and Filing Materials
1.1. Form G-1145, E-Notification of Application/Petition Acceptance [optional]
1.2. Form I-140, Immigrant Petition for Alien Worker, with filing fee [verify current fee]
1.3. Asylum Program Fee, if applicable [verify current USCIS fee rule]
1.4. Form I-907, Request for Premium Processing, with filing fee [optional; verify availability and current fee]
1.5. Employee-specific portions of ETA Form 9089 or ETA Form 750B, if applicable under current filing instructions
1.6. Photocopy of passport biographic page and U.S. immigration status documents, if applicable
1.7. Translations and translation certifications, if applicable

2. Petition Memorandum
2.1. Cover Letter and Executive Summary ........................................ pg. {{PAGE_XX}}
2.2. Overview ................................................................ pg. {{PAGE_XX}}
2.3. Basic Eligibility for EB-2 ............................................. pg. {{PAGE_XX}}
A.1. Advanced Degree Professional [optional] ............................... pg. {{PAGE_XX}}
A.2. Exceptional Ability [optional] ......................................... pg. {{PAGE_XX}}
A.2.R1. Official Academic Record .......................................... pg. {{PAGE_XX}}
A.2.R2. At Least Ten Years of Full-Time Experience ....................... pg. {{PAGE_XX}}
A.2.R3. License or Certification .......................................... pg. {{PAGE_XX}}
A.2.R4. Salary or Other Remuneration Demonstrating Exceptional Ability ... pg. {{PAGE_XX}}
A.2.R5. Membership in Professional Associations .......................... pg. {{PAGE_XX}}
A.2.R6. Recognition for Achievements and Significant Contributions ........ pg. {{PAGE_XX}}
A.2.FM. Final Merits Determination for Exceptional Ability ............... pg. {{PAGE_XX}}
2.4. Eligibility for National Interest Waiver ............................ pg. {{PAGE_XX}}
B.0. Proposed Endeavor .................................................... pg. {{PAGE_XX}}
B.1. Prong 1: Substantial Merit and National Importance .................. pg. {{PAGE_XX}}
B.1.1. Substantial Merit .................................................. pg. {{PAGE_XX}}
B.1.2. National Importance ................................................ pg. {{PAGE_XX}}
B.1.3. Broader Implications Beyond One Employer or Local Benefit .......... pg. {{PAGE_XX}}
B.2. Prong 2: Well Positioned to Advance the Proposed Endeavor ........... pg. {{PAGE_XX}}
B.2.1. Education, Skills, Knowledge, and Record of Success ................ pg. {{PAGE_XX}}
B.2.2. Detailed Proposal or Plan for Future Activities .................... pg. {{PAGE_XX}}
B.2.3. Progress, Use by Others, Customers, Partners, Investors, and Support pg. {{PAGE_XX}}
B.2.3.1. Work Already Used by Others / Completed Projects ................. pg. {{PAGE_XX}}
B.2.3.2. Prospective Customers, Partners, Investors, or Relevant Entities . pg. {{PAGE_XX}}
B.2.3.3. Feasible Plans for Financial Support ............................. pg. {{PAGE_XX}}
B.2.3.4. Contracts, Agreements, Licenses, or Similar Records .............. pg. {{PAGE_XX}}
B.2.3.5. Published Materials / Media / Independent Recognition ............ pg. {{PAGE_XX}}
B.2.4. Totality of Circumstances Under Prong 2 ........................... pg. {{PAGE_XX}}
B.3. Prong 3: On Balance, Waiver of Job Offer and Labor Certification .... pg. {{PAGE_XX}}
B.3.1. Impracticality of Labor Certification .............................. pg. {{PAGE_XX}}
B.3.2. Unique Knowledge, Skills, or Entrepreneurial Role .................. pg. {{PAGE_XX}}
B.3.3. Benefits Even if Other U.S. Workers Are Available .................. pg. {{PAGE_XX}}
B.3.4. Urgency, Public Benefit, or Time-Sensitive Need .................... pg. {{PAGE_XX}}
B.3.5. Economic Impact, Job Creation, Regional or Sectoral Effects ........ pg. {{PAGE_XX}}
B.3.6. Balance Conclusion ................................................. pg. {{PAGE_XX}}
2.5. Conclusion ........................................................... pg. {{PAGE_XX}}

3. List of Exhibits ....................................................... pg. {{PAGE_XX}}
```

---

## 2. Filing Materials Checklist

Финальный пакет обычно начинается с форм и filing materials. Точные fees, addresses, edition dates и filing instructions должны проверяться перед отправкой. Да, бюрократия требует обновлять даже то, что вчера казалось стабильным. Земля пока вращается.

```text
1. Forms and Filing Materials

1.1. Form G-1145, E-Notification of Application/Petition Acceptance [optional]
1.2. Form I-140, Immigrant Petition for Alien Worker
     - Filing fee: {{CURRENT_I_140_FEE}}
     - Asylum Program Fee: {{CURRENT_ASYLUM_PROGRAM_FEE_OR_NA}}
1.3. Form I-907, Request for Premium Processing [optional]
     - Premium processing fee: {{CURRENT_I_907_FEE}}
1.4. Employee-specific portions of ETA Form 9089 or ETA Form 750B, if applicable under current instructions
1.5. Passport biographic page
1.6. Current and prior U.S. immigration status documents, if applicable
1.7. I-94, visa, approval notices, EAD, if applicable
1.8. Certified translations for all non-English documents
1.9. Petition Memorandum
1.10. Exhibit List
1.11. Exhibits with technical divider pages
```

USCIS Policy Manual insertion to keep in the working draft:

> A petition filed with a request for a national interest waiver on behalf of a person does not need to be supported by a job offer; therefore, the person may file as a self-petitioner. A waiver of a job offer also includes a waiver of the permanent labor certification requirement. In support of the petition, however, the petitioner must submit the employee-specific portions of a permanent labor certification, without DOL approval. The petitioner may submit either the Form ETA 750B or Form ETA 9089.

Drafting rule:

- If the final USCIS instructions no longer require a specific ETA filing component or require a different version, update this checklist.
- If the petitioner is outside the United States, remove U.S. status documents unless relevant.
- If premium processing is not used, remove I-907 from the cover letter and exhibit list.

---

## 3. Cover Letter Template

Этот блок можно почти полностью сохранять из кейса, заменяя facts, basis, endeavor и references. Структура хорошая: адрес, caption, statutory basis, EB-2 basis, NIW three-prong summary, request for approval.

```text
Immigrant Petition for Alien Worker Under the EB-2 Category with a Request for a National Interest Waiver on Behalf of {{PETITIONER_FULL_NAME}}

{{DATE}}

To:
USCIS {{LOCKBOX_OR_SERVICE_CENTER_NAME}}
{{USCIS_ADDRESS_LINE_1}}
{{USCIS_ADDRESS_LINE_2}}
{{USCIS_ADDRESS_LINE_3}}

From:
{{PETITIONER_FULL_NAME}}
{{PETITIONER_ADDRESS}}

RE: Petition for Classification Under the EB-2 Category with a Request for a National Interest Waiver
Petitioner/Beneficiary: {{PETITIONER_FULL_NAME}}
Classification Sought: INA § 203(b)(2), Employment-Based Second Preference (EB-2) with National Interest Waiver
Type of Petition: Form I-140, Immigrant Petition for Alien Worker (EB-2 NIW)

Dear Immigration Officer:

The following evidence is submitted in support of the Immigrant Petition for Alien Worker (Form I-140) filed by {{PETITIONER_FULL_NAME}}, seeking classification under the Employment-Based Second Preference (EB-2) category pursuant to section 203(b)(2) of the Immigration and Nationality Act (INA), with a request for a National Interest Waiver (NIW).

The evidence presented demonstrates that {{PETITIONER_FULL_NAME}} satisfies the statutory and regulatory requirements for classification under the EB-2 category, as well as the discretionary waiver standard established in Matter of Dhanasar, 26 I&N Dec. 884 (AAO 2016), for the following reasons:

1. {{PETITIONER_LAST_NAME}} qualifies for classification as {{AN_ADVANCED_DEGREE_PROFESSIONAL_AND_OR_PERSON_OF_EXCEPTIONAL_ABILITY}}.

[If using Advanced Degree]
{{PETITIONER_LAST_NAME}} qualifies for classification as a member of the professions holding an advanced degree under 8 C.F.R. § 204.5(k)(2), as {{PRONOUN_SUBJECT}} possesses {{A_US_ADVANCED_DEGREE_OR_FOREIGN_EQUIVALENT_OR_BACHELOR_PLUS_5_PROGRESSIVE_YEARS}} in a field directly related to {{PRONOUN_POSSESSIVE}} proposed endeavor. {{PRONOUN_POSSESSIVE_CAP}} academic credentials in {{FIELD_OF_STUDY}}, supported by {{CREDENTIAL_EVALUATION_OR_OTHER_EVIDENCE}}, establish that {{PRONOUN_SUBJECT}} meets the advanced degree requirement. (See Section A.1.)

[If using Exceptional Ability]
In the alternative, and independently, {{PETITIONER_LAST_NAME}} demonstrates exceptional ability in {{FIELD_OF_EXCEPTIONAL_ABILITY}} pursuant to 8 C.F.R. § 204.5(k)(3)(ii). {{PRONOUN_SUBJECT_CAP}} satisfies at least three regulatory criteria, including:
- {{EA_CRITERION_1}};
- {{EA_CRITERION_2}};
- {{EA_CRITERION_3}};
- {{EA_CRITERION_4_OPTIONAL}};
- {{EA_CRITERION_5_OPTIONAL}}.
(See Section A.2.)

2. {{PETITIONER_LAST_NAME}} seeks a waiver of the job offer and labor certification requirements in the national interest of the United States. {{PRONOUN_POSSESSIVE_CAP}} proposed endeavor is {{PROPOSED_ENDEAVOR_DESCRIPTION_1_SENTENCE}}. (See Section B.0.)

2.1. The proposed endeavor has substantial merit and national importance because {{ONE_SENTENCE_PRONG_1_SUMMARY}}. (See Section B.1.)

2.2. {{PETITIONER_LAST_NAME}} is well positioned to advance the proposed endeavor based on {{ONE_SENTENCE_PRONG_2_SUMMARY}}. (See Section B.2.)

2.3. On balance, it would be beneficial to the United States to waive the requirements of a job offer and labor certification because {{ONE_SENTENCE_PRONG_3_SUMMARY}}. (See Section B.3.)

Accordingly, pursuant to INA § 203(b)(2), 8 C.F.R. § 204.5(k), the USCIS Policy Manual guidance on national interest waivers, and the analytical framework established in Matter of Dhanasar, {{PETITIONER_FULL_NAME}} respectfully requests classification under the EB-2 category and approval of the National Interest Waiver.

Neither a specific job offer nor a labor certification is required for this classification where USCIS grants the national interest waiver under 8 C.F.R. § 204.5(k)(4)(ii).

Respectfully submitted,

{{PETITIONER_FULL_NAME}}
{{DATE}}
```

Cover letter drafting rule:

- Keep this letter short. It is not the memorandum.
- Use it as an executive routing document: who, what classification, what basis, why eligible, where to look.
- If only Advanced Degree is used, remove Exceptional Ability language.
- If only Exceptional Ability is used, remove Advanced Degree language.
- If both are used, write “in the alternative, and independently” only when both sections are actually developed.
- Do not list a weak exceptional ability criterion just to look busy. USCIS is not grading vibes.

---

## 4. Petition Memorandum: Overview

Purpose: give the officer a clean map of the case before dense legal analysis begins.

Required content:

1. Who the petitioner is.
2. Field and intended occupation.
3. Proposed endeavor in plain English.
4. What problem the endeavor addresses.
5. What the petitioner has already done.
6. EB-2 basis: Advanced Degree, Exceptional Ability, or both.
7. Why the endeavor satisfies Dhanasar.
8. One-paragraph conclusion.

Template:

```text
Overview

{{PETITIONER_FULL_NAME}} is {{A_SHORT_PROFESSIONAL_IDENTIFIER}} with {{YEARS_OF_EXPERIENCE}} years of experience in {{FIELD_OR_INDUSTRY}}, {{KEY_CREDENTIALS}}, and a record of {{KEY_RECORD_OF_SUCCESS}}.

{{PETITIONER_LAST_NAME}} proposes to advance {{PROPOSED_ENDEAVOR_TITLE}} in the United States. The endeavor is {{PLAIN_ENGLISH_DESCRIPTION_OF_ENDEAVOR}}. It addresses {{SPECIFIC_PROBLEM}}, which affects {{BROADER_FIELD_REGION_PUBLIC_OR_MARKET}}.

The endeavor is already supported by {{EXISTING_COMPANY_PROJECTS_CUSTOMERS_RESEARCH_PATENTS_CONTRACTS_OR_OTHER_PROGRESS}}. The record shows {{METRICS_OR_FACTS}}, including {{METRIC_1}}, {{METRIC_2}}, and {{METRIC_3}}. These facts demonstrate that the petition is based on an operating or credibly planned endeavor, rather than a general intention to work in an important occupation.

{{PETITIONER_LAST_NAME}} qualifies for EB-2 classification as {{EB2_BASIS}}. [Advanced Degree sentence.] [Exceptional Ability sentence.]

The proposed endeavor has substantial merit and national importance because {{PRONG_1_SUMMARY}}. {{PETITIONER_LAST_NAME}} is well positioned to advance it because {{PRONG_2_SUMMARY}}. On balance, waiving the job offer and labor certification requirements would benefit the United States because {{PRONG_3_SUMMARY}}.

For these reasons, {{PETITIONER_FULL_NAME}} satisfies the requirements for EB-2 classification and the national interest waiver.

(Please refer to Exhibit 0, p. {{PAGE_XX}}: {{PETITIONER_LAST_NAME}}’s CV.)
```

LLM drafting instruction:

- Write this section last, after the evidence map is done.
- Limit it to 5–8 paragraphs unless the case is unusually complex.
- Use specific metrics where available: revenue, projects, states, users, citations, patents, deployments, publications, grants, contracts, jobs created, letters, awards.
- Avoid a generic biography. The overview must lead to the legal theory.

---

## 5. Basic Eligibility for EB-2

USCIS Policy Manual insertion:

> To establish eligibility for a national interest waiver, a petitioner must first demonstrate the person’s qualification for the underlying EB-2 visa classification as either a member of the professions holding an advanced degree or an individual of exceptional ability in the sciences, arts, or business. If the person does not have the qualifications for the EB-2 classification, the petition is statutorily ineligible for the national interest waiver.

> Whether demonstrating EB-2 eligibility as an advanced degree professional or as a person of exceptional ability, the petitioner must clearly describe in a straightforward manner the person’s occupation and proposed endeavor. The intended occupation is the one through which the person plans to advance the proposed endeavor, and the proposed endeavor is more specific than the general occupation.

Drafting rule:

- Start EB-2 section by identifying the intended occupation and proposed endeavor.
- Explain the connection between the credential/exceptional ability and the endeavor.
- If the petitioner cannot pass threshold EB-2, the NIW analysis does not matter. This is a gate. A shiny gate, but still a gate.

Template:

```text
Basic Eligibility for EB-2

To qualify for a national interest waiver, {{PETITIONER_FULL_NAME}} must first qualify for the underlying EB-2 classification as either a member of the professions holding an advanced degree or a person of exceptional ability in the sciences, arts, or business.

{{PETITIONER_LAST_NAME}}’s intended occupation is {{INTENDED_OCCUPATION}}. Through this occupation, {{PRONOUN_SUBJECT}} will advance {{PROPOSED_ENDEAVOR_TITLE}}, which is specifically defined as {{PROPOSED_ENDEAVOR_DESCRIPTION_1_SENTENCE}}.

The evidence establishes EB-2 eligibility because {{PETITIONER_LAST_NAME}} qualifies as {{EB2_BASIS}}.
```

---

# A.1. Advanced Degree Professional [optional]

Use this section if the petitioner has:

- U.S. master’s degree or higher;
- foreign equivalent of U.S. master’s degree or higher;
- U.S. bachelor’s degree or foreign equivalent plus at least five years of progressive post-baccalaureate experience in the specialty.

USCIS Policy Manual insertion:

> An advanced degree is any U.S. academic or professional degree or a foreign equivalent degree above that of baccalaureate. A U.S. baccalaureate degree or a foreign equivalent degree followed by at least 5 years of progressive experience in the specialty is considered the equivalent of a master’s degree.

> A beneficiary can satisfy the advanced degree requirement by holding either a U.S. master’s degree or higher or a foreign degree evaluated to be the equivalent of a U.S. master’s degree or higher; or a U.S. bachelor’s degree, or a foreign degree evaluated to be the equivalent of a U.S. bachelor’s degree, plus 5 years of progressive, post-degree work experience.

> The intended occupation through which the person plans to advance the proposed endeavor must meet the definition of a profession. A professional occupation is determined by the general requirements to enter the intended occupation, and not by the credentials of any one person seeking to work in that field.

Template:

```text
[A.1.] Advanced Degree Professional

{{PETITIONER_FULL_NAME}} qualifies for EB-2 classification as a member of the professions holding an advanced degree because {{PRONOUN_SUBJECT}} possesses {{DEGREE_OR_EQUIVALENT}}, and {{PRONOUN_POSSESSIVE}} intended occupation, {{INTENDED_OCCUPATION}}, is a profession requiring at least a U.S. bachelor’s degree or foreign equivalent for entry.

{{PETITIONER_LAST_NAME}} earned {{DEGREE_NAME}} in {{FIELD_OF_STUDY}} from {{INSTITUTION_NAME}} in {{YEAR}}. The program included coursework in {{COURSEWORK_AREAS}}, directly relevant to {{FIELD_OF_ENDEAVOR}} and {{PROPOSED_ENDEAVOR_TITLE}}.

[If foreign degree]
A credential evaluation prepared by {{EVALUATION_AGENCY}} determined that this degree is equivalent to {{US_EQUIVALENT_DEGREE}} from an accredited U.S. institution. The evaluation explains that {{SUMMARY_OF_EVALUATION_REASONING}}.

[If bachelor + five years]
Alternatively, or additionally, {{PETITIONER_LAST_NAME}} holds {{BACHELOR_DEGREE}} and has at least five years of progressive post-baccalaureate experience in {{SPECIALTY}}, as shown by {{EMPLOYER_LETTERS_OR_EMPLOYMENT_RECORDS}}. This experience occurred after completion of the bachelor’s degree and is directly related to {{PROPOSED_ENDEAVOR_TITLE}}.

The intended occupation of {{INTENDED_OCCUPATION}} qualifies as a profession because {{EVIDENCE_OCCUPATION_REQUIRES_BACHELOR}}, including {{O_NET_BLS_JOB_POSTINGS_PROFESSIONAL_STANDARDS_OR_OTHER_EVIDENCE}}.

{{PETITIONER_LAST_NAME}}’s academic and professional background is directly related to the proposed endeavor. Specifically, {{PRONOUN_POSSESSIVE}} education and training provide expertise in {{SKILL_1}}, {{SKILL_2}}, and {{SKILL_3}}, all of which are necessary to advance {{PROPOSED_ENDEAVOR_TITLE}}.

Accordingly, {{PETITIONER_FULL_NAME}} satisfies the EB-2 requirement of holding an advanced degree, as defined under 8 C.F.R. § 204.5(k)(2), and demonstrates that the degree is directly relevant to the intended occupation and proposed endeavor.

(Please refer to Exhibit A.1, p. {{PAGE_XX}}: {{DEGREE_DOCUMENTS_AND_EVALUATION}}.)
```

Evidence to attach:

```text
A.1-1. Diploma / degree certificate
A.1-2. Academic transcript
A.1-3. Credential evaluation, if foreign degree
A.1-4. Translation and translation certificate, if applicable
A.1-5. Evidence that intended occupation is a profession: BLS/O*NET, job postings, industry standards, licensing rules, expert letter, employer standards
A.1-6. Employer letters documenting five progressive post-baccalaureate years, if relying on bachelor + 5
```

Common problems:

- Degree is advanced, but intended occupation does not normally require a bachelor’s degree.
- Degree field is unrelated to endeavor, and petition does not explain transferability.
- Bachelor + 5 years experience is pre-degree or unrelated to specialty.
- Credential evaluation exists but is conclusory.

---

# A.2. Exceptional Ability [optional]

Use this section if petitioner can satisfy at least three of six regulatory criteria and then pass final merits determination.

USCIS Policy Manual insertion:

> The term exceptional ability is defined as a degree of expertise significantly above that ordinarily encountered in the sciences, arts, or business. This standard is lower than the standard for extraordinary ability classification.

> Officers should use a two-step analysis to evaluate the evidence submitted with the petition to demonstrate eligibility for exceptional ability classification. Step 1: assess whether evidence meets regulatory criteria. Step 2: final merits determination.

> The first step of the evidentiary review is limited to determining whether the evidence submitted with the petition is comprised of at least three of the six regulatory criteria. Meeting the minimum requirement by providing at least three types of initial evidence does not, in itself, establish that the beneficiary in fact meets the requirements for exceptional ability classification.

> Officers must also consider the quality of the evidence. In the second part of the analysis, officers should evaluate the evidence together when considering the petition in its entirety for the final merits determination.

Master structure:

```text
[A.2.] Exceptional Ability

{{PETITIONER_FULL_NAME}} independently qualifies for EB-2 classification as a person of exceptional ability in {{FIELD_OF_EXCEPTIONAL_ABILITY}}. The evidence satisfies at least three of the six regulatory criteria under 8 C.F.R. § 204.5(k)(3)(ii), and, when evaluated in its totality, demonstrates expertise significantly above that ordinarily encountered in {{FIELD_OF_EXCEPTIONAL_ABILITY}}.

The claimed area of exceptional ability is {{FIELD_OF_EXCEPTIONAL_ABILITY}}. This area is directly related to the proposed endeavor because {{DIRECT_CONNECTION_BETWEEN_EA_AND_ENDEAVOR}}.

The petition satisfies the following criteria:

- A.2.R1. Official academic record: {{YES_NO}}
- A.2.R2. At least ten years full-time experience: {{YES_NO}}
- A.2.R3. License or certification: {{YES_NO}}
- A.2.R4. Salary or remuneration demonstrating exceptional ability: {{YES_NO}}
- A.2.R5. Membership in professional associations: {{YES_NO}}
- A.2.R6. Recognition for achievements and significant contributions: {{YES_NO}}

The evidence is then evaluated in the aggregate in Section A.2.FM.
```

LLM rule:

- Do not renumber the six criteria depending on which are used. Use R1–R6 stable regulatory numbering.
- The final filed memorandum may omit unused criteria, but do not shift numbering.
- Include final merits. The source case had strong evidence but the master template should make final merits explicit, because USCIS says Step 1 is not enough.

---

## A.2.R1. Official Academic Record

USCIS Policy Manual insertion:

> The initial evidence may include an official academic record showing that the beneficiary has a degree, diploma, certificate, or similar award from a college, university, school, or other institution of learning relating to the area of exceptional ability.

Template:

```text
A.2.R1. Official Academic Record Relating to the Area of Exceptional Ability

{{PETITIONER_FULL_NAME}} satisfies the regulatory criterion requiring an official academic record relating to {{PRONOUN_POSSESSIVE}} area of exceptional ability.

{{PETITIONER_LAST_NAME}} holds {{DEGREE_DIPLOMA_CERTIFICATE}} in {{FIELD_OF_STUDY}}, awarded by {{INSTITUTION_NAME}} in {{YEAR}}. This academic record relates directly to {{FIELD_OF_EXCEPTIONAL_ABILITY}} because the program covered {{RELEVANT_COURSEWORK}}, including {{COURSE_1}}, {{COURSE_2}}, and {{COURSE_3}}.

[If applicable]
A U.S. credential evaluation confirms that the degree is equivalent to {{US_EQUIVALENT}}. This supports the academic standing and relevance of the credential within the United States.

[If professional certificates are included here]
In addition to formal academic education, {{PETITIONER_LAST_NAME}} completed {{PROFESSIONAL_TRAINING_OR_CERTIFICATE}}, which is relevant to {{SPECIFIC_COMPETENCY}} within {{FIELD_OF_EXCEPTIONAL_ABILITY}}.

This evidence demonstrates that {{PETITIONER_LAST_NAME}} possesses formal education directly related to {{FIELD_OF_EXCEPTIONAL_ABILITY}} and {{PROPOSED_ENDEAVOR_TITLE}}.

(Please refer to Exhibit A.2.R1, p. {{PAGE_XX}}: {{ACADEMIC_RECORDS}}.)
```

Evidence:

```text
A.2.R1-1. Degree / diploma / certificate
A.2.R1-2. Transcript
A.2.R1-3. Credential evaluation
A.2.R1-4. Professional training certificates related to field
A.2.R1-5. Translation certification
```

Drafting caution:

- A degree alone may meet this criterion but does not prove exceptional ability in final merits.
- Explain relevance to the area of exceptional ability, not merely existence of education.

---

## A.2.R2. At Least Ten Years of Full-Time Experience

USCIS Policy Manual insertion:

> The initial evidence may include evidence in the form of letter(s) from current or former employer(s) showing that the beneficiary has at least 10 years of full-time experience in the occupation in which he or she is being sought.

Template:

```text
A.2.R2. Letters from Current or Former Employers Documenting at Least Ten Years of Full-Time Experience

{{PETITIONER_FULL_NAME}} satisfies the regulatory criterion requiring letters from current or former employers documenting at least ten years of full-time experience in {{INTENDED_OCCUPATION_OR_RELATED_OCCUPATION}}.

The record documents full-time professional activity beginning in {{START_YEAR}} and continuing through {{END_YEAR_OR_PRESENT}}. During this period, {{PETITIONER_LAST_NAME}} held positions including {{POSITION_1}}, {{POSITION_2}}, and {{POSITION_3}}, with responsibilities in {{RESPONSIBILITY_CLUSTER}}.

The following documents establish the required experience:

{{EXPERIENCE_DOCUMENT_TABLE}}

These roles are directly relevant to the occupation and proposed endeavor because they required {{SKILL_1}}, {{SKILL_2}}, {{SKILL_3}}, and {{SKILL_4}}, which are the same competencies necessary to advance {{PROPOSED_ENDEAVOR_TITLE}}.

[Employer 1 subsection]
{{EMPLOYER_1_NAME}}, {{DATES}}
{{EMPLOYER_1_LETTER_SUMMARY}}
(Please refer to Exhibit A.2.R2-{{N}}, p. {{PAGE_XX}}: {{EMPLOYER_1_DOCUMENT_TITLE}}.)

[Employer 2 subsection]
{{EMPLOYER_2_NAME}}, {{DATES}}
{{EMPLOYER_2_LETTER_SUMMARY}}
(Please refer to Exhibit A.2.R2-{{N}}, p. {{PAGE_XX}}: {{EMPLOYER_2_DOCUMENT_TITLE}}.)

[Continue as needed]

Taken together, the employer letters and employment records demonstrate at least ten years of full-time experience in {{OCCUPATION}}, including progressive responsibility in {{KEY_AREAS}}. This evidence satisfies the criterion under 8 C.F.R. § 204.5(k)(3)(ii).
```

Recommended experience table:

```text
| Employer | Position | Dates | Full-time? | Key responsibilities | Exhibit |
| --- | --- | --- | --- | --- | --- |
| {{EMPLOYER}} | {{POSITION}} | {{DATES}} | {{YES}} | {{SUMMARY}} | A.2.R2-{{N}} |
```

Evidence:

```text
A.2.R2-1. Employment record / labor book / tax record / social security record
A.2.R2-2. Employer letter from {{EMPLOYER_1}}
A.2.R2-3. Employer letter from {{EMPLOYER_2}}
A.2.R2-4. Employment contracts / job descriptions / appointment orders
A.2.R2-5. Performance awards or internal recognition corroborating role
A.2.R2-6. Translation certifications
```

Letter requirements:

- employer name and address;
- signer name, title, contact details;
- exact employment dates;
- full-time status;
- position titles;
- duties;
- achievements or projects;
- relationship to the petitioner;
- signature and date.

Common problems:

- letters say “worked with us” but do not confirm full-time status;
- experience is in another field and connection to endeavor is not explained;
- periods overlap confusingly and no timeline table is provided;
- independent records do not corroborate letters.

---

## A.2.R3. License or Certification [optional]

USCIS Policy Manual insertion:

> The initial evidence may include a license to practice the profession or certification for a particular profession or occupation.

Template:

```text
A.2.R3. License or Certification for the Profession or Occupation

{{PETITIONER_FULL_NAME}} satisfies the regulatory criterion requiring a license to practice the profession or certification for a particular profession or occupation.

{{PETITIONER_LAST_NAME}} holds {{LICENSE_OR_CERTIFICATION_NAME}}, issued by {{ISSUING_AUTHORITY}} on {{DATE}}, valid through {{EXPIRATION_DATE_OR_NA}}. This credential is relevant to {{FIELD_OF_EXCEPTIONAL_ABILITY}} because {{RELEVANCE_EXPLANATION}}.

The license/certification demonstrates that {{PETITIONER_LAST_NAME}} meets recognized professional or technical standards in {{SPECIFIC_AREA}} and is qualified to perform {{ACTIVITIES_AUTHORIZED_OR_CERTIFIED}}.

(Please refer to Exhibit A.2.R3, p. {{PAGE_XX}}: {{LICENSE_OR_CERTIFICATION_DOCUMENT}}.)
```

Evidence:

```text
A.2.R3-1. License / certification
A.2.R3-2. Issuing authority description
A.2.R3-3. Verification page / registry lookup
A.2.R3-4. Explanation of relevance to occupation
A.2.R3-5. Translation certification
```

Drafting caution:

- OSHA-type safety training may support field relevance, but may not always be a “license to practice” or occupation certification. Use carefully.
- If weak, move it to Prong 2 as skills/knowledge evidence rather than forcing it as an exceptional ability criterion.

---

## A.2.R4. Salary or Other Remuneration Demonstrating Exceptional Ability

USCIS Policy Manual insertion:

> The initial evidence may include evidence that the beneficiary has commanded a salary or other remuneration for services that demonstrates exceptional ability. To satisfy this criterion, the evidence must show that the beneficiary has commanded a salary or remuneration for services that is indicative of his or her claimed exceptional ability relative to others working in the field.

Template:

```text
A.2.R4. Evidence of Salary or Other Remuneration Demonstrating Exceptional Ability

{{PETITIONER_FULL_NAME}} satisfies the regulatory criterion requiring evidence that {{PRONOUN_SUBJECT}} has commanded salary or other remuneration for services demonstrating exceptional ability.

The record shows that {{PETITIONER_LAST_NAME}} received {{COMPENSATION_AMOUNT}} in {{YEAR}} from {{SOURCE_OF_COMPENSATION}}, connected to {{FIELD_OF_EXCEPTIONAL_ABILITY}} and {{PROPOSED_ENDEAVOR_OR_OCCUPATION}}. The evidence includes {{TAX_RETURNS_PAYROLL_CONTRACTS_INVOICES_BANK_RECORDS_K1_1099_W2_OR_OTHER}}.

The compensation should be evaluated against benchmarks for {{COMPARABLE_OCCUPATIONS}}, including {{BLS_OES_PRIVATE_MARKET_OR_INDUSTRY_SOURCES}}. These benchmarks are appropriate because {{COMPARABILITY_EXPLANATION}}.

Comparison:

- Petitioner compensation: {{PETITIONER_COMPENSATION}}
- Benchmark 1: {{BENCHMARK_1}} — {{COMPARISON_RESULT}}
- Benchmark 2: {{BENCHMARK_2}} — {{COMPARISON_RESULT}}
- Benchmark 3: {{BENCHMARK_3}} — {{COMPARISON_RESULT}}

This evidence demonstrates that {{PETITIONER_LAST_NAME}} commanded remuneration above ordinary compensation levels for comparable roles in {{FIELD_OR_GEOGRAPHY}}, supporting a finding that the compensation is indicative of exceptional ability.

(Please refer to Exhibit A.2.R4, pp. {{PAGE_XX}}-{{PAGE_YY}}: {{COMPENSATION_EVIDENCE_AND_BENCHMARKS}}.)
```

Recommended compensation table:

```text
| Year | Source | Amount | Evidence | Notes |
| --- | --- | ---: | --- | --- |
| {{YEAR}} | {{SOURCE}} | {{AMOUNT}} | {{EXHIBIT}} | {{NOTES}} |

| Benchmark | Geography | Period | Amount | Source | Comparison |
| --- | --- | --- | ---: | --- | --- |
| {{OCCUPATION}} | {{AREA}} | {{DATE}} | {{AMOUNT}} | {{SOURCE}} | {{PETITIONER_AMOUNT}} is {{X}}% above |
```

Evidence:

```text
A.2.R4-1. Tax returns / W-2 / 1099 / K-1 / Schedule E / Schedule C / payroll records
A.2.R4-2. Company tax returns, if pass-through or owner remuneration is relevant
A.2.R4-3. Contracts, invoices, bank statements, payment records
A.2.R4-4. BLS/OES/O*NET wage data
A.2.R4-5. Industry salary surveys
A.2.R4-6. Private salary sources, if used carefully and dated
A.2.R4-7. Explanation of why selected benchmarks are comparable
```

Common problems:

- comparing owner revenue to employee wages without explaining pass-through/remuneration structure;
- using household income that belongs to spouse or unrelated business;
- selecting low benchmarks to make compensation look high;
- failing to show “relative to others working in the field.”

---

## A.2.R5. Membership in Professional Associations

USCIS Policy Manual insertion:

> The initial evidence may include evidence of membership in professional associations.

Policy Manual caution:

> Objectively meeting the regulatory criteria alone does not establish that the beneficiary in fact meets the requirements for exceptional ability classification. For example, being a member of professional associations alone, regardless of the caliber, should satisfy one of the three required regulatory criteria. However, the beneficiary's membership should also be evaluated to determine whether it is indicative of the beneficiary having a degree of expertise significantly above that ordinarily encountered.

Template:

```text
A.2.R5. Membership in Professional Associations

{{PETITIONER_FULL_NAME}} satisfies the regulatory criterion relating to membership in professional associations through {{PRONOUN_POSSESSIVE}} membership in {{ASSOCIATION_NAME}}.

{{ASSOCIATION_NAME}} is {{DESCRIPTION_OF_ASSOCIATION}}, serving {{FIELD_OR_INDUSTRY}}. Membership is relevant to {{FIELD_OF_EXCEPTIONAL_ABILITY}} because {{RELEVANCE}}.

{{PETITIONER_LAST_NAME}} has been a member since {{DATE}} / maintains active membership valid through {{DATE}}. Through this membership, {{PRONOUN_SUBJECT}} has access to / participates in {{COMMITTEES_WORKING_GROUPS_PROFESSIONAL_STANDARDS_POLICY_ADVOCACY_EVENTS_OR_OTHER}}.

[If membership is company-level]
Although the membership is held by {{US_ENTITY_NAME}}, {{PETITIONER_LAST_NAME}} is {{ROLE_IN_ENTITY}} and directs the entity’s professional activities in {{FIELD}}. The membership therefore reflects {{PRONOUN_POSSESSIVE}} active participation in the professional community through the entity.

(Please refer to Exhibit A.2.R5, p. {{PAGE_XX}}: {{MEMBERSHIP_EVIDENCE}}.)
```

Evidence:

```text
A.2.R5-1. Membership certificate
A.2.R5-2. Membership profile / directory page
A.2.R5-3. Association description
A.2.R5-4. Membership criteria
A.2.R5-5. Evidence of participation: committees, events, working groups, publications, presentations
```

Common problems:

- membership is open to anyone who pays a fee;
- no evidence of petitioner’s active role;
- company registration in a government system is mischaracterized as professional association membership. It may be useful evidence elsewhere, but be careful.

---

## A.2.R6. Recognition for Achievements and Significant Contributions

USCIS Policy Manual insertion:

> The initial evidence may include evidence of recognition for achievements and significant contributions to the industry or field by peers, governmental entities, or professional or business organizations.

Template:

```text
A.2.R6. Recognition for Achievements and Significant Contributions to the Industry or Field

{{PETITIONER_FULL_NAME}} satisfies the regulatory criterion requiring evidence of recognition for achievements and significant contributions to {{FIELD_OF_EXCEPTIONAL_ABILITY}} by peers, governmental entities, professional organizations, or business organizations.

The record includes {{NUMBER_OF_LETTERS_OR_RECOGNITION_DOCUMENTS}} letters / awards / institutional recognitions / media records from {{RECOGNIZING_ENTITIES}}. These materials recognize {{PETITIONER_LAST_NAME}} for {{SPECIFIC_RECOGNIZED_CONTRIBUTION}}, including {{CONTRIBUTION_1}}, {{CONTRIBUTION_2}}, and {{CONTRIBUTION_3}}.

The strongest evidence comes from {{STRONGEST_RECOGNIZING_ENTITIES}}, because they are {{WHY_RELEVANT_AND_CREDIBLE}} and have first-hand knowledge of {{PETITIONER_LAST_NAME}}’s work.

Recognition summary:

{{RECOGNITION_TABLE}}

[Subsection for each major letter or recognition]

{{RECOGNIZING_ENTITY_1}}
{{DESCRIPTION_OF_ENTITY}}
{{SUMMARY_OF_RECOGNITION}}
Selected recognition statement:
"{{SHORT_QUOTE_OR_PARAPHRASE}}"
(Please refer to Exhibit A.2.R6-{{N}}, p. {{PAGE_XX}}: {{DOCUMENT_TITLE}}.)

Taken together, these materials show recognition for a specific contribution to the field: {{SPECIFIC_FIELD_CONTRIBUTION}}. The evidence does not merely confirm employment or routine performance. It identifies {{PETITIONER_LAST_NAME}}’s contribution as {{WHY_SIGNIFICANT}}.
```

Recommended recognition table:

```text
| Entity / person | Type | Relationship | What is recognized | Independent corroboration | Exhibit |
| --- | --- | --- | --- | --- | --- |
| {{ENTITY}} | {{peer / customer / government / association / employer}} | {{relationship}} | {{recognized contribution}} | {{contracts / metrics / media / records}} | A.2.R6-{{N}} |
```

Evidence:

```text
A.2.R6-1. Support letter from peer / expert / organization
A.2.R6-2. Award certificate or official award page
A.2.R6-3. Government or quasi-government recognition
A.2.R6-4. Customer or institutional user letter
A.2.R6-5. Contracts, work orders, metrics, publications, screenshots corroborating the contribution
A.2.R6-6. Evidence of the recognizing entity’s reputation or relevance
```

Common problems:

- letters are generic praise and do not identify significant contribution;
- letters are from friends or clients with no field-level perspective;
- no independent corroboration;
- recognition is for company/team but not petitioner’s role;
- “significant contribution” is asserted, but field impact is not explained.

---

## A.2.FM. Final Merits Determination for Exceptional Ability

This section is essential if using Exceptional Ability. Step 1 says at least three criteria are met. Final merits says the evidence, in totality, shows expertise significantly above the ordinary level.

USCIS Policy Manual insertion:

> Meeting the minimum requirement by providing at least three types of initial evidence does not, in itself, establish that the beneficiary in fact meets the requirements for exceptional ability classification. Officers must also consider the quality of the evidence.

> The petitioner must demonstrate that the beneficiary is above others in the field; qualifications possessed by most members of a given field cannot demonstrate a degree of expertise significantly above that ordinarily encountered.

> Formal recognition in the form of certificates and other documentation that are contemporaneous with the beneficiary's claimed contributions and achievements may have more weight than letters prepared for the petition recognizing the beneficiary's achievements.

Template:

```text
A.2.FM. Final Merits Determination for Exceptional Ability

After satisfying at least three regulatory criteria, the evidence must be evaluated in the aggregate to determine whether {{PETITIONER_FULL_NAME}} has a degree of expertise significantly above that ordinarily encountered in {{FIELD_OF_EXCEPTIONAL_ABILITY}}.

The totality of the record supports this determination for several reasons.

First, {{PETITIONER_LAST_NAME}}’s education and specialized training provide a formal foundation in {{RELEVANT_KNOWLEDGE_AREA}}, directly related to {{FIELD_OF_EXCEPTIONAL_ABILITY}}. (See Section A.2.R1.)

Second, {{PRONOUN_SUBJECT}} has accumulated more than ten years of full-time experience in {{OCCUPATION}}, including progressive responsibility in {{PROGRESSIVE_RESPONSIBILITY}}, rather than ordinary or entry-level work. (See Section A.2.R2.)

Third, {{PRONOUN_SUBJECT}} has commanded remuneration that exceeds relevant benchmarks for comparable professionals in {{FIELD_OR_GEOGRAPHY}}, indicating market recognition of {{PRONOUN_POSSESSIVE}} professional value. (See Section A.2.R4.)

Fourth, {{PRONOUN_SUBJECT}} participates in professional associations or professional frameworks relevant to {{FIELD}}, supporting {{PRONOUN_POSSESSIVE}} integration into the field. (See Section A.2.R5.)

Fifth, and most importantly, independent entities have recognized {{PETITIONER_LAST_NAME}} for {{SPECIFIC_SIGNIFICANT_CONTRIBUTION}}, with corroborating evidence showing {{METRICS_OR_IMPACT}}. (See Section A.2.R6.)

These facts show more than possession of ordinary qualifications. They demonstrate {{PETITIONER_LAST_NAME}}’s above-ordinary expertise in {{FIELD}}, particularly in {{NICHE_OR_SPECIALIZATION}}, which is directly related to {{PROPOSED_ENDEAVOR_TITLE}}.

Accordingly, the evidence establishes by a preponderance of the evidence that {{PETITIONER_FULL_NAME}} qualifies as a person of exceptional ability under INA § 203(b)(2) and 8 C.F.R. § 204.5(k).
```

LLM rule:

- This section should not repeat every fact. It should synthesize.
- Strongest evidence should be objective: metrics, awards, contracts, adoption, citations, financials, official records, contemporaneous documents.
- Letters can support, but they should not carry the whole section like a sad legal backpack.

---

# B. National Interest Waiver

USCIS Policy Manual insertion:

> To establish eligibility for the national interest waiver, the petitioner has the burden of demonstrating that the person qualifies as either a member of the professions holding an advanced degree or as a person of exceptional ability; and the waiver of the job offer requirement, and thus, the labor certification requirement, is in the “national interest.”

> Qualification for the EB-2 classification as a member of the professions holding an advanced degree or as a person of exceptional ability does not automatically mean that the person qualifies for a national interest waiver.

> USCIS may grant a national interest waiver as a matter of discretion if the petitioner demonstrates eligibility by a preponderance of the evidence, based on the following three prongs: the alien’s proposed endeavor has both substantial merit and national importance; the alien is well positioned to advance the proposed endeavor; and on balance, it would be beneficial to the United States to waive the job offer and thus the permanent labor certification requirements.

Template intro:

```text
B. National Interest Waiver

Having established eligibility for the underlying EB-2 classification, {{PETITIONER_FULL_NAME}} respectfully requests a waiver of the job offer and labor certification requirements in the national interest.

The proposed endeavor is {{PROPOSED_ENDEAVOR_TITLE}}. This endeavor has substantial merit and national importance, {{PETITIONER_LAST_NAME}} is well positioned to advance it, and, on balance, waiving the job offer and labor certification requirements would benefit the United States.
```

---

## B.0. Proposed Endeavor

This is the anchor of the petition. If this section is vague, everything downstream rots. A lovely botanical process, except with RFEs.

USCIS Policy Manual insertion:

> The term “endeavor” is more specific than the general occupation; a petitioner should offer details not only as to what the occupation normally involves, but what types of work the person proposes to undertake specifically within that occupation.

> When explaining the endeavor, the petitioner should do so in a straightforward manner and clearly lay out the potential direct impacts of the endeavor and whether the endeavor will be furthered through the course of the person’s duties at a particular employer or some other way.

Template:

```text
[B.0.] Proposed Endeavor

Endeavor: {{PROPOSED_ENDEAVOR_TITLE}}

{{PETITIONER_FULL_NAME}} proposes to {{ACTION_VERB_1}}, {{ACTION_VERB_2}}, and {{ACTION_VERB_3}} {{SPECIFIC_WORK_PRODUCT_SERVICE_RESEARCH_BUSINESS_MODEL_OR_PROGRAM}} in the United States. The endeavor will be advanced through {{US_ENTITY_NAME_OR_EMPLOYMENT_RESEARCH_APPOINTMENT_SELF_EMPLOYMENT_OTHER}}, and its primary objective is {{OBJECTIVE}}.

This endeavor is more specific than {{PETITIONER_LAST_NAME}}’s general occupation of {{INTENDED_OCCUPATION}}. While the occupation generally involves {{GENERAL_OCCUPATION_DUTIES}}, the proposed endeavor specifically involves {{SPECIFIC_PROJECTS_PROGRAMS_TECHNOLOGY_MARKET_OR_IMPLEMENTATION_PLAN}}.

The endeavor addresses the following problem:
{{PROBLEM_STATEMENT}}

The proposed solution is:
{{SOLUTION_STATEMENT}}

The operational / research / business model includes:
- {{COMPONENT_1}}
- {{COMPONENT_2}}
- {{COMPONENT_3}}
- {{COMPONENT_4}}

The endeavor will produce potential direct impacts including:
- {{DIRECT_IMPACT_1}}
- {{DIRECT_IMPACT_2}}
- {{DIRECT_IMPACT_3}}

The endeavor will be implemented through the following steps:
1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}
4. {{STEP_4}}

The record includes documentary evidence supporting the proposed endeavor, including {{PROPOSED_ENDEAVOR_STATEMENT}}, {{BUSINESS_PLAN_OR_RESEARCH_PLAN}}, {{COMPANY_DOCUMENTS}}, {{WEBSITE_OR_PUBLIC_MATERIALS}}, and {{OTHER_SUPPORTING_DOCUMENTS}}.

(Please refer to Exhibit B.0, pp. {{PAGE_XX}}-{{PAGE_YY}}: {{ENDEAVOR_DOCUMENTS}}.)
```

Evidence:

```text
B.0-1. Proposed Endeavor Statement
B.0-2. Business plan / research plan / implementation plan
B.0-3. Company formation documents, if entrepreneur
B.0-4. Website pages, pitch deck, product pages, technical documentation
B.0-5. Roadmap, milestones, budget, staffing plan
B.0-6. Letters explaining planned work
B.0-7. Existing contracts, statements of work, invoices, project records
```

LLM rule:

- The proposed endeavor should be one defined project/system/program/business/research direction, not “work as a data analyst” or “continue career in business.”
- Include who benefits, how, through what mechanism, and what evidence supports feasibility.
- If there is a U.S. entity, describe its role, but do not reduce national importance to that entity’s revenue.

---

## B.1. Prong 1: Substantial Merit and National Importance

USCIS Policy Manual insertion:

> The endeavor’s merit may be demonstrated in areas including, but not limited to, business, entrepreneurship, science, technology, culture, health, or education.

> Merit may be established without immediate or quantifiable economic impact, and endeavors related to research, pure science, and the furtherance of human knowledge may qualify whether or not the potential accomplishments are likely to translate into economic benefits for the United States.

> Officers must also examine the national importance of the specific endeavor proposed by considering its potential prospective impact. Officers should focus on the nature of the proposed endeavor, rather than only the geographic breadth of the endeavor.

> Benefits to a specific employer alone, even an employer with a national footprint, are not sufficiently relevant to whether a person’s endeavor has national importance. At issue is whether the petitioner can demonstrate that the person’s own individual endeavor stands to have broader implications, such as for a field, a region, or the public at large.

> Proposing to work in an occupation with a national shortage or serve in a consulting capacity for others seeking to work in an occupation with a national shortage alone, is also insufficient.

Template intro:

```text
B.1. Prong 1: The Proposed Endeavor Has Both Substantial Merit and National Importance

The proposed endeavor satisfies the first prong of Matter of Dhanasar because it has substantial merit in {{MERIT_AREA}} and national importance through its potential prospective impact on {{FIELD_REGION_PUBLIC_MARKET_OR_NATIONAL_PRIORITY}}.
```

---

### B.1.1. Substantial Merit

Template:

```text
B.1.1. Substantial Merit

{{PROPOSED_ENDEAVOR_TITLE}} has substantial merit because it addresses {{PROBLEM}} in {{AREA}}, a field involving {{BUSINESS_SCIENCE_TECHNOLOGY_HEALTH_CULTURE_EDUCATION_PUBLIC_SAFETY_OR_OTHER}}.

The record demonstrates substantial merit through:

1. {{MERIT_REASON_1}}
   Evidence: {{SOURCE_OR_EXHIBIT}}

2. {{MERIT_REASON_2}}
   Evidence: {{SOURCE_OR_EXHIBIT}}

3. {{MERIT_REASON_3}}
   Evidence: {{SOURCE_OR_EXHIBIT}}

The endeavor’s merit does not depend solely on immediate economic impact. It is independently meritorious because {{NON_ECONOMIC_OR_PUBLIC_INTEREST_REASON}}, and it may also produce economic benefits through {{ECONOMIC_REASON_IF_APPLICABLE}}.
```

Evidence:

```text
B.1-1. Government reports showing problem / priority
B.1-2. Agency guidance / federal program materials
B.1-3. Industry reports
B.1-4. Academic or market research
B.1-5. News or official examples showing urgency/problem
B.1-6. Evidence connecting petitioner’s endeavor to the problem
```

---

### B.1.2. National Importance

Template:

```text
B.1.2. National Importance

The proposed endeavor has national importance because its prospective impact extends beyond {{ONE_EMPLOYER_ONE_CLIENT_LOCAL_JOB}} and has broader implications for {{FIELD_REGION_PUBLIC_AT_LARGE_OR_NATIONAL_SYSTEM}}.

USCIS evaluates national importance by focusing on the nature of the specific endeavor and its potential prospective impact. Here, the proposed endeavor is nationally important for the following reasons:

First, {{NATIONAL_IMPORTANCE_REASON_1}}.
Evidence: {{EVIDENCE_1}}.

Second, {{NATIONAL_IMPORTANCE_REASON_2}}.
Evidence: {{EVIDENCE_2}}.

Third, {{NATIONAL_IMPORTANCE_REASON_3}}.
Evidence: {{EVIDENCE_3}}.

The endeavor is not presented as nationally important merely because {{FIELD_OR_OCCUPATION}} is important. Rather, {{PETITIONER_LAST_NAME}}’s specific endeavor will {{SPECIFIC_MECHANISM_OF_BROADER_IMPACT}}.

Accordingly, the proposed endeavor satisfies the national importance component of Prong 1.
```

Possible national importance theories:

```text
- Field-level impact: endeavor advances a technology, practice, standard, method, research area, or operational model.
- Regional impact: endeavor materially affects an economically depressed, underserved, rural, disaster-affected, or strategic region.
- Public welfare impact: health, safety, education, infrastructure, access to services, civil rights, cybersecurity, resilience.
- Economic impact: significant job creation, investment, productivity, exports, supply-chain resilience, commercialization.
- National priority: alignment with federal programs, agency priorities, national security, competitiveness, critical infrastructure.
- Cultural/artistic enrichment: broader access, preservation, innovation, institutional adoption, recognized cultural contribution.
```

Common problems:

- “The United States needs more {{OCCUPATION}}” without explaining petitioner’s specific endeavor.
- “This company has national clients” without showing field/public implications.
- “The industry is important” without showing the endeavor’s prospective impact.
- “There is a labor shortage” used as a complete argument. Policy Manual says this alone is insufficient. Humanity had one job: read the paragraph.

---

### B.1.3. Broader Implications Beyond One Employer or Local Benefit

Use this subsection when the case involves a company, client, employer, or geographically specific work.

Template:

```text
B.1.3. Broader Implications Beyond One Employer or Local Benefit

The proposed endeavor is not limited to ordinary service for a single employer or private customer. Although {{US_ENTITY_NAME_OR_EMPLOYER}} will be one vehicle through which the endeavor is advanced, the evidence shows that the endeavor has broader implications because {{BROADER_IMPLICATIONS_MECHANISM}}.

Specifically:

- {{BROADER_IMPACT_1}}
- {{BROADER_IMPACT_2}}
- {{BROADER_IMPACT_3}}

The benefit is therefore not merely {{PRIVATE_BENEFIT}}, but {{FIELD_REGION_PUBLIC_OR_NATIONAL_BENEFIT}}.
```

Evidence:

```text
B.1.BI-1. Multi-client adoption
B.1.BI-2. Licensing, replication, open-source release, publications, standards
B.1.BI-3. Government interest
B.1.BI-4. Regional economic data
B.1.BI-5. Public users or institutional users
B.1.BI-6. Evidence of shortage plus petitioner's specific mechanism to address it
```

---

## B.2. Prong 2: Well Positioned to Advance the Proposed Endeavor

USCIS Policy Manual insertion:

> Unlike the first prong, which focuses on the merit and importance of the proposed endeavor, the second prong centers on the person. Specifically, the petitioner must demonstrate that the person is well positioned to advance the endeavor.

> USCIS considers factors including, but not limited to: the person’s education, skills, knowledge, and record of success in related or similar efforts; evidence of a detailed proposal or plan that the person developed, or played a significant role in developing, for future activities related to the proposed endeavor; any progress towards achieving the proposed endeavor; and the interest or support garnered by the person from potential customers, users, investors, or other relevant entities or persons.

> A person may be well-positioned to advance an endeavor even if the person cannot demonstrate that the proposed endeavor is more likely than not to ultimately succeed. However, unsubstantiated claims would not meet the petitioner’s burden of proof.

> Letters may be persuasive when they are from experts in the person’s field who have first-hand knowledge of the person’s achievements, describe those achievements, provide specific examples of how the person is well positioned to advance the person’s endeavor, and are supported by other independent evidence. Business plans or other similar descriptions of the person’s plans, while useful in explaining the person’s objectives, should be supported by other independent evidence.

Template intro:

```text
B.2. Prong 2: {{PETITIONER_FULL_NAME}} Is Well Positioned to Advance the Proposed Endeavor

{{PETITIONER_FULL_NAME}} is well positioned to advance {{PROPOSED_ENDEAVOR_TITLE}} based on {{PRONOUN_POSSESSIVE}} education, skills, knowledge, record of success in related efforts, detailed plan, progress already made, and support from {{CUSTOMERS_USERS_INVESTORS_PARTNERS_GOVERNMENT_OR_OTHER}}.
```

---

### B.2.1. Education, Skills, Knowledge, and Record of Success

Template:

```text
B.2.1. Education, Skills, Knowledge, and Record of Success in Related or Similar Efforts

{{PETITIONER_LAST_NAME}}’s education and professional record directly position {{PRONOUN_OBJECT}} to advance the proposed endeavor.

Education and training:
{{SUMMARY_OF_EDUCATION_RELEVANT_TO_ENDEAVOR}}

Skills and knowledge:
{{SUMMARY_OF_SPECIALIZED_SKILLS}}

Record of success:
{{SUMMARY_OF_PRIOR_RESULTS}}

The connection between past achievements and the proposed endeavor is direct: {{EXPLAIN_TRANSFERABILITY_AND_CONTINUITY}}.

(Please refer to Exhibits {{RELEVANT_EXHIBITS}}.)
```

Evidence:

```text
B.2.1-1. Degrees, certificates, licenses
B.2.1-2. CV
B.2.1-3. Employment letters
B.2.1-4. Awards, grants, patents, publications, media
B.2.1-5. Project metrics and performance records
B.2.1-6. Prior business success or research success
```

---

### B.2.2. Detailed Proposal or Plan

Template:

```text
B.2.2. Detailed Proposal or Plan for Future Activities Related to the Proposed Endeavor

The record includes a detailed plan for advancing {{PROPOSED_ENDEAVOR_TITLE}} in the United States. The plan was developed by {{PETITIONER_FULL_NAME}} / with {{PETITIONER_LAST_NAME}} playing a significant role.

The plan includes:

- Objective: {{OBJECTIVE}}
- Implementation vehicle: {{US_ENTITY_OR_EMPLOYER_OR_RESEARCH_GROUP}}
- Timeline: {{TIMELINE}}
- Key activities: {{KEY_ACTIVITIES}}
- Required resources: {{RESOURCES}}
- Milestones: {{MILESTONES}}
- Expected outputs: {{OUTPUTS}}
- Risk controls: {{RISK_CONTROLS}}
- Metrics: {{METRICS}}

This plan is credible because it is supported by {{INDEPENDENT_SUPPORTING_EVIDENCE}}, including {{EVIDENCE_LIST}}.

(Please refer to Exhibit B.2.2, p. {{PAGE_XX}}: {{PLAN_DOCUMENT}}.)
```

Evidence:

```text
B.2.2-1. Business plan / research plan / project plan
B.2.2-2. Market analysis / technical roadmap
B.2.2-3. Budget and financial forecast
B.2.2-4. Staffing plan
B.2.2-5. Timeline and milestones
B.2.2-6. Proof petitioner developed or controls the plan
```

Drafting caution:

- Business plan is useful, but USCIS wants corroboration. Attach contracts, revenue, letters, investor correspondence, purchase orders, pilots, grants, publications, prototypes, website, user data, etc.

---

### B.2.3. Progress, Use by Others, Customers, Partners, Investors, and Support

Template:

```text
B.2.3. Progress Toward Achieving the Endeavor and Support from Relevant Entities or Persons

{{PETITIONER_LAST_NAME}} has already made concrete progress toward {{PROPOSED_ENDEAVOR_TITLE}}. The record includes {{PROGRESS_EVIDENCE_TYPES}}, showing that the endeavor is not speculative.

The evidence demonstrates:

1. Work already used by others: {{SUMMARY}}
2. Existing or prospective customers/users/partners: {{SUMMARY}}
3. Financial support or feasible financing: {{SUMMARY}}
4. Contracts, agreements, licenses, or other implementation records: {{SUMMARY}}
5. Public materials, media, or independent recognition: {{SUMMARY}}
```

---

#### B.2.3.1. Work Already Used by Others / Completed Projects

Template:

```text
B.2.3.1. Evidence Demonstrating That {{PETITIONER_LAST_NAME}}’s Work Is Already Being Used by Others

The record shows that {{PETITIONER_LAST_NAME}}’s work has already been used by {{CUSTOMERS_USERS_COMPANIES_INSTITUTIONS_OR_FIELD_PARTICIPANTS}}.

Completed work includes:

{{PROJECT_TABLE}}

These records show actual implementation because they include {{CONTRACTS_WORK_ORDERS_INVOICES_SCREENSHOTS_REPORTS_PHOTOS_DELIVERY_RECORDS_USER_DATA_OR_OTHER}}.

[Project subsection]
{{PROJECT_OR_CUSTOMER_NAME}}
{{PROJECT_DESCRIPTION}}
Result: {{RESULT_OR_METRIC}}
Evidence: {{EXHIBIT_REFERENCE}}

This evidence is relevant to Prong 2 because it shows that {{PETITIONER_LAST_NAME}} has already performed work similar to the proposed endeavor and has generated interest or use from relevant entities.
```

Recommended project table:

```text
| Project / customer | Location | Dates | Work performed | Metrics | Evidence | Relevance to endeavor |
| --- | --- | --- | --- | --- | --- | --- |
| {{PROJECT}} | {{LOCATION}} | {{DATES}} | {{WORK}} | {{METRICS}} | B.2.3.1-{{N}} | {{RELEVANCE}} |
```

---

#### B.2.3.2. Prospective Support

Template:

```text
B.2.3.2. Correspondence from Prospective or Potential Customers, Users, Investors, Partners, or Other Relevant Entities

The record includes correspondence and support from {{ENTITIES}}, demonstrating external interest in {{PROPOSED_ENDEAVOR_TITLE}}.

This evidence includes:

- {{LETTER_OR_EMAIL_1}}: {{SUMMARY}}
- {{LETTER_OR_EMAIL_2}}: {{SUMMARY}}
- {{LETTER_OR_EMAIL_3}}: {{SUMMARY}}

The support is probative because {{WHY_SUPPORT_IS_RELEVANT_AND_CREDIBLE}}.

(Please refer to Exhibit B.2.3.2, pp. {{PAGE_XX}}-{{PAGE_YY}}.)
```

Evidence:

```text
B.2.3.2-1. Letters of interest
B.2.3.2-2. Emails from prospective customers/users/partners
B.2.3.2-3. LOIs / MOUs
B.2.3.2-4. Investor communications
B.2.3.2-5. Government or quasi-government letters
B.2.3.2-6. Website inquiries / CRM records / pipeline records
```

---

#### B.2.3.3. Feasible Plans for Financial Support

Template:

```text
B.2.3.3. Documentation Reflecting Feasible Plans for Financial Support

The record demonstrates feasible plans for financial support through {{REVENUE_INVESTMENT_GRANTS_SAVINGS_CONTRACTS_COMMITTED_CUSTOMERS_LOANS_OR_OTHER}}.

The financial support evidence includes {{FINANCIAL_EVIDENCE_LIST}}. These records show that {{PETITIONER_LAST_NAME}} has access to resources reasonably connected to the proposed plan, including {{RESOURCE_1}}, {{RESOURCE_2}}, and {{RESOURCE_3}}.

(Please refer to Exhibit B.2.3.3, p. {{PAGE_XX}}: {{FINANCIAL_SUPPORT_DOCUMENTS}}.)
```

Evidence:

```text
B.2.3.3-1. Bank statements
B.2.3.3-2. Tax returns
B.2.3.3-3. Revenue statements
B.2.3.3-4. Investor letters / term sheets
B.2.3.3-5. Grant documents
B.2.3.3-6. Contracts generating revenue
B.2.3.3-7. Budget and financial forecast
```

---

#### B.2.3.4. Contracts, Agreements, Licenses

Template:

```text
B.2.3.4. Contracts, Agreements, or Licenses Showing Potential Impact of the Proposed Endeavor

The record includes contracts, agreements, licenses, or similar records showing that {{PETITIONER_LAST_NAME}}’s work has practical application and potential impact.

Key documents include:

{{CONTRACT_TABLE}}

These documents support Prong 2 because they show {{IMPLEMENTATION_USE_MARKET_VALIDATION_OR_FIELD_ADOPTION}}.
```

Evidence:

```text
B.2.3.4-1. Customer contracts
B.2.3.4-2. Contractor agreements
B.2.3.4-3. Licensing agreements
B.2.3.4-4. Statements of work
B.2.3.4-5. Purchase orders
B.2.3.4-6. Invoices tied to contracts
```

---

#### B.2.3.5. Published Materials / Media / Independent Recognition

Template:

```text
B.2.3.5. Published Articles or Media Reports About {{PETITIONER_LAST_NAME}}’s Achievements or Current Work

The record includes published materials about {{PETITIONER_LAST_NAME}} / {{US_ENTITY_NAME}} / {{PROJECT_NAME}}, including {{MEDIA_LIST}}.

These materials are relevant because they show independent attention to {{PETITIONER_LAST_NAME}}’s work and corroborate {{CLAIM}}.

(Please refer to Exhibit B.2.3.5, p. {{PAGE_XX}}: {{MEDIA_DOCUMENTS}}.)
```

Evidence:

```text
B.2.3.5-1. Articles about petitioner
B.2.3.5-2. Articles about petitioner’s company with petitioner’s role identified
B.2.3.5-3. Interviews
B.2.3.5-4. Press releases, if supported by independent materials
B.2.3.5-5. Media outlet reputation evidence
```

---

### B.2.4. Totality of Circumstances Under Prong 2

Template:

```text
B.2.4. Totality of Circumstances Under Prong 2

When evaluated in the totality of circumstances, the evidence establishes that {{PETITIONER_FULL_NAME}} is well positioned to advance {{PROPOSED_ENDEAVOR_TITLE}}.

The evidence includes {{PRONG_2_EVIDENCE_CATEGORIES}}. Together, these records show that {{PETITIONER_LAST_NAME}} has the background, plan, progress, and external support needed to continue advancing the endeavor.

USCIS does not require proof that the endeavor is more likely than not to ultimately succeed. The relevant question is whether {{PETITIONER_LAST_NAME}} is well positioned to advance it. The record satisfies that standard because {{SYNTHESIS}}.
```

---

## B.3. Prong 3: On Balance, Waiver of Job Offer and Labor Certification Would Benefit the United States

USCIS Policy Manual insertion:

> Once officers have determined that the petitioner met the first two prongs, they proceed with the analysis of the third prong. This last prong requires the petitioner to demonstrate that the factors in favor of granting the waiver outweigh those that support the requirement of a job offer and thus a labor certification, which is intended to ensure that the admission of foreign workers will not adversely affect the job opportunities, wages, and working conditions of U.S. workers.

> For the third prong, an officer assesses whether the person’s endeavor and the person being well-positioned to advance that endeavor, taken together, provide benefits to the nation such that a waiver of the labor certification requirement outweighs the benefits that ordinarily flow from that requirement.

> In establishing eligibility for the third prong, petitioners may submit evidence relating to one or more of the following factors: whether, in light of the nature of the person’s qualifications or proposed endeavor, it would be impractical to obtain a labor certification; the benefit to the United States from the prospective alien’s contributions, even if other U.S. workers were also available; and the national interest in the person’s contributions is sufficiently urgent to warrant forgoing the labor certification process.

> Note that evidence of a national labor shortage in the person’s occupation would not, by itself, satisfy this third prong.

Template intro:

```text
B.3. Prong 3: On Balance, Waiving the Job Offer and Labor Certification Requirements Would Benefit the United States

The third Dhanasar prong is satisfied because the benefits of {{PETITIONER_LAST_NAME}}’s proposed endeavor and {{PRONOUN_POSSESSIVE}} ability to advance it outweigh the benefits ordinarily served by a job offer and labor certification requirement.
```

---

### B.3.1. Impracticality of Labor Certification

Template:

```text
B.3.1. The Nature of the Proposed Endeavor Makes Labor Certification Impractical

The labor certification process is designed around a specific employer, specific position, and geographically defined labor market. In this case, that framework is impractical because {{PROPOSED_ENDEAVOR_TITLE}} requires {{SELF_EMPLOYMENT_ENTREPRENEURIAL_FLEXIBILITY_MULTI_CLIENT_WORK_RESEARCH_FUNDING_STARTUP_OPERATIONS_GEOGRAPHIC_MOBILITY_OR_OTHER}}.

Requiring a labor certification tied to one employer and one position would {{NEGATIVE_EFFECT_ON_ENDEAVOR}}, while the waiver would allow {{PETITIONER_LAST_NAME}} to {{POSITIVE_EFFECT_OF_WAIVER}}.
```

Use this theory when:

- entrepreneur or founder;
- multi-client work;
- independent research/commercialization;
- geographically mobile deployment;
- consulting/advisory model with broader field impact;
- urgent disaster/public safety response;
- unique role cannot be captured as minimum job requirements.

---

### B.3.2. Unique Knowledge, Skills, or Entrepreneurial Role

Template:

```text
B.3.2. {{PETITIONER_LAST_NAME}}’s Knowledge, Skills, or Role Exceed What Labor Certification Is Designed to Capture

The labor certification process focuses on minimum job requirements. {{PETITIONER_LAST_NAME}}’s value to the proposed endeavor depends on {{UNIQUE_KNOWLEDGE_SKILLS_ROLE}}, including {{SPECIFIC_FACTOR_1}}, {{SPECIFIC_FACTOR_2}}, and {{SPECIFIC_FACTOR_3}}.

These qualities are not simply minimum qualifications for a conventional job. They are the reason {{PETITIONER_LAST_NAME}} can advance {{PROPOSED_ENDEAVOR_TITLE}} in a way that produces broader national benefit.
```

---

### B.3.3. Benefits Even if Other U.S. Workers Are Available

Template:

```text
B.3.3. The United States Would Benefit from {{PETITIONER_LAST_NAME}}’s Contributions Even if Other U.S. Workers Are Available

Even assuming that qualified U.S. workers are available in {{FIELD_OR_OCCUPATION}}, the United States would benefit from {{PETITIONER_LAST_NAME}}’s specific contributions because {{SPECIFIC_CONTRIBUTION_VALUE}}.

The record shows that {{PETITIONER_LAST_NAME}} offers {{CONTRIBUTION_1}}, {{CONTRIBUTION_2}}, and {{CONTRIBUTION_3}}, which are tied to the proposed endeavor’s nationally important impact.
```

---

### B.3.4. Urgency, Public Benefit, or Time-Sensitive Need

Template:

```text
B.3.4. The National Interest in the Contributions Supports Forgoing Labor Certification

The proposed endeavor addresses {{URGENT_OR_TIME_SENSITIVE_PROBLEM}}. Delays in advancing the endeavor could affect {{PUBLIC_SAFETY_HEALTH_INFRASTRUCTURE_EDUCATION_ECONOMIC_SECURITY_OR_OTHER}}.

The record supports urgency through {{OFFICIAL_REPORTS_MARKET_TIMELINES_DISASTER_EXAMPLES_PROJECT_DEADLINES_GRANT_TIMELINES_OR_OTHER}}.

This supports waiver because {{WHY_DELAY_FROM_LABOR_CERTIFICATION_WOULD_REDUCE_NATIONAL_BENEFIT}}.
```

---

### B.3.5. Economic Impact, Job Creation, Regional or Sectoral Effects

Template:

```text
B.3.5. The Endeavor Has Documented or Credible Economic and Operational Benefits

The proposed endeavor has the potential to generate economic or operational benefits through {{JOB_CREATION_REVENUE_INVESTMENT_PRODUCTIVITY_INFRASTRUCTURE_RESILIENCE_REGIONAL_DEVELOPMENT_OR_OTHER}}.

Evidence includes:

- {{ECONOMIC_EVIDENCE_1}}
- {{ECONOMIC_EVIDENCE_2}}
- {{ECONOMIC_EVIDENCE_3}}

These benefits support the balance analysis because they show that the waiver would advance {{NATIONAL_OR_REGIONAL_BENEFIT}}, rather than merely benefit {{PETITIONER_LAST_NAME}} or a single employer.
```

---

### B.3.6. Balance Conclusion

Template:

```text
B.3.6. On Balance, the Benefits of the Waiver Outweigh the Benefits of Labor Certification

When the proposed endeavor and {{PETITIONER_LAST_NAME}}’s positioning are considered together, the factors favoring waiver outweigh the benefits of requiring a job offer and labor certification.

The record establishes that:

1. The endeavor has substantial merit and national importance because {{PRONG_1_SHORT}}.
2. {{PETITIONER_LAST_NAME}} is well positioned to advance it because {{PRONG_2_SHORT}}.
3. The labor certification process would be impractical or counterproductive because {{LABOR_CERT_IMPRACTICALITY_SHORT}}.
4. The United States would benefit from {{PETITIONER_LAST_NAME}}’s specific contributions even if other workers are available because {{BENEFIT_SHORT}}.
5. The endeavor has {{URGENCY_ECONOMIC_PUBLIC_OR_FIELD_IMPACT_SHORT}}.

Accordingly, the third prong of Matter of Dhanasar is satisfied.
```

Common problems:

- repeating Prong 1 and Prong 2 without balance analysis;
- saying “labor shortage” and stopping there;
- arguing that the petitioner deserves flexibility, rather than that the United States benefits from waiver;
- no explanation why ordinary labor certification is a poor fit.

---

## 6. STEM, Government-Interest, and Entrepreneur Modules

These are optional modules. Include only when facts justify them.

### 6.1. STEM module

USCIS Policy Manual insertion:

> USCIS recognizes the importance of progress in STEM fields and the essential role of persons with advanced STEM degrees in fostering this progress, especially in focused critical and emerging technologies or other STEM areas important to U.S. competitiveness or national security.

> USCIS considers an advanced degree, particularly a Ph.D., in a STEM field tied to the proposed endeavor and related to work furthering a critical and emerging technology or other STEM area important to U.S. competitiveness or national security, an especially positive factor.

Template:

```text
STEM Evidentiary Considerations

{{PETITIONER_LAST_NAME}}’s proposed endeavor falls within {{STEM_FIELD}} and relates to {{CRITICAL_OR_EMERGING_TECH_OR_COMPETITIVENESS_AREA}}. The record supports this through {{AUTHORITATIVE_SOURCES}}.

{{PETITIONER_LAST_NAME}} holds {{STEM_DEGREE}} in {{FIELD}}, directly tied to the proposed endeavor. This education, combined with {{RESEARCH_PUBLICATIONS_PATENTS_PROJECTS_GOVERNMENT_INTEREST_OR_OTHER}}, supports the conclusion that {{PRONOUN_SUBJECT}} is well positioned to advance a STEM endeavor of national importance.
```

### 6.2. Government or quasi-government support module

USCIS Policy Manual insertion:

> While not required, letters from interested government agencies or quasi-governmental entities in the United States can be helpful evidence and, depending on the contents of the letters, can be relevant to all three prongs.

Template:

```text
Interested Government Agency or Quasi-Governmental Support

The record includes support from {{GOVERNMENT_OR_QUASI_GOV_ENTITY}}, which is relevant because {{ENTITY_EXPERTISE}}.

The letter supports Prong 1 by explaining {{NATIONAL_IMPORTANCE_SUPPORT}}.
The letter supports Prong 2 by explaining {{WELL_POSITIONED_SUPPORT}}.
The letter supports Prong 3 by explaining {{WAIVER_BALANCE_SUPPORT}}.

(Please refer to Exhibit {{EXHIBIT_CODE}}, p. {{PAGE_XX}}: {{LETTER_TITLE}}.)
```

### 6.3. Entrepreneur module

USCIS Policy Manual insertion:

> Not every entrepreneur qualifies for a national interest waiver. While USCIS decides each case on its merits, broad assertions regarding general benefits to the economy and potential to create jobs will not establish an entrepreneur’s qualification for a national interest waiver.

> Evidence of ownership and role in the U.S.-based entity may have probative value in demonstrating the petitioner is well positioned to advance the endeavor.

> Strong petitions would discuss how the person’s record of success would translate to a proposed plan or forecast for continued success, and steps they have taken toward those proposed activities, and plans that tie into the person’s background and expertise.

Entrepreneur evidence checklist:

```text
- Ownership and active central role in U.S.-based entity
- Formation documents, operating agreement, cap table
- Founder/officer role evidence
- Business plan
- Revenue, growth, customer adoption, contracts
- Investments or binding commitments to invest
- Incubator/accelerator participation
- Awards or grants
- Intellectual property
- Published materials
- Job creation evidence and projections
- Third-party letters from investors, customers, government entities, business associations
- Evidence that business metrics are realistic and corroborated
```

Entrepreneur template:

```text
Specific Evidentiary Considerations for Entrepreneur Petitioner

{{PETITIONER_FULL_NAME}} advances the proposed endeavor through {{US_ENTITY_NAME}}, a {{STATE}}-based entity engaged in {{BUSINESS_ACTIVITY}}. {{PETITIONER_LAST_NAME}} is {{FOUNDER_COFOUNDER_OWNER_MANAGER_OFFICER_ROLE}} and maintains an active and central role in {{ENTITY_NAME}}.

The record shows:

1. Ownership and role: {{OWNERSHIP_ROLE_EVIDENCE}}
2. Business progress: {{REVENUE_CUSTOMERS_CONTRACTS_PROJECTS}}
3. Market validation: {{INVESTMENT_CUSTOMER_SUPPORT_MEDIA_OR_AWARDS}}
4. Feasible growth plan: {{BUSINESS_PLAN_METRICS_FORECASTS}}
5. National-interest connection: {{HOW_BUSINESS_ADVANCES_NATIONALLY_IMPORTANT_ENDEAVOR}}

This evidence is not offered as a generic claim that entrepreneurship is good for the economy. It is offered to show that this specific endeavor, led by this specific petitioner, has substantial merit, national importance, credible progress, and waiver justification.
```

---

## 7. Conclusion Template

```text
Conclusion

When evaluated in the aggregate, the evidence establishes that {{PETITIONER_FULL_NAME}} qualifies for EB-2 classification as {{EB2_BASIS}} and satisfies all three prongs of Matter of Dhanasar.

First, the proposed endeavor has substantial merit and national importance because {{PRONG_1_SUMMARY}}.

Second, {{PETITIONER_LAST_NAME}} is well positioned to advance the endeavor because {{PRONG_2_SUMMARY}}.

Third, on balance, waiving the job offer and labor certification requirements would benefit the United States because {{PRONG_3_SUMMARY}}.

Accordingly, pursuant to INA § 203(b)(2), 8 C.F.R. § 204.5(k), the USCIS Policy Manual guidance on national interest waivers, and the analytical framework established in Matter of Dhanasar, 26 I&N Dec. 884 (AAO 2016), {{PETITIONER_FULL_NAME}} respectfully requests that USCIS approve the Form I-140 petition and grant the National Interest Waiver.

Respectfully submitted,

{{PETITIONER_FULL_NAME}}
{{DATE}}
```

---

# 8. Master List of Exhibits

Use this as the universal exhibit architecture. Delete unused items in final version. Do not shift regulatory criterion codes; stability matters for humans and LLMs, which is a depressing sentence but a true one.

```text
List of Exhibits

Exhibit 0. Overview and CV ................................................ pg. {{PAGE_XX}}
0-1. Curriculum Vitae of {{PETITIONER_FULL_NAME}} .......................... pg. {{PAGE_XX}}
0-2. Passport biographic page / identity document [if included here] ....... pg. {{PAGE_XX}}

Exhibit A. Basic Eligibility for EB-2 ...................................... pg. {{PAGE_XX}}

Exhibit A.1. Advanced Degree Professional [optional] ....................... pg. {{PAGE_XX}}
A.1-1. {{DEGREE_DOCUMENT}} ................................................. pg. {{PAGE_XX}}
A.1-2. {{TRANSCRIPT}} ...................................................... pg. {{PAGE_XX}}
A.1-3. {{CREDENTIAL_EVALUATION}} ........................................... pg. {{PAGE_XX}}
A.1-4. {{OCCUPATION_PROFESSION_EVIDENCE}} .................................. pg. {{PAGE_XX}}
A.1-5. {{BACHELOR_PLUS_5_EXPERIENCE_EVIDENCE_IF_APPLICABLE}} ............... pg. {{PAGE_XX}}

Exhibit A.2. Exceptional Ability [optional] ................................ pg. {{PAGE_XX}}

Exhibit A.2.R1. Official Academic Record ................................... pg. {{PAGE_XX}}
A.2.R1-1. {{ACADEMIC_RECORD_1}} ............................................ pg. {{PAGE_XX}}
A.2.R1-2. {{CERTIFICATE_OR_TRAINING}} ...................................... pg. {{PAGE_XX}}

Exhibit A.2.R2. At Least Ten Years of Full-Time Experience ................. pg. {{PAGE_XX}}
A.2.R2-1. {{EMPLOYMENT_RECORD}} ............................................ pg. {{PAGE_XX}}
A.2.R2-2. {{EMPLOYER_LETTER_1}} ............................................ pg. {{PAGE_XX}}
A.2.R2-3. {{EMPLOYER_LETTER_2}} ............................................ pg. {{PAGE_XX}}
A.2.R2-4. {{EMPLOYER_LETTER_3}} ............................................ pg. {{PAGE_XX}}

Exhibit A.2.R3. License or Certification ................................... pg. {{PAGE_XX}}
A.2.R3-1. {{LICENSE_OR_CERTIFICATION}} ..................................... pg. {{PAGE_XX}}
A.2.R3-2. {{ISSUING_AUTHORITY_INFORMATION}} ................................ pg. {{PAGE_XX}}

Exhibit A.2.R4. Salary or Other Remuneration ............................... pg. {{PAGE_XX}}
A.2.R4-1. {{COMPENSATION_EVIDENCE}} ........................................ pg. {{PAGE_XX}}
A.2.R4-2. {{COMPARATIVE_COMPENSATION_BENCHMARKS}} .......................... pg. {{PAGE_XX}}

Exhibit A.2.R5. Membership in Professional Associations .................... pg. {{PAGE_XX}}
A.2.R5-1. {{MEMBERSHIP_CERTIFICATE}} ....................................... pg. {{PAGE_XX}}
A.2.R5-2. {{ASSOCIATION_INFORMATION_AND_MEMBERSHIP_CRITERIA}} ............... pg. {{PAGE_XX}}
A.2.R5-3. {{PARTICIPATION_EVIDENCE}} ....................................... pg. {{PAGE_XX}}

Exhibit A.2.R6. Recognition for Achievements and Significant Contributions . pg. {{PAGE_XX}}
A.2.R6-1. {{RECOGNITION_LETTER_OR_AWARD_1}} ................................ pg. {{PAGE_XX}}
A.2.R6-2. {{RECOGNITION_LETTER_OR_AWARD_2}} ................................ pg. {{PAGE_XX}}
A.2.R6-3. {{RECOGNITION_LETTER_OR_AWARD_3}} ................................ pg. {{PAGE_XX}}
A.2.R6-4. {{INDEPENDENT_CORROBORATION}} .................................... pg. {{PAGE_XX}}

Exhibit B. Eligibility for National Interest Waiver ........................ pg. {{PAGE_XX}}

Exhibit B.0. Proposed Endeavor ............................................. pg. {{PAGE_XX}}
B.0-1. Proposed Endeavor Statement ......................................... pg. {{PAGE_XX}}
B.0-2. Business Plan / Research Plan / Implementation Plan ................. pg. {{PAGE_XX}}
B.0-3. U.S. Entity Formation Documents [if applicable] ..................... pg. {{PAGE_XX}}
B.0-4. Website / Public Materials / Product or Program Description ......... pg. {{PAGE_XX}}
B.0-5. Roadmap, Milestones, Budget, or Staffing Plan ....................... pg. {{PAGE_XX}}

Exhibit B.1. Prong 1: Substantial Merit and National Importance ............ pg. {{PAGE_XX}}
B.1-1. {{OFFICIAL_SOURCE_1}} ............................................... pg. {{PAGE_XX}}
B.1-2. {{OFFICIAL_SOURCE_2}} ............................................... pg. {{PAGE_XX}}
B.1-3. {{INDUSTRY_REPORT_1}} ............................................... pg. {{PAGE_XX}}
B.1-4. {{ACADEMIC_OR_MARKET_SOURCE}} ....................................... pg. {{PAGE_XX}}
B.1-5. {{SOURCE_CONNECTING_PROBLEM_TO_ENDEAVOR}} ........................... pg. {{PAGE_XX}}

Exhibit B.2. Prong 2: Well Positioned to Advance the Endeavor .............. pg. {{PAGE_XX}}
B.2.1-1. Education, skills, knowledge, and record of success evidence ...... pg. {{PAGE_XX}}
B.2.2-1. Detailed plan / proposal .......................................... pg. {{PAGE_XX}}
B.2.3.1-1. Completed project / work used by others evidence #1 ............. pg. {{PAGE_XX}}
B.2.3.1-2. Completed project / work used by others evidence #2 ............. pg. {{PAGE_XX}}
B.2.3.2-1. Prospective customer / user / partner / investor correspondence . pg. {{PAGE_XX}}
B.2.3.3-1. Financial support evidence ...................................... pg. {{PAGE_XX}}
B.2.3.4-1. Contracts / agreements / licenses ............................... pg. {{PAGE_XX}}
B.2.3.5-1. Published materials / media ..................................... pg. {{PAGE_XX}}

Exhibit B.3. Prong 3: Waiver of Job Offer and Labor Certification .......... pg. {{PAGE_XX}}
B.3-1. Evidence supporting impracticality of labor certification ............ pg. {{PAGE_XX}}
B.3-2. Evidence supporting benefits even if U.S. workers are available ...... pg. {{PAGE_XX}}
B.3-3. Evidence supporting urgency / public benefit / economic impact ....... pg. {{PAGE_XX}}
B.3-4. Job creation / economic impact / regional impact evidence ............ pg. {{PAGE_XX}}
```

---

# 9. Technical Divider Pages

Purpose: after the exhibit list, these pages act as visible separators before the underlying documents. They are also useful when merging PDFs. Civilization has chosen page dividers as the price of organized evidence.

Use a consistent format.

## 9.1. Main Exhibit Divider

```text
[PAGE BREAK]

{{PETITION_TITLE}}

EXHIBIT {{EXHIBIT_CODE}}
{{EXHIBIT_TITLE}}

Purpose of this exhibit:
{{ONE_OR_TWO_SENTENCES_EXPLAINING_WHAT_THIS_EXHIBIT_PROVES}}

Documents included:
{{DOCUMENT_LIST}}

Please see next page.
```

Example:

```text
[PAGE BREAK]

Petition for Classification Under the EB-2 Category with a Request for a National Interest Waiver on Behalf of {{PETITIONER_FULL_NAME}}

EXHIBIT B.0
PROPOSED ENDEAVOR

Purpose of this exhibit:
This exhibit documents the proposed endeavor, including the petitioner’s specific plan, implementation vehicle, operational model, and supporting materials showing that the endeavor is concrete and more specific than the general occupation.

Documents included:
B.0-1. Proposed Endeavor Statement
B.0-2. Business Plan
B.0-3. U.S. Entity Formation Documents
B.0-4. Website and Public Materials

Please see next page.
```

## 9.2. Sub-Exhibit Divider

```text
[PAGE BREAK]

EXHIBIT {{EXHIBIT_CODE}}
{{EXHIBIT_TITLE}}

This document is submitted in support of:
- {{LEGAL_SECTION_1}}
- {{LEGAL_SECTION_2_IF_APPLICABLE}}

Relevance:
{{RELEVANCE_EXPLANATION}}

Please see next page.
```

## 9.3. Document-Level Divider

```text
[PAGE BREAK]

EXHIBIT {{EXHIBIT_CODE}}
{{DOCUMENT_TITLE}}

Document type: {{DOCUMENT_TYPE}}
Date: {{DOCUMENT_DATE}}
Issuer / source: {{ISSUER_OR_SOURCE}}
Language: {{LANGUAGE}}
Translation: {{YES_NO_NA}}

This document supports the following factual proposition:
{{FACTUAL_PROPOSITION}}

Please see next page.
```

## 9.4. Original + Translation Divider

```text
[PAGE BREAK]

EXHIBIT {{EXHIBIT_CODE}}
{{DOCUMENT_TITLE}}

The original-language document appears first, followed by its certified English translation.

Original language: {{LANGUAGE}}
Translation certification: included / not required / attached separately

Please see next page.
```

## 9.5. Source Excerpt Divider

Use for government reports, BLS pages, screenshots, articles, web pages.

```text
[PAGE BREAK]

EXHIBIT {{EXHIBIT_CODE}}
{{SOURCE_TITLE}}

Source: {{URL_OR_PUBLICATION_DETAILS}}
Date accessed / publication date: {{DATE}}
Relevant issue: {{WHY_INCLUDED}}

This source is cited for the following proposition:
{{CLAIM_SUPPORTED_BY_SOURCE}}

Please see next page.
```

---

# 10. LLM Evidence Mapping Protocol

Перед drafting агент должен создать evidence map. Без этого он будет писать уверенно и пусто, как LinkedIn-пост.

## 10.1. Required input table

```text
| Evidence ID | Document title | Date | Source / issuer | Language | Translation? | Facts proved | Legal section | Strength | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {{ID}} | {{TITLE}} | {{DATE}} | {{SOURCE}} | {{LANG}} | {{YES/NO}} | {{FACTS}} | {{A.1 / A.2.R2 / B.1 / etc.}} | {{High/Medium/Low}} | {{GAPS}} |
```

## 10.2. Claim-evidence rule

Every important sentence in the memorandum should fit one of these patterns:

```text
Legal rule -> Fact -> Evidence -> Conclusion
```

Example:

```text
USCIS evaluates whether the proposed endeavor has substantial merit and national importance by examining the specific endeavor and its prospective impact. Here, {{PROPOSED_ENDEAVOR_TITLE}} addresses {{PROBLEM}} through {{MECHANISM}}. Official sources show {{SOURCE_FACT}}, and the petitioner’s records show {{PETITIONER_FACT}}. Therefore, the endeavor has substantial merit and national importance.
```

## 10.3. External sources rule

For Prong 1 and sometimes Prong 3, use recent and authoritative sources:

```text
Preferred:
- USCIS Policy Manual
- Federal statutes/regulations
- Federal agencies: DHS, DOL, BLS, NTIA, FCC, CISA, NIH, NSF, DOE, USDA, GAO, etc.
- State government sources, if regional theory
- Peer-reviewed research, if scientific/technical theory
- Industry associations, if credible and directly relevant
- Market reports, if methodology and date are clear

Use carefully:
- News articles
- Private salary sites
- Company blogs
- Press releases

Avoid as primary support:
- Generic blogs
- Unsourced claims
- Old sources where the market or policy changed
```

## 10.4. Letters rule

A strong support letter should include:

```text
- Recommender identity, title, organization, and field relevance
- How recommender knows petitioner
- Specific achievements observed
- Why achievements matter in the field
- Concrete examples, dates, projects, metrics
- How petitioner is well positioned to advance the endeavor
- If possible, why waiver benefits the United States
- Corroborating records: contracts, invoices, project reports, publications, metrics
```

Weak letter symptoms:

```text
- “He is excellent” with no facts
- No dates, no projects, no metrics
- Recommender does not know field
- Letter praises company but does not identify petitioner’s role
- Letter sounds written by the petition drafter and copied ten times. USCIS officers own eyes, regrettably.
```

---

# 11. Section-by-Section Drafting Prompts for LLM Agent

## 11.1. Evidence parsing prompt

```text
You are preparing an EB-2 NIW petition. Parse the provided evidence into a structured evidence map. For each document, identify: title, date, issuer, language, whether translation is needed, factual propositions proved, possible legal sections, strength, weaknesses, and missing corroboration. Do not draft argument yet. Do not invent facts.
```

## 11.2. Proposed endeavor prompt

```text
Using the evidence map, define the petitioner’s intended occupation and proposed endeavor. The proposed endeavor must be more specific than the occupation. Write: (1) one-sentence endeavor, (2) one-paragraph plain-English description, (3) problem addressed, (4) implementation mechanism, (5) direct impacts, (6) evidence supporting concreteness. Flag if the endeavor is too broad or if it depends only on a general occupation shortage.
```

## 11.3. EB-2 threshold prompt

```text
Determine whether the petitioner qualifies for EB-2 as advanced degree professional, person of exceptional ability, or both. For advanced degree, analyze degree equivalency, profession requirement, and relation to endeavor. For exceptional ability, identify which of the six regulatory criteria are supported, then draft a final merits synthesis. Do not count weak criteria unless evidence objectively fits the regulatory language.
```

## 11.4. Prong 1 prompt

```text
Draft Prong 1 under Matter of Dhanasar. Separate substantial merit from national importance. Use official and independent sources. Explain the specific endeavor’s prospective impact, not the general importance of the occupation. Include a subsection showing broader implications beyond one employer, client, or local business benefit if relevant.
```

## 11.5. Prong 2 prompt

```text
Draft Prong 2 under Matter of Dhanasar. Focus on the petitioner. Use evidence of education, skills, knowledge, record of success, detailed plan, progress, customers/users/investors/partners, contracts, financial support, media, and letters. Explain how past achievements connect to the proposed endeavor. Do not require proof of guaranteed success, but do require substantiated positioning.
```

## 11.6. Prong 3 prompt

```text
Draft Prong 3 under Matter of Dhanasar. Analyze why, on balance, waiver of job offer and labor certification benefits the United States. Address impracticality of labor certification, value of petitioner’s specific contributions even if U.S. workers are available, urgency or public benefit if applicable, and economic/job creation/regional/sectoral effects if supported. Do not rely only on national labor shortage.
```

## 11.7. Exhibit divider generation prompt

```text
Using the final exhibit list, generate technical divider pages for every main exhibit, sub-exhibit, and document-level exhibit. Each divider must include exhibit code, title, purpose, documents included, and “Please see next page.” For non-English documents, add a note that original appears first followed by certified English translation.
```

---

# 12. Quality Control Checklist Before Filing

## 12.1. Legal theory checklist

```text
[ ] Intended occupation is defined.
[ ] Proposed endeavor is defined and more specific than occupation.
[ ] EB-2 threshold basis is clear: Advanced Degree / Exceptional Ability / Both.
[ ] If Advanced Degree: degree equivalency and occupation-as-profession are both addressed.
[ ] If bachelor + 5: experience is post-baccalaureate, progressive, and in specialty.
[ ] If Exceptional Ability: at least three criteria are objectively met.
[ ] If Exceptional Ability: final merits determination is included.
[ ] Prong 1 separates substantial merit and national importance.
[ ] Prong 1 does not rely only on general occupational importance or shortage.
[ ] Prong 1 shows broader implications beyond one employer/client.
[ ] Prong 2 focuses on petitioner and is supported by independent evidence.
[ ] Prong 2 includes detailed plan and progress if available.
[ ] Prong 3 includes actual balance analysis.
[ ] Prong 3 does not rely only on labor shortage.
[ ] Entrepreneur/STEM/government modules included only if factually supported.
```

## 12.2. Evidence checklist

```text
[ ] Every major claim has an exhibit citation.
[ ] All non-English documents have translations.
[ ] Employer letters include dates, full-time status, duties, title, signer information.
[ ] Compensation evidence separates petitioner’s income from household/entity gross revenue unless legally explained.
[ ] Salary benchmarks are comparable by occupation, geography, date, and level.
[ ] Support letters identify specific achievements and field contribution.
[ ] Business plan is supported by independent evidence.
[ ] Project claims are supported by contracts, invoices, work orders, screenshots, photos, reports, or customer letters.
[ ] External sources are current enough for the claim.
[ ] Exhibit list matches actual compiled documents.
[ ] Page references are updated after final PDF assembly.
```

## 12.3. Formatting checklist

```text
[ ] Cover letter included.
[ ] Table of contents updated.
[ ] List of exhibits updated.
[ ] Technical divider pages inserted.
[ ] Exhibit codes are consistent across memorandum, exhibit list, and divider pages.
[ ] Page numbers match final compiled PDF.
[ ] No unresolved placeholders remain.
[ ] No client facts from another case remain. Yes, check this. Humans keep doing it.
[ ] USCIS address, fees, and form editions verified immediately before filing.
```

---

# 13. Recommended Final Folder Structure

Use this for source files before PDF assembly.

```text
EB2_NIW_{{PETITIONER_LAST_NAME}}/

00_ADMIN/
  00_filing_checklist.md
  01_forms/
  02_fees_receipts/
  03_passport_status_docs/

01_MEMORANDUM/
  01_cover_letter.docx
  02_petition_memorandum.docx
  03_table_of_contents.docx
  04_list_of_exhibits.docx

02_EXHIBITS/
  Exhibit_0_CV/
  Exhibit_A_Basic_Eligibility/
    A1_Advanced_Degree/
    A2_Exceptional_Ability/
      A2_R1_Academic_Record/
      A2_R2_Ten_Years_Experience/
      A2_R3_License_Certification/
      A2_R4_Remuneration/
      A2_R5_Membership/
      A2_R6_Recognition/
  Exhibit_B_NIW/
    B0_Proposed_Endeavor/
    B1_Prонg_1_Substantial_Merit_National_Importance/
    B2_Prонg_2_Well_Positioned/
      B2_1_Education_Skills_Record/
      B2_2_Detailed_Plan/
      B2_3_Progress_Support/
    B3_Prонg_3_Balance/

03_DIVIDERS/
  dividers_generated.docx

04_FINAL_PACKET/
  EB2_NIW_{{PETITIONER_LAST_NAME}}_final_packet.pdf
  EB2_NIW_{{PETITIONER_LAST_NAME}}_page_reference_check.xlsx
```

---

# 14. Minimal Case-Specific Intake Form

Before drafting, collect this. Otherwise the petition becomes a creative writing exercise, which is charming until USCIS notices.

```text
1. Petitioner identity
Full name:
DOB:
Country of birth:
Country of citizenship:
Current address:
Current U.S. status, if any:
Passport:

2. Proposed endeavor
Intended occupation:
Proposed endeavor title:
One-sentence endeavor:
Implementation vehicle:
U.S. entity, if any:
Geographic scope:
Target beneficiaries/users/customers/public:
Problem addressed:
Why the problem matters nationally:
Direct impacts:
Timeline:
Milestones:
Resources:

3. EB-2 basis
Advanced degree?
Degree:
Institution:
Year:
Field:
Credential evaluation?
Occupation requires bachelor’s degree?
Evidence:

Exceptional ability?
Criteria supported:
R1 academic record:
R2 ten years experience:
R3 license/certification:
R4 remuneration:
R5 memberships:
R6 recognition:
Final merits strongest facts:

4. Prong 1 evidence
Official sources:
Industry sources:
Market data:
Government priorities:
Public welfare / economic / infrastructure / science / cultural theory:
Specific connection to endeavor:

5. Prong 2 evidence
Education:
Skills:
Record of success:
Plan:
Progress:
Customers/users:
Partners:
Investors:
Contracts:
Revenue:
Media:
Letters:

6. Prong 3 evidence
Why labor certification is impractical:
Why U.S. benefits even if workers are available:
Urgency:
Economic impact:
Job creation:
Public benefit:
Entrepreneurial/self-employed factors:

7. Exhibits
For each document:
Title:
Date:
Issuer:
Language:
Translation:
Facts proved:
Legal section:
```

---

# 15. Short “Source Case Logic” Extracted from the Provided EB-2 NIW Case

The source case uses this architecture:

1. Cover letter with statutory basis and Dhanasar preview.
2. Overview describing petitioner, endeavor, operating company, market problem, metrics, EB-2 basis, and three-prong summary.
3. EB-2 threshold section:
   - A.1 Advanced Degree Professional.
   - A.2 Exceptional Ability, using academic record, ten years experience, remuneration, membership, recognition.
4. NIW section:
   - B.0 Proposed Endeavor, with business plan, company documents, website materials.
   - B.1 Prong 1, using government and industry sources to show substantial merit and national importance.
   - B.2 Prong 2, using petitioner’s education, record, detailed plan, U.S. business progress, projects, customers, contracts, financial support, media.
   - B.3 Prong 3, arguing that the endeavor requires entrepreneurial, multi-client, multi-state flexibility and that the U.S. benefits outweigh labor certification.
5. List of Exhibits.
6. Technical divider pages after exhibit list, matching exhibit structure.

The master template above keeps that logic but normalizes it for reuse, adds missing optional regulatory criterion R3, stabilizes exceptional ability numbering, and adds explicit final merits analysis.

---

# 16. Final Note on Policy Manual Insertions

The quoted Policy Manual blocks in this template are working insertions. In a final memorandum, use them selectively. The petition should not become a pasted Policy Manual anthology wearing a tie. Use the legal standard, then apply facts immediately.

Recommended pattern for final drafting:

```text
Rule: one short Policy Manual / Dhanasar principle.
Application: specific petitioner facts.
Evidence: exhibit citation.
Conclusion: why the standard is met.
```

That pattern is boring. Boring wins immigration filings.
