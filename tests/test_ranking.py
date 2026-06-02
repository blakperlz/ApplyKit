from applykit.models import DimensionScore, Evaluation
from applykit.ranking import filter_by, filter_by_grade, rank, select_for_craft


def _ev(company, role, score):
    dims = [DimensionScore("role_fit", "Role Fit", score=score, weight=100)]
    return Evaluation.from_dimension_scores(company, role, dims)


def test_rank_orders_best_first():
    evals = [_ev("A", "r", 70), _ev("B", "r", 95), _ev("C", "r", 82)]
    ranked = rank(evals)
    assert [e.company for e in ranked] == ["B", "C", "A"]


def test_rank_breaks_ties_by_company():
    evals = [_ev("Zed", "r", 80), _ev("Ace", "r", 80)]
    ranked = rank(evals)
    assert [e.company for e in ranked] == ["Ace", "Zed"]


def test_filter_by_grade():
    evals = [_ev("A", "r", 95), _ev("B", "r", 86), _ev("C", "r", 70)]
    kept = filter_by_grade(evals, "B+")
    assert {e.company for e in kept} == {"A", "B"}


def test_filter_by_company_and_score():
    evals = [_ev("A", "r", 95), _ev("A", "s", 60), _ev("B", "r", 95)]
    assert len(filter_by(evals, company="A")) == 2
    assert len(filter_by(evals, min_score=90)) == 2


def test_select_for_craft_threshold_and_cap():
    evals = [_ev("A", "r", 95), _ev("B", "r", 92), _ev("C", "r", 88),
             _ev("D", "r", 70)]
    # threshold B+ keeps the first three; cap 2 takes top two by score.
    chosen = select_for_craft(evals, threshold="B+", cap=2)
    assert [e.company for e in chosen] == ["A", "B"]


def test_select_for_craft_per_company_threshold():
    evals = [_ev("Dream Co", "r", 82), _ev("Other", "r", 82)]
    # Dream Co threshold B (82 -> B qualifies); Other uses B+ (82 -> B fails).
    def per_company(name):
        return "B" if name == "Dream Co" else "B+"

    chosen = select_for_craft(evals, threshold="B+", cap=5,
                              company_threshold=per_company)
    assert [e.company for e in chosen] == ["Dream Co"]
