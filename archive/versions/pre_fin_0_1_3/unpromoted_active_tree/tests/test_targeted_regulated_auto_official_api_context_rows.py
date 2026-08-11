from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_targeted_regulated_auto_official_api_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_targeted_regulated_auto_official_api_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_clinical_trials_rows_accept_bound_collaborator() -> None:
    rows = MODULE._clinical_trials_rows(
        {"ticker": "MRNA", "company_name": "Moderna"},
        [
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT1", "briefTitle": "VX-522 Study"},
                    "statusModule": {"overallStatus": "RECRUITING", "startDateStruct": {"date": "2026-01"}},
                    "sponsorCollaboratorsModule": {
                        "leadSponsor": {"name": "Vertex Pharmaceuticals Incorporated", "class": "INDUSTRY"},
                        "collaborators": [{"name": "Moderna, Inc", "class": "INDUSTRY"}],
                    },
                }
            }
        ],
        aliases=("Moderna",),
        api_url="https://clinicaltrials.gov/api/v2/studies?query.spons=Moderna",
        generated_at="2026-06-19T00:00:00Z",
        max_rows=1,
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "MRNA"
    assert rows[0]["source_entity_name"] == "Moderna, Inc"
    assert rows[0]["source_id"] == "clinicaltrials_api"


def test_openfda_device_510k_rows_are_regulated_context() -> None:
    rows = MODULE._openfda_device_510k_rows(
        {"ticker": "WST", "company_name": "West Pharmaceutical Services"},
        [
            {
                "applicant": "West Pharmaceutical Services, Inc.",
                "k_number": "K141464",
                "product_code": "MEG",
                "openfda": {"device_name": "Syringe, Antistick"},
                "decision_date": "2014-08-01",
                "decision_description": "Substantially Equivalent",
            }
        ],
        aliases=("West Pharmaceutical",),
        api_url="https://api.fda.gov/device/510k.json?search=applicant:%22WEST%20PHARMACEUTICAL%22",
        generated_at="2026-06-19T00:00:00Z",
        max_rows=1,
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "WST"
    assert rows[0]["source_id"] == "openfda_api"
    assert rows[0]["application_number"] == "K141464"
    assert rows[0]["device_id"] == "MEG"
    assert rows[0]["product_binding_status"] == "product_mentioned_in_snapshot"


def test_fda_animal_drug_rows_are_regulated_context() -> None:
    rows = MODULE._fda_animal_drug_rows(
        {"ticker": "ZTS", "company_name": "Zoetis"},
        [
            {
                "applicationId": 13285,
                "applicationNumber": 141555,
                "applicationType": "N",
                "applicationStatusCode": "A",
                "publishDate": 1729123200000,
                "proprietaryName": "apoquel® chewable",
                "sponsorName": "Zoetis Inc.",
                "activeIngredientName": "Oclacitinib",
            }
        ],
        sponsor_aliases=("Zoetis Inc.",),
        api_url="https://animaldrugsatfda.fda.gov/adafda/app/search/public/advancedSearch",
        query_payload={"proprietaryName": "apoquel®"},
        generated_at="2026-06-19T00:00:00Z",
        max_rows=1,
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "ZTS"
    assert rows[0]["source_id"] == "fda_animal_drugs_api"
    assert rows[0]["application_number"] == "N141555"
    assert rows[0]["product_or_segment"] == "apoquel® chewable"
    assert rows[0]["active_ingredient_name"] == "Oclacitinib"
    assert rows[0]["period"] == "2024-10-17"
    assert "sales" in rows[0]["forbidden_claims"]


def test_nhtsa_manufacturer_rows_cover_pcar_identity() -> None:
    rows = MODULE._nhtsa_manufacturer_rows(
        {"ticker": "PCAR", "company_name": "PACCAR Inc"},
        [
            {
                "Mfr_Name": "PACCAR INC.",
                "VehicleTypes": [{"Name": "Truck", "IsPrimary": True}],
            }
        ],
        alias="PACCAR",
        api_url="https://vpic.nhtsa.dot.gov/api/vehicles/GetManufacturerDetails/PACCAR?format=json",
        generated_at="2026-06-19T00:00:00Z",
        max_rows=1,
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "PCAR"
    assert rows[0]["source_id"] == "nhtsa_vpic_api"
    assert rows[0]["manufacturer"] == "PACCAR INC."
    assert rows[0]["product_or_segment"] == "Truck"
