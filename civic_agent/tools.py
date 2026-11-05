"""Tools the CivicAssist agent can call.

Each tool is a plain Python function wrapped with LangChain's ``@tool``
decorator (the docstring becomes the tool description the model sees). The
OpenInference instrumentor records every call as a TOOL span with its
arguments and return value, so you can see exactly what the agent asked for
and what it got back.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from .knowledge_base import APPLICATIONS, INCOME_LIMITS, OFFICES, PROGRAMS


def _income_limit(program_id: str, household_size: int) -> int:
    table = INCOME_LIMITS[program_id]
    if household_size <= 6:
        return table[household_size]
    return table[6] + table["per_additional"] * (household_size - 6)


_STOPWORDS = {"program", "programs", "help", "with", "that", "this", "what", "does", "offer",
              "apply", "about", "have", "need", "state", "columbia", "benefit", "benefits"}


def search_programs_impl(query: str) -> str:
    q = query.lower()
    tokens = [w.strip("?,.!()") for w in q.split()]
    words = [w for w in tokens if len(w) > 3 and w not in _STOPWORDS]
    hits = []
    for p in PROGRAMS.values():
        haystack = " ".join([p["id"], p["name"], p["description"], p["eligibility"]]).lower()
        if any(word in haystack for word in words) or p["id"].lower() in tokens:
            hits.append(p)
    if not hits:
        return json.dumps({"results": [], "note": "No DCS program matches this query."})
    return json.dumps({"results": hits})


def check_eligibility_impl(program_id: str, household_size: int, monthly_income: float) -> str:
    program_id = program_id.upper()
    if program_id not in INCOME_LIMITS:
        return json.dumps({"error": f"Eligibility rules for '{program_id}' are not available. "
                                    "Valid program IDs: " + ", ".join(INCOME_LIMITS)})
    if household_size < 1:
        return json.dumps({"error": "household_size must be at least 1."})
    limit = _income_limit(program_id, household_size)
    eligible = monthly_income <= limit
    return json.dumps({
        "program_id": program_id,
        "household_size": household_size,
        "monthly_income": monthly_income,
        "income_limit": limit,
        "income_eligible": eligible,
        "note": "Income test only. Final eligibility is determined by a caseworker.",
        "source_url": PROGRAMS[program_id]["source_url"],
    })


def get_application_status_impl(application_id: str) -> str:
    app = APPLICATIONS.get(application_id.strip().upper())
    if not app:
        return json.dumps({"error": f"No application found with ID {application_id}."})
    return json.dumps({"application_id": application_id.upper(), **app})


def find_office_impl(zip_code: str) -> str:
    for office in OFFICES:
        if any(zip_code.startswith(prefix) for prefix in office["zip_prefixes"]):
            return json.dumps({k: v for k, v in office.items() if k != "zip_prefixes"})
    return json.dumps({"error": f"No DCS office serves ZIP {zip_code}. Call the DCS hotline at (555) 010-1000."})


# ---- Agent-facing tool wrappers -------------------------------------------

@tool(parse_docstring=True)
def search_programs(query: str) -> str:
    """Search the official DCS program catalog.

    Returns program descriptions, eligibility rules, required documents, and a source URL.

    Args:
        query: Keywords describing the program or need (e.g. "food", "heating bill").
    """
    return search_programs_impl(query)


@tool(parse_docstring=True)
def check_eligibility(program_id: str, household_size: int, monthly_income: float) -> str:
    """Run the official income test for a DCS program.

    Args:
        program_id: Program ID from search_programs (FAP, HEAP, CCS, or VHG).
        household_size: Number of people in the household.
        monthly_income: Gross monthly household income in USD.
    """
    return check_eligibility_impl(program_id, household_size, monthly_income)


@tool(parse_docstring=True)
def get_application_status(application_id: str) -> str:
    """Look up the status of a submitted application.

    Args:
        application_id: Application ID, formatted like DCS-12345.
    """
    return get_application_status_impl(application_id)


@tool(parse_docstring=True)
def find_office(zip_code: str) -> str:
    """Find the DCS office that serves a ZIP code, with address, hours, and phone.

    Args:
        zip_code: Five-digit ZIP code.
    """
    return find_office_impl(zip_code)


ALL_TOOLS = [search_programs, check_eligibility, get_application_status, find_office]
