"""Mock knowledge base for CivicAssist.

Everything here is fictional. "The State of Columbia Department of Community
Services" (DCS) is a made-up agency so the workshop can use realistic public
sector questions without touching real systems or real people's data.
"""

PROGRAMS = {
    "FAP": {
        "id": "FAP",
        "name": "Food Assistance Program",
        "description": "Monthly benefits loaded onto an EBT card to buy groceries.",
        "eligibility": "Gross monthly household income at or below the FAP income limit for the household size. Must be a Columbia resident.",
        "how_to_apply": "Apply online at the DCS portal or at any DCS office. Decisions are issued within 30 days.",
        "documents": ["Photo ID", "Proof of address", "Proof of income for the last 30 days"],
        "source_url": "https://dcs.columbia.example.gov/programs/fap",
        "last_updated": "2026-09-15",
    },
    "HEAP": {
        "id": "HEAP",
        "name": "Home Energy Assistance Program",
        "description": "One-time payment toward heating or cooling bills, paid directly to the utility.",
        "eligibility": "Gross monthly household income at or below the HEAP income limit. Applicant must be responsible for an energy bill.",
        "how_to_apply": "Applications open October 1 and close March 31. Apply online or by mail.",
        "documents": ["Photo ID", "Most recent utility bill", "Proof of income"],
        "source_url": "https://dcs.columbia.example.gov/programs/heap",
        "last_updated": "2026-10-01",
    },
    "CCS": {
        "id": "CCS",
        "name": "Child Care Subsidy",
        "description": "Helps working families pay for licensed child care for children under 13.",
        "eligibility": "Parent or guardian must work or attend school at least 20 hours per week and meet the CCS income limit.",
        "how_to_apply": "Apply online. You must choose a licensed provider before benefits begin.",
        "documents": ["Photo ID", "Child's birth certificate", "Work or school schedule", "Proof of income"],
        "source_url": "https://dcs.columbia.example.gov/programs/ccs",
        "last_updated": "2026-08-20",
    },
    "VHG": {
        "id": "VHG",
        "name": "Veterans Housing Grant",
        "description": "Up to $5,000 toward a security deposit or first month's rent for veterans.",
        "eligibility": "Veteran with an honorable discharge (DD-214 required). Household income at or below the VHG income limit.",
        "how_to_apply": "Apply in person at a DCS office with a Veterans Services Officer.",
        "documents": ["DD-214", "Photo ID", "Signed lease or rental offer"],
        "source_url": "https://dcs.columbia.example.gov/programs/vhg",
        "last_updated": "2026-07-01",
    },
    "SBRG": {
        "id": "SBRG",
        "name": "Small Business Recovery Grant",
        "description": "Grants of $2,500 to $25,000 for Columbia small businesses with fewer than 50 employees.",
        "eligibility": "Business registered in Columbia for at least 1 year with fewer than 50 employees. Grant amount is based on annual revenue.",
        "how_to_apply": "Apply online during the open funding round. The current round closes December 15, 2026.",
        "documents": ["Business registration", "Most recent tax return", "Payroll summary"],
        "source_url": "https://dcs.columbia.example.gov/programs/sbrg",
        "last_updated": "2026-10-10",
    },
}

# Monthly gross income limits (USD) by household size.
# Sizes larger than 6: add the "per_additional" amount for each extra person.
INCOME_LIMITS = {
    "FAP": {1: 1_980, 2: 2_680, 3: 3_380, 4: 4_080, 5: 4_780, 6: 5_480, "per_additional": 700},
    "HEAP": {1: 2_640, 2: 3_450, 3: 4_260, 4: 5_070, 5: 5_880, 6: 6_690, "per_additional": 810},
    "CCS": {1: 3_200, 2: 4_300, 3: 5_400, 4: 6_500, 5: 7_600, 6: 8_700, "per_additional": 1_100},
    "VHG": {1: 4_100, 2: 4_700, 3: 5_300, 4: 5_850, 5: 6_350, 6: 6_800, "per_additional": 450},
}

APPLICATIONS = {
    "DCS-10422": {"program": "FAP", "status": "Approved", "detail": "First benefits deposit scheduled for the 5th of next month."},
    "DCS-10587": {"program": "HEAP", "status": "Pending documents", "detail": "We are missing a recent utility bill. Upload it in the portal within 10 days."},
    "DCS-10613": {"program": "CCS", "status": "Under review", "detail": "A caseworker will contact you within 7 business days."},
    "DCS-10790": {"program": "VHG", "status": "Denied", "detail": "DD-214 could not be verified. You can appeal within 30 days."},
}

OFFICES = [
    {"name": "Capitol City DCS Office", "zip_prefixes": ["200", "201"], "address": "100 Liberty Ave, Capitol City, CB 20010",
     "hours": "Mon-Fri 8:00am-5:00pm", "phone": "(555) 010-2000"},
    {"name": "Riverside DCS Office", "zip_prefixes": ["202", "203"], "address": "45 Mill St, Riverside, CB 20231",
     "hours": "Mon-Thu 9:00am-6:00pm", "phone": "(555) 010-3000"},
    {"name": "Lakeview DCS Office", "zip_prefixes": ["204", "205"], "address": "9 Harbor Rd, Lakeview, CB 20455",
     "hours": "Tue-Sat 9:00am-4:00pm", "phone": "(555) 010-4000"},
]
