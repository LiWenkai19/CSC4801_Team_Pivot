"""FP-MATCH-1 性质测试：独立 oracle、固定规模、可复现。

覆盖 `docs/REQUIREMENTS.md` 第 5 节 FP-MATCH-1 的匹配分数与技能归一化。所有期望值
都来自需求文字：

    score = 100                                      when |R| = 0
    score = floor(100 * |C intersection R| / |R|)    otherwise

以及“去掉首尾空白、转换为小写、删除空值、删除重复”的归一化描述。期望值由
`_requirement_score` / `_requirement_normalize` 用 `Fraction`、集合交和
`math.floor` 独立实现，**不调用** `match_score` 或 `normalize_skills`；实现和
oracle 是两套代码，实现写错时测试变红，而不是用实现给自己生成期望值。

大小写按需求“转换为小写”理解为 Python `str.lower()`，因此 `ß`、`İ` 等字符按该
映射的行为断言（例如 `"ß".lower() == "ß"`，不会折叠成 `"ss"`）。

规模固定以便复现：每个性质 `max_examples=200`、`derandomize=True`（固定种子，
同一份代码和依赖每次生成同一批例子）、`deadline=None`、`database=None`（不在
仓库或镜像里写 `.hypothesis/`）。技能词策略把“排除代理项的自由文本”与固定词表
混合，再随机加前后空白；列表长度上限 10。
"""

from fractions import Fraction
from math import floor

from hypothesis import example, given, settings
from hypothesis import strategies as st

from app.employer.matching import match_score
from app.users.service import normalize_skills

PADDING = st.sampled_from(["", " ", "\t", "\n"])

FIXED_SKILLS = (
    "Python",
    "SQL",
    "Rust",
    "C++",
    "C#",
    ".NET",
    "机器学习",
    "ß",
    "SS",
    "İ",
    "i̇",
    "",
)

FREE_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    max_size=12,
)

# 技能词 = 随机前后空白 + （自由文本或固定词表）。
SKILL_WORD = st.builds(
    lambda left, body, right: left + body + right,
    PADDING,
    st.one_of(FREE_TEXT, st.sampled_from(FIXED_SKILLS)),
    PADDING,
)

SKILL_LIST = st.lists(SKILL_WORD, max_size=10)

# 归一化后一定为空的需求列表：只有空白字符，归一化时全部删除。
BLANK_SKILL_LIST = st.lists(
    st.sampled_from(["", " ", "\t", "\n", "  ", "\t \n"]), max_size=10
)

# 归一化后长度至少 27 的无关技能，必然长于任何技能词（自由文本 ≤ 12，固定词 ≤ 6），
# 因此一定不在需求技能集合里。
IRRELEVANT_SKILL = st.builds(
    lambda digits: "irrelevant_skill_" + digits,
    st.text(alphabet="0123456789", min_size=10, max_size=20),
)


def _requirement_normalize(skills):
    """需求文字的直接翻译：去首尾空白、转小写、去空项、去重、按名称排序。"""
    return sorted({skill.strip().lower() for skill in skills if skill.strip()})


