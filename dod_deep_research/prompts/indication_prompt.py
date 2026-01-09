"""Prompt template for drug indication research reports."""


def generate_indication_prompt(
    disease: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
) -> str:
    """
    Generate a comprehensive research report prompt for drug indication analysis.

    Args:
        disease: The specific disease indication (e.g., "Alzheimer's", "ALS", "SLE")
        drug_name: The drug name (e.g., "IL-2", "Aspirin")
        drug_form: The specific form of the drug (e.g., "low-dose IL-2"). If None, uses drug_name.
        drug_generic_name: The generic name of the drug (e.g., "Aldesleukin"). If None, uses drug_name.

    Returns:
        A formatted prompt string for generating the research report.
    """
    drug_form = drug_form or drug_name
    drug_generic_name = drug_generic_name or drug_name

    prompt = f"""
My specific disease indication for this report is: {disease}. 

Please generate a comprehensive report on {drug_form} for {disease} ONLY. 

Adhere strictly to the following "Comprehensive Instructions and Template Guidance for IL-2 Indication Reports" that I am pasting below. 

Ensure all information and analysis provided is specific to {disease} and {drug_name}'s role within that context.

## Comprehensive Instructions and Template Guidance for IL-2 Indication Reports

### 1. Project Objective & Audience
**Audience:** This project is for a US biotechnology company.
**Objective:** To explore whether there are additional indications for {drug_name}, either as immunotherapy support in oncology or in dampening inflammation in other diseases. Each report generated will be a deep dive into a single, specified disease indication.

### 2. Overarching Directives for Report Generation

**Primary Directive: Single Indication Focus Per Report:** 
- Each report request will specify a single disease indication (e.g., ALS, SLE, a specific cancer type), denoted as [disease] throughout this document.
- All sections of the generated report must pertain exclusively to this specified [disease].
- Information on other diseases or broader {drug_name} applications should only be included if it provides essential mechanistic context directly relevant and briefly explained for the specified [disease].

**Tone and Evidence:** 
- Maintain a neutral, evidence-based tone.
- Avoid dramatic adjectives (e.g., "devastating", "ground-breaking") unless directly quoting a source.
- Quantify all efficacy, safety, or epidemiology statements, and provide citations.

**Content Focus:** 
- Include mechanistic explanations only when they illuminate {drug_name}'s relevance to the specified [disease]; keep them focused and cite primary data.
- Highlight biomarker-driven stratification where supported for the specified [disease] (e.g., neurofilament subgroups); specify thresholds and clinical utility.
- Discuss diagnostic delays / misdiagnosis for the specified [disease] only if they materially affect {drug_name} therapy positioning or trial design for that indication; provide numeric ranges.

**Achieving a 'Crisp' and Focused Report:** 
- Prioritize Key Data: While comprehensive, ensure information directly addresses template sections for the specified [disease]. Avoid tangential information.
- Conciseness: Use bullet points for lists (e.g., trial outcomes, unmet needs).
- User-Defined Depth (Optional per request): The user may specify if particular sections require more exhaustive detail or a summary for a given report.
- Strict Adherence to Scope: If information for a template section is not available or not relevant for the single specified [disease], clearly state that.

**Style and Referencing:** 
- For each clinical trial, include: phase, design, enrollment, endpoints, key results (efficacy, toxicity), statistical significance, and primary identifier (NCTID or registry link).
- Follow the Regulatory-Status Rules (Section 4) when classifying therapies.
- Use numbers in square brackets for citations (e.g., [1], [2]); every citation must map to an entry in the "References" section.
- Keep sentences readable (aim for <30 words). Split complex ideas.

### 3. Report Structure & Section-Specific Guidance (Based on "IL-2 Project Template v2.docx")

#### A. Rationale/Executive Summary
**Focus:** Summarize the core findings and recommendation for the specified [disease] only.
**Asset:** Name (e.g., {drug_form} / {drug_generic_name}) and its basic therapeutic mechanisms relevant to dampening inflammation or supporting immunotherapy for [disease].
**Objective:** Assess whether {drug_name} should be further developed for the treatment of the specified [disease].
**Unmet Need:** Summarize treatment gaps specifically in the [disease] setting and how {drug_name} (or its relevant form) offers differentiation.
**Supportive Evidence (Pre-clinical/Clinical):** Briefly summarize pre-clinical evidence supporting {drug_name}'s therapeutic target in [disease] and describe any clinical trial evidence supporting {drug_name} use for this specific [disease].
**Relevant Regulatory History:** Note drug approval milestones or FDA/EMA designations (e.g., Orphan Drug, Fast Track) specifically for {drug_name} in the context of [disease].

#### B. Disease Overview: [disease]
**Focus:** All content must be specific to the [disease] indicated for the report.
- **High-level description:** 1-2 paragraphs on [disease] characteristics: presenting symptoms, sequelae, biologic changes, mortality/morbidity.
- **Epidemiology:** Incidence and prevalence of [disease] in the US market, including any significant demographic variations.
- **Diagnosis:** How [disease] is diagnosed, including screening procedures/testing, and any relevant diagnostic delays or undiagnosed populations for [disease].
- **Pathophysiology:** How [disease] affects the body and the specific therapeutic target for {drug_name} within the context of [disease] pathology. Specify whether {drug_name} aims to treat the underlying [disease] or only alleviate its symptoms.
- **Biomarkers:** Commonly used, clinically validated diagnostic and/or prognostic biomarkers currently recommended in treatment guidelines for [disease].
- **Potential Exclusion Criteria for {drug_name} Therapy in [disease]:** Populations with [disease] where {drug_name} may be contraindicated or likely ineffective.

**Sources for this section:** Peer-reviewed literature (PubMed/Google Scholar). Search on [disease] name + biomarkers, current reviews, or consensus treatment articles. Also search for therapeutic targets in [disease] and preclinical data relevant to {drug_name} for [disease]. Identify pivotal papers (e.g., most cited).

#### C. Therapeutic Landscape for [disease]
**Focus:** Overview of treatments specifically for [disease].

**Approved Treatments** 
- **Approved Therapies (for [disease])** 
  - Table format: Owner, Trade/Generic Name, Year FDA Approved, Mechanism of Action, Efficacy (e.g. increase survival, slow disease progression, reduce symptoms for [disease])
- **Competing Therapies (Immunomodulators) In Development (for [disease])** 
  - Table format: Owner, Name, Mechanism of Action, Status (Preclinical, phase of trial planned, in clinical trials), Trial ID (Link to NCTID if in clinical trials)
- **Other Key Therapies in Development (for [disease])** 
  - Table format: Owner, Name, Mechanism of Action, Status (Preclinical, phase of trial planned, in clinical trials), Trial ID (Link to NCTID if in clinical trials)

**Sources for this section:** FDA label database, FDA Orphan Drug database, Competitor websites (publications, press releases). For approved drugs for [disease], use IP owner website for prescribing information. Use current treatment guidelines for [disease].

#### D. Current Treatment Guidelines for [disease]
- Summarize current treatment guidelines for the specified [disease].
- Describe how {drug_name} (relevant form) could potentially be added to or integrated into these guidelines for [disease].

#### E. Competitor Analysis for [disease]
**Focus:** Direct competitors to an {drug_name} therapy for the specified [disease].
- Summarize information on direct competitors in development for [disease] and their potential market impact in this disease area.
- Include any relevant market trends for [disease] treatment.

#### F. Clinical Trials Analysis for {drug_name} in [disease]
**Focus:** Clinical trials of {drug_name} (relevant form, e.g., {drug_form}) specifically for [disease].
**Source:** PubMed, ClinicalTrials.gov

- **Completed {drug_name} Trials in [disease]** 
  - Table format: NCTID link, Sponsor, Enrollment, Design (Phase, # & dosage of treatment arms, +/- placebo), Endpoints (Progression measures, list all biomarkers used for [disease]), Results (Efficacy, toxicity), Publication (Link to article/poster/presentation)
- **Recruiting/Active, Not Recruiting {drug_name} Trials in [disease]** 
  - Table format: NCTID Link, Sponsor, Enrollment Goal, Design (Phase, key parameters), Endpoints
- **Terminated/Unknown Status {drug_name} Trials in [disease]** 
  - Table format: NCTID Link, Sponsor, Enrollment Goal, Design, Endpoints

**Guidance:** For each completed trial, search for a related publication. Also search for publications from trials without an NCTID (e.g., single-site retrospective analyses from last 5 years, cited by other papers) if they are pivotal for {drug_name} in [disease].

#### G. Market & Opportunity Analysis for {drug_name} in [disease]
**Focus:** Market and opportunity specifically for an {drug_name} therapy in [disease].
- **Market Overview for [disease]:** Assess the potential market size for [disease] treatments.
- **Patents:** Discuss patents relevant to {drug_name} therapies (specific formulations, use in [disease]) and key competing therapies in the [disease] space.
- **Relevant Designations for {drug_name} in [disease]:** Are any {drug_name} derivatives/formulations for [disease] on an FDA fast-track, orphan drug, or other special designation?
- **Competitor Landscape for [disease]:** Who owns key competitor assets for [disease], and what is their potential market penetration?
- **Unmet Need & Asset Differentiation for {drug_name} in [disease]:** Define the specific opportunity for {drug_name} in [disease]. Are there treatment gaps in [disease] that {drug_name} can fill? Could it be better than current approved treatments for [disease] in efficacy/toxicity, cost, or accessibility (e.g., route of administration)?
- **Market Size (Incidence for [disease]):** Identify the number of new cases of [disease] diagnosed annually in the US.

**Sources for this section:** Search internet for drugs in development for [disease] (early testing/not yet in trials), scientific posters, abstracts, conference presentations (last 3 years) relevant to [disease].

#### H. References
- Include links to the sources used (e.g., PubMed, ClinicalTrials.gov, competitor press releases) for all the above sections.
- Provide citations for every research article reviewed.
- The aim is an exhaustive list of research articles relevant to {drug_name} and the specified [disease] to demonstrate thoroughness, even if not all are directly referenced in the report body.
- Ensure all pivotal trials for {drug_name} in [disease] are included.

### 4. Regulatory-Status Rules for Therapeutic Landscape (General Application)
- **Currently Marketed FDA-Approved Products** – list in "Approved Treatments – Actively Marketed"; Status = "Approved – Marketed."
- **Approved but Not Commercially Available** – list in "Withdrawn / Discontinued"; include withdrawal month/year & reason.
- **NDA Revoked / FDA-Requested Withdrawal** – also list under "Withdrawn / Discontinued"; Status = "NDA revoked – <month year> – FDA action."
- **Non-US Approvals** – list in "Outside-US Approved Therapies"; include region & approval date; flag "Not FDA-approved."
- **Pipeline Assets** – therapies without FDA approval remain in "Therapies in Development."
- ⚠️ **Update tables promptly if a therapy's marketing status changes (e.g., voluntary withdrawal).**
"""
    return prompt
