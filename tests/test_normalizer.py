from __future__ import annotations

import pytest

from models.entities import Relation, RelationKind, UiKind
from models.relation_normalizer import (
    SelfRelationError,
    code_key,
    denormalize,
    normalize,
    search_key,
    split_code_title,
)


@pytest.mark.parametrize("raw", ["31 23 00", "312300", "31-23-00", "31.23.00", " 31  23 00 "])
def test_code_key_variants(raw):
    assert code_key(raw) == "312300"


def test_code_key_with_letters_and_dots():
    assert code_key("4.28.33") == "42833"
    assert code_key("01 35 13a") == "013513A"


def test_normalize_references():
    assert normalize(1, UiKind.REFERENCES, 2) == (1, 2, RelationKind.REF)
    assert normalize(2, UiKind.REFERENCES, 1) == (2, 1, RelationKind.REF)


def test_normalize_referenced_by_swaps():
    assert normalize(1, UiKind.REFERENCED_BY, 2) == (2, 1, RelationKind.REF)


def test_self_relation():
    with pytest.raises(SelfRelationError):
        normalize(3, UiKind.REFERENCES, 3)


def test_denormalize_roundtrip():
    rel = Relation(1, 7, 3, RelationKind.REF)
    a, kind, b = denormalize(rel)
    assert kind is UiKind.REFERENCES and normalize(a, kind, b) == (7, 3, RelationKind.REF)
    assert not hasattr(UiKind, "MUTUAL") and not hasattr(RelationKind, "MUTUAL")


def test_split_code_title():
    assert split_code_title("31 23 00 Excavación") == ("31 23 00", "Excavación")
    assert split_code_title("4.28.33 Sitio de obra") == ("4.28.33", "Sitio de obra")
    assert split_code_title("31 23 00") == ("31 23 00", "")
    assert split_code_title("Solo texto") == ("Solo texto", "")


def test_search_key_strips_accents():
    assert search_key("Excavación") == "excavacion"
    assert "excavacion" in search_key("31 23 00 EXCAVACIÓN")
