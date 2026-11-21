"""Offline checks on the step 01 case files (cases/cep9.json, cases/a160.json)."""
import re

import pytest

from sites import site_names
from step01_select_host import cases

REFCAT = re.compile(r"^[0-9]{7}[A-Z]{2}[0-9]{4}[A-Z]$")


def test_both_cases_exist():
    assert {"cep9", "a160"} <= set(cases.case_names())


@pytest.mark.parametrize("name", ["cep9", "a160"])
def test_case_is_complete(name):
    case = cases.load_case(name)
    assert case["site_file"] in site_names()
    for roof in case["host"]["roofs"]:
        assert REFCAT.match(roof["refcat"]), roof["refcat"]
    for p in case["participants"]:
        ref = p.get("refcat")
        assert ref is None or ref == "see host roofs" or REFCAT.match(ref), (p["id"], ref)
    assert case["available_data"] and case["unknowns"]
    # data/ and root run outputs are local only (not in git); examples/ must be there
    assert [f for f in cases.missing_files(case) if f.startswith("examples/")] == []
    assert cases.summary(case)
