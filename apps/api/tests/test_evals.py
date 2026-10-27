"""Eval scoring is deterministic and tested here; running the evals needs a real model."""

from hosoai.evals.run import load_cases
from hosoai.evals.scoring import RoutingCase, amounts, score_fee, score_routing
from hosoai.procedures.store import get_store
from hosoai.settings import Settings

CATALOG = {"passport", "id-card-reissue"}


def case(expected: list[str], allow_nf: bool = False) -> RoutingCase:
    return RoutingCase(
        id="x",
        category="direct",
        lang="vi",
        query="q",
        expected=expected,
        allow_not_found=allow_nf,
    )


def test_routing_scoring() -> None:
    ok = score_routing(case(["passport"]), ["passport"], ["passport"], True, CATALOG, 1.0)
    assert ok.correct and ok.invented == []
    wrong = score_routing(case(["passport"]), ["id-card-reissue"], [], True, CATALOG, 1.0)
    assert not wrong.correct
    refuse = score_routing(case([]), [], ["made-up"], True, CATALOG, 1.0)
    assert refuse.correct and refuse.invented == ["made-up"]
    assert not score_routing(case([]), ["passport"], [], True, CATALOG, 1.0).correct
    assert score_routing(case(["passport"], allow_nf=True), [], [], True, CATALOG, 1.0).correct


def test_amounts_ignore_years_and_legal_numbers() -> None:
    text = "Phí: 160.000/hộ chiếu, cấp lại 320.000đ (Thông tư số 44/2023/TT-BTC, năm 2023)"
    assert amounts(text) == {160000, 320000}
    assert amounts("200,000 VND hoặc 200000 đồng") == {200000}
    assert amounts("Không") == set()


def test_fee_scoring_flags_unsupported_amounts() -> None:
    o = score_fee("passport", "Phí: 160.000/hộ chiếu", "Lệ phí là 200.000 đồng")
    assert o.unsupported_amounts == [200000]
    o = score_fee("passport", "Phí: 160.000/hộ chiếu", "Khoảng 160.000 đồng")
    assert o.unsupported_amounts == []


def test_dataset_is_valid_and_points_at_known_procedures() -> None:
    cases = load_cases(Settings().data_dir / "evals" / "routing.jsonl")
    known = {p.slug for p in get_store().list()}
    assert len(cases) >= 60
    assert len({c.id for c in cases}) == len(cases)
    for c in cases:
        assert set(c.expected) <= known, c.id
    assert {c.category for c in cases} >= {"direct", "out_of_scope", "adversarial"}
