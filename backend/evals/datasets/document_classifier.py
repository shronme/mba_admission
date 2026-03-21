"""
Labeled examples for DocumentClassifier.

Each Example has:
  - document_text: str
  - document_type: str  (cv | life_story | recommendation_letter | grade_sheet | irrelevant | unclassified)

Labels were generated using StaticDocumentClassifier as an oracle and then
manually reviewed for edge-case correctness.
"""
from __future__ import annotations

import dspy

_INPUT_FIELDS = ("document_text",)

EXAMPLES: list[dspy.Example] = [
    # ---------------------------------------------------------------------- cv
    dspy.Example(
        document_text=(
            "CURRICULUM VITAE\n\nJane Smith\njane.smith@email.com\n\nPROFESSIONAL EXPERIENCE\n"
            "Senior Product Manager, Acme Corp (2021–present)\n"
            "- Led cross-functional team of 12 to deliver $4M ARR product line\n\n"
            "Software Engineer, StartupXYZ (2018–2021)\n\n"
            "EDUCATION\nUniversity of Toronto — BSc Computer Science, GPA 3.8\n\n"
            "SKILLS\nPython, SQL, Figma, Agile, Stakeholder Management"
        ),
        document_type="cv",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Resume — Alex Johnson\n\n"
            "Work Experience:\n"
            "Investment Banking Analyst, Goldman Sachs 2019–2022\n"
            "Modeled LBO transactions across healthcare and TMT sectors.\n\n"
            "Associate, Private Equity Fund 2022–present\n\n"
            "Education: Bachelor of Commerce, McGill University\n"
            "Skills: Financial modelling, Excel, Bloomberg, client management"
        ),
        document_type="cv",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Professional Experience\n"
            "Director of Operations — MedTech Inc. (2020–present)\n"
            "Managed supply chain for 14 manufacturing sites across APAC.\n\n"
            "Employment History\n"
            "Operations Manager — RegionalHealth (2016–2020)\n\n"
            "Education\nMaster of Engineering, NUS Singapore\nBachelor of Science, NUS Singapore\n\n"
            "Key Skills: Lean Six Sigma, P&L management, cross-cultural leadership"
        ),
        document_type="cv",
    ).with_inputs(*_INPUT_FIELDS),
    # ---------------------------------------------------------------- life_story
    dspy.Example(
        document_text=(
            "Personal Statement\n\n"
            "Growing up in a small town in rural Nigeria, I was the first in my family to attend "
            "university. My journey to where I am today has been shaped by a relentless curiosity "
            "and a deep sense of responsibility to my community. My passion for social enterprise "
            "was ignited when I saw how access to clean water transformed a village near my hometown."
        ),
        document_type="life_story",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Statement of Purpose\n\n"
            "My journey into medicine began with a simple question: why do some communities have "
            "so much less access to healthcare than others? This question has motivated me "
            "throughout my undergraduate studies and my three years of volunteering at a free clinic. "
            "Who I am today is inseparable from that early experience."
        ),
        document_type="life_story",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Life Story Essay\n\n"
            "I was born in Seoul and moved to Toronto when I was eight. Straddling two cultures "
            "shaped my identity in ways I'm still unpacking. My childhood was defined by translation "
            "— not just of language, but of values and expectations. This duality has become my "
            "greatest professional asset: I can read a room across cultures."
        ),
        document_type="life_story",
    ).with_inputs(*_INPUT_FIELDS),
    # --------------------------------------------------- recommendation_letter
    dspy.Example(
        document_text=(
            "Dear Admissions Committee,\n\n"
            "I have had the pleasure of working alongside Marcus Chen for the past four years at "
            "Deloitte Consulting. I am pleased to recommend him unreservedly for your MBA programme. "
            "Marcus consistently demonstrates exceptional analytical rigour and collaborative "
            "leadership.\n\nSincerely,\nDr. Patricia Okafor\nSenior Partner, Deloitte"
        ),
        document_type="recommendation_letter",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Letter of Recommendation for Sara Williams\n\n"
            "To Whom It May Concern,\n\n"
            "I have known Sara for three years in my capacity as her direct manager at HealthCo. "
            "This letter of recommendation is written with great enthusiasm. Sara's ability to "
            "synthesise complex data into strategic recommendations is genuinely rare.\n\n"
            "Yours faithfully,\nJames Oduya\nVP Strategy"
        ),
        document_type="recommendation_letter",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Dear admissions team,\n\n"
            "I have had the pleasure of supervising Priya Nair during her postdoctoral research "
            "at MIT. As her referee, I can attest to her intellectual depth, collaborative spirit, "
            "and her potential to make a lasting contribution to her field.\n\n"
            "Best regards,\nProf. Daniel Stein\nDepartment of Biology, MIT"
        ),
        document_type="recommendation_letter",
    ).with_inputs(*_INPUT_FIELDS),
    # ---------------------------------------------------------------- grade_sheet
    dspy.Example(
        document_text=(
            "Official Academic Transcript — University of British Columbia\n\n"
            "Student: Kevin Lam\nProgram: Bachelor of Commerce\n\n"
            "YEAR 1\nAccounting 101 — A  (3 credits)\nEconomics 200 — B+ (3 credits)\n\n"
            "Cumulative GPA: 3.72\n\nSemester: Fall 2018"
        ),
        document_type="grade_sheet",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Grade Point Average Report\n\n"
            "Course: Advanced Calculus — Grade: A\n"
            "Course: Linear Algebra — Grade: A-\n"
            "Course: Statistics — Grade: B+\n\n"
            "Total Credits: 45\n"
            "Cumulative GPA: 3.81\n"
            "Pass/Fail courses: none"
        ),
        document_type="grade_sheet",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Academic Record — Semester 3\n\n"
            "COURSE          GRADE   CREDITS\n"
            "Microeconomics   A       4\n"
            "Financial Acct   B+      4\n"
            "Statistics I     A-      3\n\n"
            "Grade Point Average this semester: 3.67\n"
            "Status: Pass"
        ),
        document_type="grade_sheet",
    ).with_inputs(*_INPUT_FIELDS),
    # ---------------------------------------------------------------- irrelevant
    dspy.Example(
        document_text=(
            "Meeting Agenda — Q3 Marketing Review\n\n"
            "1. Campaign performance recap\n"
            "2. Budget reallocation proposals\n"
            "3. Q4 roadmap discussion\n"
            "4. AOB\n\nDate: 15 September 2024\nLocation: Boardroom B"
        ),
        document_type="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text=(
            "Invoice #10245\nBill To: Acme Corp\nFrom: Office Supplies Ltd\n\n"
            "Qty  Description          Unit Price  Total\n"
            "10   Stapler Deluxe        $12.00      $120.00\n"
            "50   A4 Paper (ream)        $5.00      $250.00\n\n"
            "Total Due: $370.00\nDue Date: 30 days"
        ),
        document_type="irrelevant",
    ).with_inputs(*_INPUT_FIELDS),
    # ---------------------------------------------------------------- unclassified
    dspy.Example(
        document_text="Lorem ipsum dolor sit amet consectetur adipiscing elit.",
        document_type="unclassified",
    ).with_inputs(*_INPUT_FIELDS),
    dspy.Example(
        document_text="Page 1 of 3\n\n[Content not extracted successfully]",
        document_type="unclassified",
    ).with_inputs(*_INPUT_FIELDS),
]


def load() -> list[dspy.Example]:
    return list(EXAMPLES)
