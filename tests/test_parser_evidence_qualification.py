"""Protect parser qualification from false positive evidence-preservation claims."""
import importlib.util
from pathlib import Path

import pytest


def load(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / "engineering" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load("evaluate_parser_evidence")
probe = load("probe_document_parsers")


@pytest.mark.parametrize("actual", ["1958", "1,958", "958.4", "958,000"])
def test_numeric_substring_is_not_retained_fact(actual):
    assert not audit.contains(actual, "958")


def test_same_document_does_not_prove_same_table():
    check = {"required": ["Nine Months", "Revenue", "21,568"], "scope": "table"}
    output = {"text": "Nine Months Revenue 21,568", "blocks": [
        {"kind": "table", "text": "Nine Months Revenue"},
        {"kind": "table", "text": "Three Months Revenue 21,568"}]}
    result = audit.evaluate(check, output)
    assert result["whole_text_retained"]
    assert not result["same_table_retained"]
    assert not result["passed"]


def test_datamule_table_context_never_crosses_identity():
    output = {"tuples": [[1, "table_preamble", "In millions"],
                         [1, "table_data", [["Cash", "11,578"]]],
                         [2, "table_preamble", "Prior year"],
                         [2, "table_data", [["Cash", "11,528"]]]]}
    tables = audit.table_texts(output)
    assert "In millions Cash 11,578" in tables
    assert not any("Prior year" in t and "11,578" in t for t in tables)


def test_blank_check_cannot_pass():
    with pytest.raises(ValueError, match="empty_reviewed_anchor"):
        audit.contains("anything", " ")


def test_attached_postamble_cannot_supply_missing_table_evidence():
    check = {"required": ["Revenue", "21,568"], "scope": "table"}
    output = {"text": "Revenue 21,568", "tuples": [
        [1, "table_data", [["Revenue", "7,302"]]],
        [1, "table_postamble", "script Revenue 21,568"],
        [1, "table_footnotes", "another period Revenue 21,568"]]}
    assert not audit.evaluate(check, output)["passed"]


def test_sentence_punctuation_is_not_decimal_continuation():
    assert audit.contains("Exhibit 99.1, attached.", "Exhibit 99.1")
    assert audit.contains("Revenue 958.", "958")


def test_probe_allows_windows_socketpair_but_blocks_remote():
    called = []
    connect = probe.local_socket_only(lambda sock, address: called.append(address))
    connect(None, ("127.0.0.1", 12345))
    assert called == [("127.0.0.1", 12345)]
    for address in [("8.8.8.8", 443), ("example.com", 443)]:
        with pytest.raises(RuntimeError, match="offline_parser_network_attempt"):
            connect(None, address)