def _requirement_score(candidate_skills, required_skills):
    """FP-MATCH-1 公式的独立实现（Fraction + 集合交 + floor），不引用被测函数。"""
    candidate = set(_requirement_normalize(candidate_skills))
    required = set(_requirement_normalize(required_skills))
    if not required:
        return 100
    return floor(Fraction(100 * len(candidate & required), len(required)))


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, SKILL_LIST)
@example([], [])
@example(["Python"], [])
@example(["Python", "SQL"], ["Python", "SQL", "Rust"])
def test_fp_match_1_property_score_is_bounded_integer(candidate, required):
    """结果必须始终是 0 到 100 的整数（不是 bool，也不越界）。"""
    score = match_score(candidate, required)
    assert type(score) is int, f"score={score!r} candidate={candidate!r}"
    assert 0 <= score <= 100, (
        f"score={score} candidate={candidate!r} required={required!r}"
    )


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, SKILL_LIST)
@example(["Python", "SQL"], ["Python", "SQL"])
@example(["Python"], ["Python", "SQL"])
@example(["Rust"], ["Python", "SQL"])
@example(["anything"], [])
@example(["a", "b"], ["a", "b", "c"])
@example([" PYTHON ", "python", ""], ["python", " SQL ", "sql", " "])
def test_fp_match_1_property_equals_independent_oracle(candidate, required):
    """实际分数必须等于需求公式的独立实现。"""
    expected = _requirement_score(candidate, required)
    actual = match_score(candidate, required)
    assert actual == expected, (
        f"candidate={candidate!r} required={required!r} "
        f"expected={expected} actual={actual}"
    )


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, BLANK_SKILL_LIST)
@example(["Python"], [])
@example([], [])
@example(["Python", "SQL"], [" ", "\t", ""])
def test_fp_match_1_property_empty_required_is_100(candidate, required):
    """需求技能归一化后为空（含全空白列表）时，分数恒为 100。"""
    assert _requirement_score(candidate, required) == 100
    assert match_score(candidate, required) == 100, (
        f"candidate={candidate!r} required={required!r}"
    )


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, SKILL_LIST)
@example(["Python", "SQL"], ["Python", "SQL"])
@example([], [])
def test_fp_match_1_property_invariant_under_permutation_duplication_whitespace(
    candidate, required
):
    """顺序、重复、空项和首尾空白都不得改变分数。"""
    baseline = match_score(candidate, required)

    reordered_candidate = list(reversed(candidate))
    reordered_required = list(reversed(required))
    assert match_score(reordered_candidate, required) == baseline
    assert match_score(candidate, reordered_required) == baseline
    assert match_score(reordered_candidate, reordered_required) == baseline

    duplicated = candidate + candidate + ["", " ", "\t"]
    assert match_score(duplicated, required) == baseline
    assert match_score(candidate, required + required + [""]) == baseline

    padded_candidate = [" " + item + "\n" for item in candidate]
    padded_required = ["\t" + item + " " for item in required]
    assert match_score(padded_candidate, required) == baseline
    assert match_score(candidate, padded_required) == baseline
    assert match_score(padded_candidate, padded_required) == baseline


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, SKILL_LIST, IRRELEVANT_SKILL)
@example(["Rust"], ["Python"], "irrelevant_skill_0123456789")
def test_fp_match_1_property_irrelevant_skill_does_not_change_score(
    candidate, required, irrelevant
):
    """给候选人加一个不在需求集合里的技能，分数不得改变。"""
    assert irrelevant.strip().lower() not in set(_requirement_normalize(required))
    baseline = match_score(candidate, required)
    assert match_score(candidate + [irrelevant], required) == baseline, (
        f"candidate={candidate!r} required={required!r} irrelevant={irrelevant!r}"
    )


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, SKILL_LIST)
@example(["Python"], ["Python"])
@example(["Rust"], ["Python", "SQL"])
def test_fp_match_1_property_adding_required_skill_never_decreases(
    candidate, required
):
    """把需求技能补进候选人技能，分数不得下降。

    这里“加入需求技能”指加入候选人的技能列表：|R| 不变、|C∩R| 只增不减，
    所以分数只可能上升或持平。若改为扩大需求集合，分母会变大，当新增的需求技能
    不在候选人技能中时分数反而下降，那是另一条性质。
    """
    required_normalized = set(_requirement_normalize(required))
    if not required_normalized:
        assert match_score(candidate, required) == 100
        return

    baseline = match_score(candidate, required)
    candidate_normalized = set(_requirement_normalize(candidate))
    missing = sorted(required_normalized - candidate_normalized)
    if missing:
        assert match_score(candidate + [missing[0]], required) >= baseline
    already_present = sorted(required_normalized & candidate_normalized)
    if already_present:
        assert match_score(candidate + [already_present[0]], required) == baseline


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, SKILL_LIST)
@example([], [])
@example(["Rust"], ["Python", "SQL"])
@example(["Python"], ["Python", "SQL"])
def test_fp_match_1_property_monotone_in_overlap(candidate, required):
    """重叠部分增大时分数不减；补满全部需求技能时必然是 100。"""
    baseline = match_score(candidate, required)
    required_normalized = sorted(set(_requirement_normalize(required)))
    augmented = candidate + required_normalized
    assert match_score(augmented, required) >= baseline
    if required_normalized:
        assert match_score(augmented, required) == 100, (
            f"candidate={candidate!r} required={required!r}"
        )


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST)
@example(["Python ", "python", ""])
@example([])
def test_fp_match_1_property_normalize_is_idempotent_and_canonical(skills):
    """归一化结果等于需求的“trim/lower/去空/去重”规范形式，且是幂等的。"""
    expected = _requirement_normalize(skills)
    actual = normalize_skills(skills)
    assert actual == expected, (
        f"skills={skills!r} expected={expected!r} actual={actual!r}"
    )
    assert normalize_skills(actual) == actual
    assert actual == sorted(set(actual))
    assert all(skill and skill == skill.strip().lower() for skill in actual)


@settings(derandomize=True, max_examples=200, deadline=None, database=None)
@given(SKILL_LIST, SKILL_LIST)
@example([], [])
@example([" Python "], ["SQL"])
def test_fp_match_1_property_inputs_are_not_mutated(candidate, required):
    """打分与归一化都不得原地修改调用者传入的列表。"""
    candidate_before = list(candidate)
    required_before = list(required)
    match_score(candidate, required)
    normalize_skills(candidate)
    normalize_skills(required)
    assert candidate == candidate_before
    assert required == required_before
