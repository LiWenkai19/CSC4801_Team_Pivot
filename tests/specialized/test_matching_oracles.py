from fractions import Fraction
from math import floor
import random

import pytest


def oracle(candidate, required):
    c = {value.strip().lower() for value in candidate if value.strip()}
    r = {value.strip().lower() for value in required if value.strip()}
    return 100 if not r else floor(Fraction(100 * len(c.intersection(r)), len(r)))


@pytest.mark.parametrize(
    "candidate,required,expected",
    [
        (["Python", "SQL"], ["Python", "SQL"], 100),
        (["Python"], ["Python", "SQL"], 50),
        (["Rust"], ["Python", "SQL"], 0),
        ([], [], 100),
        (["anything"], [], 100),
        (["a", "b"], ["a", "b", "c"], 66),
        (["a"], ["a", "b", "c"], 33),
        ([" PYTHON ", "python", ""], ["python", " SQL ", "sql", " "], 50),
        (["ß"], ["SS"], 0),
        (["İ"], ["i"], 0),
        (["İ"], ["i\u0307"], 100),
        (["机器学习", "C++"], ["机器学习", "c++", "sql"], 66),
    ],
)
def test_exact_formula_normalization_and_unicode_contract(
    candidate, required, expected
):
    from app.employer.matching import match_score

    assert oracle(candidate, required) == expected
    assert match_score(candidate, required) == expected


@pytest.mark.parametrize("seed", [4801, 20261122, 73013])
def test_seeded_structured_inputs_with_independent_and_metamorphic_oracles(
    seed, evidence
):
    from app.employer.matching import match_score

    rng = random.Random(seed)
    words = [
        "Python",
        "SQL",
        "Rust",
        "C++",
        "C#",
        ".NET",
        "Go",
        "机器学习",
        "İ",
        "i\u0307",
        "SS",
        "ß",
        "",
        "lua",
    ]
    pads = ["", " ", "\t", "\n", "\u00a0"]
    checked = 0
    for trial in range(1000):

        def generate():
            return [
                rng.choice(pads) + rng.choice(words) + rng.choice(pads)
                for _ in range(rng.randrange(9))
            ]

        candidate, required = generate(), generate()
        original = (candidate[:], required[:])
        expected = oracle(candidate, required)
        result = match_score(candidate, required)
        context = {
            "seed": seed,
            "trial": trial,
            "candidate": candidate,
            "required": required,
            "expected": expected,
            "actual": result,
        }
        assert result == expected, context
        assert type(result) is int and 0 <= result <= 100, context
        assert (
            match_score(list(reversed(candidate)), list(reversed(required))) == result
        ), context
        assert (
            match_score(
                candidate + candidate + ["", "  "], required + required + ["\t"]
            )
            == result
        ), context
        assert (
            match_score(
                [" " + x + " " for x in candidate], ["\t" + x + "\n" for x in required]
            )
            == result
        ), context
        if all(x.isascii() for x in candidate + required):
            assert (
                match_score(
                    [x.swapcase() for x in candidate], [x.swapcase() for x in required]
                )
                == result
            ), context
        assert (
            match_score(candidate + ["unique_irrelevant_skill_4801"], required)
            == result
        ), context
        c = {x.strip().lower() for x in candidate if x.strip()}
        r = {x.strip().lower() for x in required if x.strip()}
        if r - c:
            missing = sorted(r - c)[0]
            assert match_score(candidate + [missing], required) >= result, context
        assert (candidate, required) == original, context
        checked += 1
    evidence(
        "generated",
        {
            "seed": seed,
            "trials": checked,
            "oracle": "independent Fraction/floor set overlap",
            "metamorphic_dimensions": [
                "permutation",
                "duplicate/empty",
                "whitespace",
                "ASCII-only case",
                "irrelevant skill",
                "new satisfied skill",
            ],
            "coverage_guided": False,
        },
    )


def test_candidate_and_employer_share_the_scoring_implementation():
    from app.candidate import service as candidate
    from app.employer import service as employer, matching

    assert (
        candidate.match_score is matching.match_score
        and employer.match_score is matching.match_score
    )
