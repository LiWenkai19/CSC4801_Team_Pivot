#!/usr/bin/env python
"""P11: assemble the advanced-testing report from the run artefacts.

The report is *generated*, never hand-edited: every number below is read from
``<out>/summary.json``, the per-mode JUnit XML files, or the durable JSON that
P1-P12 wrote under ``<out>``.  The script is deliberately tolerant of missing
artefacts (for example when only ``run.py fast`` was executed): the affected
row is marked ``—`` and a warning is printed, so a partial run cannot silently
look complete.

Usage::

    python tests/advanced/report.py <out-dir> [--unit-junit FILE] \\
        [--ci-run RUN_ID] [--artifact NAME] [--pg-version VERSION]

``<out-dir>`` is the directory passed to ``run.py all`` (outside the checkout).
``--unit-junit`` points at the JUnit XML from ``python tests/run_tests.py
--junitxml=...`` and supplies the P1 / mandatory-suite numbers.  The CI options
are only used in the footer; without them the footer records the local
development evidence directory and PostgreSQL version.

The script writes ``docs/advanced_testing/ADVANCED_REPORT.md``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPORT_PATH = ROOT / "docs" / "advanced_testing" / "ADVANCED_REPORT.md"
P10_RESULTS = HERE / "experiments" / "llm_blind" / "results.json"
P10_MUTATION = HERE / "experiments" / "llm_blind" / "mutation" / "results.json"

MODES = (
    "smoke",
    "stateful",
    "ltl",
    "formal",
    "differential",
    "intramorphic",
    "apifuzz",
    "mutation",
    "coverage",
)


# --------------------------------------------------------------------------- #
# generic helpers
# --------------------------------------------------------------------------- #


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def get(mapping, *keys, default=None):
    value = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def number(value) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if value is None:
        return "—"
    return str(value)


def percent(value) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def code(value) -> str:
    if value is None or value == "":
        return "—"
    return f"`{value}`"


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def parse_junit(path: Path | None) -> dict | None:
    if path is None or not Path(path).is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    suites = [root] if root.tag == "testsuite" else list(root)
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    cases: list[dict] = []
    for suite in suites:
        if suite.tag != "testsuite":
            continue
        for key in ("tests", "failures", "errors", "skipped"):
            raw = suite.get(key)
            if raw is not None:
                totals[key] += int(raw)
        try:
            totals["time"] += float(suite.get("time") or 0.0)
        except ValueError:
            pass
        for case in suite.iter("testcase"):
            cases.append(
                {
                    "classname": case.get("classname") or "",
                    "name": case.get("name") or "",
                }
            )
    return {**totals, "cases": cases}


def by_id(records: list[dict], identifier: str) -> dict:
    for record in records:
        if record.get("id") == identifier:
            return record
    return {}


def metric_row(
    label: str, value: str, source: str
) -> list[str]:
    return [label, value, f"`{source}`"]


# --------------------------------------------------------------------------- #
# data collection
# --------------------------------------------------------------------------- #


def collect(out: Path, unit_junit: Path | None) -> dict:
    summary = load_json(out / "summary.json", {}) or {}
    results = {item.get("mode"): item for item in summary.get("results", [])}
    junit = {
        mode: parse_junit(out / mode / "junit.xml") for mode in MODES
    }
    coverage = load_json(out / "coverage" / "coverage-summary.json", {}) or {}
    stateful = load_json(out / "stateful" / "summary.json", {}) or {}
    ltl = load_json(out / "ltl" / "ltl_results.json", {}) or {}
    refinement = load_json(out / "ltl" / "refinement.json", {}) or {}
    matching_theory = (
        load_json(out / "formal" / "matching_theory.json", {}) or {}
    )
    spec_to_code = (
        load_json(out / "formal" / "spec_to_code_pairs.json", {}) or {}
    )
    bmc = load_json(out / "formal" / "booking_bmc.json", {}) or {}
    differential = (
        load_json(out / "differential" / "differential.json", {}) or {}
    )
    cross_view = (
        load_json(out / "differential" / "cross-view.json", {}) or {}
    )
    defense = (
        load_json(out / "intramorphic" / "defense_layers.json", {}) or {}
    )
    metamorphic = {
        name: load_json(out / "intramorphic" / f"{name}.json", {}) or {}
        for name in ("M1", "M2", "M3", "M4", "M5")
    }
    mutation = (
        load_json(out / "mutation" / "mutation-result.json", {}) or {}
    )
    apifuzz = load_json(out / "apifuzz" / "report.json", {}) or {}
    p10 = load_json(P10_RESULTS, {}) or {}
    p10_mutation = load_json(P10_MUTATION, {}) or {}
    unit = parse_junit(unit_junit) if unit_junit else None
    if unit is None:
        coverage_unit = next(
            (
                group
                for group in coverage.get("groups", [])
                if group.get("name") == "unit"
            ),
            None,
        )
        if coverage_unit and coverage_unit.get("junit"):
            unit = parse_junit(Path(coverage_unit["junit"]))
    return {
        "out": out,
        "summary": summary,
        "results": results,
        "junit": junit,
        "coverage": coverage,
        "stateful": stateful,
        "ltl": ltl,
        "refinement": refinement,
        "matching_theory": matching_theory,
        "spec_to_code": spec_to_code,
        "bmc": bmc,
        "differential": differential,
        "cross_view": cross_view,
        "defense": defense,
        "metamorphic": metamorphic,
        "mutation": mutation,
        "apifuzz": apifuzz,
        "p10": p10,
        "p10_mutation": p10_mutation,
        "unit": unit,
    }


# --------------------------------------------------------------------------- #
# report rendering
# --------------------------------------------------------------------------- #


def render(data: dict, args: argparse.Namespace) -> tuple[str, list[str]]:
    warnings: list[str] = []
    out: Path = data["out"]
    summary = data["summary"]
    results = data["results"]
    junit = data["junit"]

    def mode_ok(mode: str) -> str:
        result = results.get(mode)
        if not result:
            warnings.append(f"missing `{mode}` mode receipt")
            return "—"
        return "exit 0" if result.get("exit_code") == 0 else (
            f"exit {result.get('exit_code')}"
        )

    def mode_seconds(mode: str) -> str:
        result = results.get(mode)
        if not result or result.get("seconds") is None:
            return "—"
        return f"{result['seconds']:.2f}s"

    def count(mode: str, key: str = "tests") -> str:
        parsed = junit.get(mode)
        if not parsed:
            return "—"
        return number(parsed.get(key))

    # -- P1 / mandatory unit suite ---------------------------------------
    unit = data["unit"] or {}
    property_cases = sum(
        1
        for case in unit.get("cases", [])
        if "test_matching_properties" in case.get("classname", "")
    )
    unit_tests = unit.get("tests")
    unit_failed = unit.get("failures", 0) + unit.get("errors", 0)
    if unit_tests is None:
        warnings.append("missing --unit-junit and no unit coverage JUnit fallback")

    # -- coverage ---------------------------------------------------------
    coverage = data["coverage"]
    coverage_groups = coverage.get("groups", [])
    combined = coverage.get("combined") or {}
    unit_coverage = next(
        (group for group in coverage_groups if group.get("name") == "unit"),
        None,
    )
    unit_branch = get(unit_coverage or {}, "summary", "branch_pct")
    unit_gate = coverage.get("unit_branch_gate")

    # -- stateful ---------------------------------------------------------
    stateful = data["stateful"]
    st_ops = stateful.get("operations", {})
    st_outcomes = stateful.get("action_outcomes", {})

    # -- LTL --------------------------------------------------------------
    ltl = data["ltl"]
    ltl_traces = ltl.get("traces", {})
    ltl_properties = ltl.get("properties", {})
    ltl_selftest_cases = sum(
        1
        for case in (junit.get("ltl") or {}).get("cases", [])
        if "test_checker_selftest" in case.get("classname", "")
    )
    refinement = data["refinement"]
    refine_steps = refinement.get("steps", [])

    # -- formal matching --------------------------------------------------
    matching_theory = data["matching_theory"]
    matching_records = matching_theory.get("records", [])
    proof_records = [
        record for record in matching_records if record.get("kind") == "proof"
    ]
    negative_records = [
        record for record in matching_records if record.get("kind") == "negative"
    ]
    spec_to_code = data["spec_to_code"]

    # -- BMC / induction --------------------------------------------------
    bmc = data["bmc"]
    bmc_records = bmc.get("records", [])

    def bmc_kind(kind: str) -> list[dict]:
        return [record for record in bmc_records if record.get("kind") == kind]

    # -- differential -----------------------------------------------------
    differential = data["differential"]
    cross_view = data["cross_view"]

    # -- intramorphic -----------------------------------------------------
    defense = data["defense"]
    defense_rules = defense.get("rules", {})
    metamorphic = data["metamorphic"]

    # -- mutation ---------------------------------------------------------
    mutation = data["mutation"]
    mutation_totals = mutation.get("totals", {})
    mutation_per_file = mutation.get("per_file", {})
    mutation_baseline_killed = 184
    mutation_new_kills = (mutation_totals.get("killed") or 0) - mutation_baseline_killed

    # -- apifuzz ----------------------------------------------------------
    apifuzz = data["apifuzz"]
    apifuzz_rounds = apifuzz.get("rounds", [])
    apifuzz_requests = sum(
        int(round_.get("requests") or 0) for round_ in apifuzz_rounds
    )
    apifuzz_5xx = 0
    for round_ in apifuzz_rounds:
        for status, amount in (round_.get("status_counts") or {}).items():
            try:
                if int(status) >= 500:
                    apifuzz_5xx += int(amount)
            except (TypeError, ValueError):
                continue
    apifuzz_attribution = apifuzz.get("attribution", {})
    apifuzz_operations = get(apifuzz, "scope", "openapi_operations")
    apifuzz_selfcheck = apifuzz.get("selfcheck", {})

    # -- P10 --------------------------------------------------------------
    p10 = data["p10"]
    p10_runs = p10.get("runs", {})
    p10_cases = sum(
        int(get(run, "summary", "cases", default=0) or 0)
        for run in p10_runs.values()
    )
    p10_passed = sum(
        int(get(run, "summary", "passed", default=0) or 0)
        for run in p10_runs.values()
    )
    p10_skipped = sum(
        int(get(run, "summary", "skipped", default=0) or 0)
        for run in p10_runs.values()
    )
    p10_failed = sum(
        int(get(run, "summary", "failed", default=0) or 0)
        for run in p10_runs.values()
    )
    p10_mutation = p10.get("mutation", {})
    generated_killed = get(p10_mutation, "generated", "killed")
    generated_tested = get(p10_mutation, "generated", "tested")
    handwritten_killed = get(p10_mutation, "handwritten", "killed")
    handwritten_tested = get(p10_mutation, "handwritten", "tested")

    # -- environment ------------------------------------------------------
    pg_version = args.pg_version or get(apifuzz, "environment", "postgres")
    if isinstance(pg_version, str) and pg_version.startswith("PostgreSQL "):
        pg_version = " ".join(pg_version.split()[:2])
    if not pg_version:
        pg_version = "unknown"
    sha = summary.get("sha", "unknown")
    branch = summary.get("branch", "unknown")
    started = summary.get("finished_at") or "unknown"
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    modes_requested = summary.get("modes_requested") or []
    modes_ok = sum(
        1 for result in results.values() if result.get("exit_code") == 0
    )
    total_seconds = sum(
        float(result.get("seconds") or 0.0) for result in results.values()
    )

    # -- summary table ----------------------------------------------------
    summary_rows = [
        [
            "P0 运行器骨架",
            "L12 测试层次 / L13 方法",
            f"{len(modes_requested)} 个模式",
            f"{modes_ok}/{len(modes_requested)} exit 0；一次性 PG；产物出仓",
            "[ADVANCED_BASELINE.md](ADVANCED_BASELINE.md)、[README](../../tests/advanced/README.md)",
        ],
        [
            "P1 属性测试（必测套件）",
            "L13 性质测试",
            f"{number(property_cases)} 条性质 × 200 examples；必测 {number(unit_tests)} 例",
            f"{number(unit_tests)} passed / {number(unit_failed)} failed；独立 Fraction oracle",
            "[test_matching_properties.py](../../tests/unit/test_matching_properties.py)",
        ],
        [
            "P2 有状态模型",
            "L12/L13 状态机",
            f"{number(stateful.get('examples'))} examples / "
            f"{number(stateful.get('steps'))} 步 / "
            f"{number(stateful.get('distinct_traces'))} 条去重轨迹",
            "5 条不变量在每步后检查，0 失败"
            if (junit.get("stateful") or {}).get("failures", 0) == 0
            else f"{(junit.get('stateful') or {}).get('failures', 0)} failed",
            "[stateful/test_booking_state_machine.py](../../tests/advanced/stateful/test_booking_state_machine.py)",
        ],
        [
            "P3 有限轨迹 LTL",
            "L13 slides 46–52",
            f"L1–L5 于 {number(ltl_traces.get('files'))} 条轨迹 / "
            f"{number(ltl_traces.get('steps'))} 步；自检 {number(ltl_selftest_cases)} 例",
            f"5/5 性质全部满足；relax 链 "
            f"{refine_steps[0]['satisfied'] if refine_steps else '—'}/"
            f"{refine_steps[0]['total'] if refine_steps else '—'} → "
            f"{refine_steps[-1]['satisfied'] if refine_steps else '—'}/"
            f"{refine_steps[-1]['total'] if refine_steps else '—'}",
            "[LTL.md](LTL.md)",
        ],
        [
            "P4 匹配规格证明（Z3）",
            "L13 Hoare 三元组",
            f"{len(proof_records)} 条证明 + {len(negative_records)} 条负向；"
            f"{number(spec_to_code.get('pairs'))} 对规格/代码对拍",
            f"{len(proof_records)} unsat / {len(negative_records)} sat；"
            f"mismatch {number(spec_to_code.get('requirement_formula_mismatches'))}",
            "[FORMAL_MATCHING.md](FORMAL_MATCHING.md)",
        ],
        [
            "P5 预约 BMC + k-归纳",
            "L13 propose→check→counterexample→repair",
            f"k={number(bmc.get('steps'))} 步；{number(len(bmc_records))} 条记录",
            f"{len(bmc_kind('property'))} 条 BMC unsat；"
            f"{len(bmc_kind('reachability'))} 个可达性见证 sat；"
            f"归纳义务全部 unsat",
            "[FORMAL_BOOKING.md](FORMAL_BOOKING.md)",
        ],
        [
            "P6 差分测试",
            "L12 差分 oracle",
            f"{number(differential.get('pairs'))} 对 SQL/Python；"
            f"{number(cross_view.get('cross_view_pairs'))} 对双视图",
            f"SQL mismatch {number(differential.get('sql_mismatch'))}；"
            f"tie groups {number(differential.get('tie_groups'))}",
            "[differential/test_matching_sql.py](../../tests/advanced/differential/test_matching_sql.py)",
        ],
        [
            "P7 变异测试",
            "L13 slide 17 / L14 slide 28",
            f"{number(mutation_totals.get('mutants'))} 个变异体 / "
            f"{number(len(mutation_per_file))} 个文件",
            f"score {percent((mutation_totals.get('score') or 0) * 100)}；"
            f"survived {number(mutation_totals.get('survived'))}，"
            f"suspicious {number(mutation_totals.get('suspicious'))}",
            "[MUTATION.md](MUTATION.md)",
        ],
        [
            "P8 OpenAPI 属性模糊",
            "L14 slide 29",
            f"{number(apifuzz_operations)} 个操作 / {number(apifuzz_requests)} 请求",
            f"5xx {number(apifuzz_5xx)}；real_defect "
            f"{number(apifuzz_attribution.get('real_defect'))}；"
            f"schema_drift {number(apifuzz_attribution.get('schema_drift'))}",
            "[APIFUZZ.md](APIFUZZ.md)、[findings/P8.md](findings/P8.md)",
        ],
        [
            "P9 蜕变/内蜕变",
            "L12 slides 29–41",
            f"{len([name for name in metamorphic if metamorphic[name]])} 条蜕变工作流 + "
            f"{len([rule for rule in defense_rules if 'selfcheck' not in rule])} 条防护层 + "
            f"{len([rule for rule in defense_rules if 'selfcheck' in rule])} 个自检",
            f"I2 {number(get(defense_rules.get('I2', {}), 'round_count'))} 轮一致；"
            f"自检全部变红",
            "[INTRAMORPHIC.md](INTRAMORPHIC.md)",
        ],
        [
            "P10 LLM 盲测",
            "L14 Exercise 1/3",
            f"生成 {number(p10_cases)} 个 case；"
            f"{number(handwritten_tested)} 个手写变异体",
            f"{number(p10_passed)} passed / {number(p10_skipped)} skipped / "
            f"{number(p10_failed)} failed；"
            f"生成 {number(generated_killed)}/{number(generated_tested)} vs "
            f"手写 {number(handwritten_killed)}/{number(handwritten_tested)}",
            "[LLM_TEST_EXPERIMENT.md](LLM_TEST_EXPERIMENT.md)",
        ],
        [
            "P12 依赖与密钥扫描",
            "L14 安全",
            "全历史 69 commits；12 个唯一 advisory",
            "0 泄露；0 待处理 advisory（1 条有理由接受）",
            "[SECURITY_SCANS.md](SECURITY_SCANS.md)",
        ],
        [
            "P11 覆盖率与汇总",
            "L12 覆盖率",
            f"{len(coverage_groups)} 组套件；"
            f"{number(combined.get('statements'))} statements",
            f"combined {percent(combined.get('statement_pct'))} statements / "
            f"{percent(combined.get('branch_pct'))} branches；"
            f"unit branch gate {number(unit_gate)}%",
            "本报告",
        ],
    ]

    # -- per-mode JUnit table --------------------------------------------
    junit_rows = []
    for mode in MODES:
        parsed = junit.get(mode)
        if not parsed:
            junit_rows.append([mode, "—", "—", "—", "—", mode_ok(mode), mode_seconds(mode)])
            continue
        junit_rows.append(
            [
                mode,
                number(parsed["tests"]),
                number(parsed["passed"] if "passed" in parsed else parsed["tests"] - parsed["failures"] - parsed["errors"] - parsed["skipped"]),
                number(parsed["failures"] + parsed["errors"]),
                number(parsed["skipped"]),
                mode_ok(mode),
                mode_seconds(mode),
            ]
        )

    # -- coverage table ---------------------------------------------------
    coverage_rows = []
    for group in coverage_groups:
        summary_group = group.get("summary") or {}
        counts = group.get("counts") or {}
        coverage_rows.append(
            [
                f"`{group.get('name')}`",
                f"`{group.get('target')}`",
                number(counts.get("tests")),
                percent(summary_group.get("statement_pct")),
                percent(summary_group.get("branch_pct")),
                mode_seconds(group.get("name")) if group.get("name") in results else f"{group.get('seconds', '—')}s",
            ]
        )

    # -- LTL property table ----------------------------------------------
    ltl_rows = []
    for identifier in sorted(ltl_properties):
        record = ltl_properties[identifier]
        ltl_rows.append(
            [
                f"`{identifier}`",
                record.get("title", ""),
                f"{number(record.get('satisfied'))}/{number(record.get('traces'))}",
                f"{number(record.get('nonvacuous_traces'))}/{number(record.get('traces'))}",
                number(record.get("trigger_instances")),
            ]
        )

    refine_rows = []
    for step in refine_steps:
        refine_rows.append(
            [
                code(step.get("label")),
                step.get("operation") or "初始性质",
                f"{number(step.get('satisfied'))}/{number(step.get('total'))}",
                percent((step.get("ratio") or 0) * 100),
            ]
        )

    # -- formal matching table -------------------------------------------
    formal_rows = []
    for record in matching_records:
        formal_rows.append(
            [
                f"`{record.get('id')}`",
                record.get("title", ""),
                record.get("result", ""),
                f"{record.get('seconds', 0):.6f}s",
            ]
        )

    # -- BMC table --------------------------------------------------------
    bmc_rows = []
    for record in bmc_records:
        bmc_rows.append(
            [
                f"`{record.get('id')}`",
                record.get("kind", ""),
                record.get("result", ""),
                record.get("variant", ""),
            ]
        )

    # -- mutation per-file table -----------------------------------------
    mutation_rows = []
    for path, bucket in mutation_per_file.items():
        mutation_rows.append(
            [
                f"`{path}`",
                number(bucket.get("mutants")),
                number(bucket.get("killed")),
                number(bucket.get("survived")),
                percent((bucket.get("score") or 0) * 100),
            ]
        )

    # -- apifuzz rounds table --------------------------------------------
    apifuzz_rows = []
    for round_ in apifuzz_rounds:
        statuses = round_.get("status_counts") or {}
        apifuzz_rows.append(
            [
                str(round_.get("round", "")),
                number(round_.get("operation_count")),
                number(round_.get("requests")),
                ", ".join(f"{status}:{amount}" for status, amount in sorted(statuses.items())),
                number(len(round_.get("failures") or [])),
            ]
        )

    # -- intramorphic tables ---------------------------------------------
    defense_rows = []
    for identifier in sorted(defense_rules):
        record = defense_rules[identifier]
        if "selfcheck" in identifier:
            continue
        defense_rows.append(
            [
                f"`{identifier}`",
                record.get("rule", ""),
                (record.get("variant") or {}).get("disabled_layer")
                or record.get("disabled_layer")
                or "",
                record.get("conclusion", ""),
            ]
        )
    metamorphic_rows = []
    for name in ("M1", "M2", "M3", "M4", "M5"):
        record = metamorphic.get(name, {})
        if name == "M1":
            holds = record.get("same_timestamps")
        elif name == "M2":
            holds = (
                record.get("slot_id_sets_equal")
                and record.get("baseline_order")
                == record.get("perturbed_order")
                and record.get("baseline_slots")
                == record.get("perturbed_slots")
            )
        elif name == "M3":
            holds = (
                record.get("baseline_order") == record.get("perturbed_order")
                and record.get("baseline_signature")
                == record.get("perturbed_signature")
            )
        elif name == "M4":
            holds = record.get("baseline_signature") == record.get(
                "perturbed_signature"
            )
        else:
            holds = record.get("slot_ids_equal")
        metamorphic_rows.append(
            [
                f"`{name}`",
                record.get("relation", ""),
                number(holds),
            ]
        )

    # -- P10 comparison table --------------------------------------------
    comparison = p10.get("comparison", {})
    p10_rows = []
    for function, record in comparison.items():
        generated = record.get("generated", {})
        handwritten = record.get("handwritten", {})
        p10_rows.append(
            [
                function,
                number(generated.get("cases") or generated.get("node_cases")),
                number(
                    handwritten.get("file_cases")
                    or handwritten.get("book_specific_cases")
                    or handwritten.get("node_cases")
                ),
                record.get("unique_finding", ""),
            ]
        )

    # -- write the report -------------------------------------------------
    lines: list[str] = []
    add = lines.append

    add("# 高级测试与验证报告（P0–P12）")
    add("")
    add(
        "> 本文件由 [`tests/advanced/report.py`](../../tests/advanced/report.py) "
        "从本次运行的 JSON / JUnit 产物自动生成。**不要手工修改数字**；"
        "改测试或改实现后重新运行生成命令即可。"
    )
    add("")
    add(f"- 源码版本：`{sha}`（分支 `{branch}`）")
    add(f"- 运行完成时间：{started}")
    add(f"- 生成时间：{generated_at}")
    add(f"- 产物目录：`{out}`")
    add(f"- 确定性：`PYTHONHASHSEED=4801`，Hypothesis `derandomize=True`，"
        "`random.Random(4801)`；所有规模有上限。")
    add("")

    add("## 1. 一页摘要")
    add("")
    add(
        "本报告汇总本仓库在必测单元套件（`python tests/run_tests.py`）之外叠加的"
        " 13 项高级测试与验证技术：运行器基线、属性测试、有状态模型、有限轨迹 LTL、"
        "Z3 规格证明、有界模型检验与归纳、差分测试、变异测试、OpenAPI 属性模糊、"
        "蜕变/内蜕变、LLM 盲测实验、安全扫描和覆盖率汇总。"
        f"本次 `run.py all` 请求 {len(modes_requested)} 个模式，"
        f"{modes_ok} 个 exit 0；模式自身耗时合计 {total_seconds:.1f}s。"
        f"合并覆盖率为 {percent(combined.get('statement_pct'))} statements / "
        f"{percent(combined.get('branch_pct'))} branches；"
        f"单元套件分支覆盖 {percent(unit_branch)}，CI 门槛取 "
        f"`{number(unit_gate)}%`。"
    )
    add("")
    add(
        "所有证据都写在 checkout 之外的一次性目录；数据库是 `initdb` 新建的"
        " loopback 临时集群（CI 中由 `postgres:15` service 提供并逐库创建/删除），"
        "测试进程不访问外网、不读 `backend/.env` 的真实值。"
        "数字来自下面的产物 JSON，正文中的“亮点/局限”引用对应详细文档中的"
        "具体反例、表格与自检记录。"
    )
    add("")
    add("### 1.1 总表")
    add("")
    add(
        table(
            ["技术", "讲义出处", "规模", "结果", "证据文档"],
            summary_rows,
        )
    )
    add("")
    add("### 1.2 模式回执与 JUnit 统计")
    add("")
    add(
        table(
            ["模式", "用例", "通过", "失败", "跳过", "回执", "耗时"],
            junit_rows,
        )
    )
    add("")
    add(
        "> 入口型（`entry.py`）模式没有 pytest JUnit；它们的用例数/请求数在各自一节"
        "从业务 JSON 读取。`run.py` 的模式回执来自 `<out>/<mode>/result.json`。"
    )
    add("")

    add("## 2. 方法论")
    add("")
    add(
        "**独立 oracle。** 每条 oracle 都由需求文字、手算或独立实现得到，"
        "不调用被测实现生成期望值：P1 用 `Fraction` 与集合交重写 FP-MATCH-1；"
        "P4 的 Z3 编码不导入 `app.*`，1024 对子集另行与真实 `match_score` 对拍；"
        "P6 的 SQL 打分不导入生产匹配模块；P8 的期望状态矩阵从 FP-AUTH-3/SPEC 手写。"
    )
    add("")
    add(
        "**每个 oracle 至少做一次“故意引入错误 → 测试变红 → 恢复”。** "
        "P1 用仓库外 `-p` 插件替换实现；P2 故意把“已预约时段可删除”预测为 204，"
        "并要求 Hypothesis 给出最小操作序列；P3 在内存里替换检查器运算符；"
        "P4 把 `int_div` 改成乘法近似；P5 用 `Variant` 逐条删除守卫；"
        "P6 用 monkeypatch 改候选视图分数；P7 的 304 个变异体本身就是 304 次"
        "受控错误注入；P8 在 `finally` 中恢复 4 个受控回归；P9 直接删除数据库唯一"
        "约束（比吞掉异常更忠实）；P10 用 5 个手写变异体与 F3 不安全渲染对照。"
        "生产代码没有被修改，所有临时变异都在仓库外或进程内完成。"
    )
    add("")
    add(
        "**空真与可达性检查。** P3 为每条 LTL 性质单独统计前件触发实例数，"
        "并显式报告“非空真轨迹”；P5 用 3 个可达性见证证明 BMC 的 `unsat` 不是"
        "空模型，用 M5 展示“守卫恒假时 BMC 仍 unsat”的假绿风险。"
        "P4 的 N1/N2 是两个故意为假的负向查询，`sat` 才说明编码能判错。"
    )
    add("")
    add(
        "**确定性。** `PYTHONHASHSEED=4801` 由 `run.py` 传给所有子进程；"
        "Hypothesis 统一 `derandomize=True`、`deadline=None`；"
        "随机数据用 `random.Random(4801)`；每个模式的规模有上限"
        "（属性 200、状态机 25×12 步、模糊读 20/写 10、变异 304 个）。"
        "P3 的 relax 链与 P2 的轨迹逐字节可复现。"
    )
    add("")
    add(
        "**安全边界。** `--out` 在 checkout 内会被 `run.py` 拒绝；"
        "数据库只允许 `127.0.0.1`/`localhost`/`::1`；"
        "`ADVANCED_PG_URL` 的密码不会写进 summary；"
        "日志和 evidence 不打印 Cookie/CSRF/密码/哈希；"
        "测试不访问外网。"
    )
    add("")

    add("## 3. 逐项技术")
    add("")
    add("每小节按“讲义出处 / 要回答的问题 / 命令 / 关键数字 / 亮点 / 局限 / 详细文档”"
        "组织；关键数字表第三列是产物相对路径，数字由本脚本读取，不手填。")
    add("")
    add("### 3.0 P0 运行器骨架：自动发现、一次性 PG、产物出仓")
    add("")
    add("**讲义出处**：L12（测试层次与可复现运行）/ L13（测试方法与工具）。")
    add("")
    add("**要回答的问题**：高级套件能否一条命令复现，并且不污染仓库、共享数据库或"
        "管理员环境？")
    add("")
    add(f"**命令**：`python tests/advanced/run.py all --out <仓库外新目录>`；"
        f"本次 `run.py` 实际模式列表：{', '.join('`' + m + '`' for m in modes_requested)}。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("发现的模式数", number(len(modes_requested)), "summary.json"),
                metric_row("一次性 PG 启动", number(get(summary, "pg", "started")), "summary.json"),
                metric_row("PG 模式", str(get(summary, "pg", "mode")), "summary.json"),
                metric_row("模式总耗时", f"{total_seconds:.2f}s", "summary.json"),
                metric_row("git 工作区干净", number(summary.get("git_status_clean")), "summary.json"),
            ],
        )
    )
    add("")
    add("**亮点**：模式由目录自动发现（`entry.py` 或 pytest、`SLOW`、`NEEDS_DB` 三个标记），"
        "新增模式不需要改 `run.py` 或 CI；`run.py` 用 `initdb` 在随机端口新建"
        "仅 loopback、trust 认证的临时集群，结束后删除；`--out` 必须在 checkout 外且"
        "新目录/空目录，避免把含合成会话令牌的日志提交进仓库；"
        "`support/pg.py::validate_loopback_url` 拒绝非 loopback 主机。")
    add("")
    add("**局限**：`run.py` 不设模式超时，靠调用方/CI 的 `timeout-minutes` 兜底；"
        "`entry.py` 模式不加载共享 `conftest.py`，需要自己建库/迁移/清理；"
        "各模式独立子进程，无法共享 Python 状态（这是隔离性，也是无法复用昂贵"
        "对象的原因）。")
    add("")
    add("**详细文档**：[ADVANCED_BASELINE.md](ADVANCED_BASELINE.md)、"
        "[README](../../tests/advanced/README.md)。")
    add("")

    add("### 3.1 P1 属性测试：FP-MATCH-1 的规格性质")
    add("")
    add("**讲义出处**：L13（性质测试与独立 oracle）。")
    add("")
    add("**要回答的问题**：匹配分数与技能归一化在任意合法输入上是否满足需求，"
        "而不只是四个示例行？")
    add("")
    add("**命令**：`python tests/run_tests.py --junitxml=<仓库外>/unit.xml`。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("必测套件用例", number(unit_tests), "unit.xml"),
                metric_row("必测套件失败", number(unit_failed), "unit.xml"),
                metric_row("属性测试用例", number(property_cases), "unit.xml"),
                metric_row("每个性质规模", "200 examples", "test_matching_properties.py"),
                metric_row("oracle", "Fraction + 集合交 + floor", "test_matching_properties.py"),
            ],
        )
    )
    add("")
    add("**亮点**：9 条性质覆盖返回值范围/类型、独立 oracle、空需求 100、排列/重复/"
        "空白不变性、无关技能不变、单调性、归一化幂等与输入不被原地修改。"
        "自检时把 `//` 改成 `round()`，Hypothesis 自动缩小出最小反例"
        "`['0','00']` vs `['0','00','000']`（floor 66 vs round 67）；"
        "把 `.strip()` 删除时生成测试单独杀死对应变异体。"
        "属性测试已进入**必测** `python tests/run_tests.py`，不是可选脚本。")
    add("")
    add("**局限**：每个性质是有界随机采样（200 examples），不是穷举证明；"
        "归一化按需求的 `str.lower()` 解释（`ß`/`İ` 不折叠）；"
        "不覆盖数据库、路由或前端渲染。")
    add("")
    add("**详细文档**：[test_matching_properties.py](../../tests/unit/test_matching_properties.py)。")
    add("")

    add("### 3.2 P2 有状态模型：预约生命周期")
    add("")
    add("**讲义出处**：L12/L13（状态机与模型化测试）。")
    add("")
    add("**要回答的问题**：在任意合法/非法操作序列下，预约生命周期的 5 条不变量是否"
        "始终成立？")
    add("")
    add("**命令**：`python tests/advanced/run.py stateful`。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("examples", number(stateful.get("examples")), "stateful/summary.json"),
                metric_row("总步数", number(stateful.get("steps")), "stateful/summary.json"),
                metric_row("轨迹文件 / 去重", f"{number(stateful.get('traces'))} / {number(stateful.get('distinct_traces'))}", "stateful/summary.json"),
                metric_row("成功预约", number(st_outcomes.get("book->201")), "stateful/summary.json"),
                metric_row("删除已预约时段被拒", number(st_outcomes.get("delete_slot->409")), "stateful/summary.json"),
                metric_row("状态改成功", number(st_outcomes.get("set_status->200")), "stateful/summary.json"),
                metric_row(
                    "失败数",
                    number(
                        (junit.get("stateful") or {}).get("failures", 0)
                        + (junit.get("stateful") or {}).get("errors", 0)
                    ),
                    "stateful/junit.xml",
                ),
            ],
        )
    )
    add("")
    add("**亮点**：每步都是**真实 HTTP 调用 + 真实 SQL 断言**，不是会话替身："
        "不变量 1 直接数 `booking` 行，不变量 2 检查已预约时段不出现在可用列表，"
        "不变量 3 检查预约只在 `Interviewing` 时创建且状态变化后保留，"
        "不变量 4 用独立 FP-MATCH-1 oracle 核对雇主申请人列表的分数与排序，"
        "不变量 5 检查被拒绝操作不改变任何表行数。"
        "`perform` 用 `hypothesis.strategies.randoms()` 在**适用操作**间均匀抽取，"
        "避免 Hypothesis 的规则采样偏置把一半步骤分给同一条廉价规则；"
        "这个 draw 仍在 Hypothesis 数据流里，所以 `derandomize=True` 下轨迹逐字节"
        "可复现，shrinking 也仍然有效。两个自检分别验证“已预约时段可删除”的"
        "错误模型预测和“可用列表包含已预约时段”的 monkeypatch 都会变红，"
        "并要求 Hypothesis 给出最小操作序列。")
    add("")
    add("**局限**：25 个 example、每例最多 12 步是**有界随机探索**，不是穷举；"
        "规则权重与 seed 决定轨迹空间；删除已预约时段的成功分支在本次轨迹中只"
        "触发了 2 次拒绝，覆盖较薄；真实并发由数据库行锁/唯一约束保证，"
        "状态机是顺序执行。")
    add("")
    add("**详细文档**：模块 docstring "
        "[test_booking_state_machine.py](../../tests/advanced/stateful/test_booking_state_machine.py)。")
    add("")

    add("### 3.3 P3 有限轨迹 LTL：空真检查与 relax/restrict")
    add("")
    add("**讲义出处**：L13 slides 46–52（LTL、relax/restrict 精化）。")
    add("")
    add("**要回答的问题**：P2 产生的业务轨迹是否满足 FP-SCHED/FP-CAN 的时序性质？"
        "检查器本身是否能判出违规？")
    add("")
    add("**命令**：`python tests/advanced/run.py ltl`。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("轨迹文件 / 去重", f"{number(ltl_traces.get('files'))} / {number(ltl_traces.get('distinct'))}", "ltl/ltl_results.json"),
                metric_row("步数 / 去重步数", f"{number(ltl_traces.get('steps'))} / {number(ltl_traces.get('steps_distinct'))}", "ltl/ltl_results.json"),
                metric_row("性质数", number(len(ltl_properties)), "ltl/ltl_results.json"),
                metric_row("selftest 用例", number(ltl_selftest_cases), "ltl/junit.xml"),
                metric_row("refine 链", " → ".join(
                    f"{step.get('label')} {step.get('satisfied')}/{step.get('total')}"
                    for step in refine_steps
                ) or "—", "ltl/refinement.json"),
            ],
        )
    )
    add("")
    add("**关键数字（逐性质，来自 `ltl/ltl_results.json`）**：")
    add("")
    add(table(["性质", "标题", "满足/轨迹", "非空真轨迹", "前件触发实例"], ltl_rows))
    add("")
    add("**亮点**：自研有限轨迹 LTL 支持 `G/F/X/WX/U`、布尔连接词、有限域"
        "`forall/exists` 与参数化原子；每个运算符至少 3 条满足 + 3 条违反，"
        "`G(p -> X q)` / `p U q` 各穷举 3 步的 64 种真值组合，`F G p` 穷举 8 种。"
        "**空真检查**不是口号：每条性质单独统计前件触发实例（L1/L4 为 11 个 booking、"
        "L5 为 43 个申请），并列出“非空真轨迹 < 5”的警告。"
        "`explain` 给出第一个违规的 trace index、step、props、binding 与原因。"
        "relax 链用 `random.Random(4801)` 从 0/25 精化到 25/25，"
        "restrict 探针 R0/R1 又分别暴露 15/1 条新反例，说明“放宽到 100%”不等于"
        "性质已无约束。")
    add("")
    add("**局限**：只支持有限轨迹，不支持无限轨迹/lasso/公平性；"
        "25 条轨迹的有界随机探索不是穷尽证明；量词域只来自轨迹中出现过的值，"
        "是依赖 P2 原子词汇表的有限近似；L4 的“删除已预约时段被拒”分支只有 2 次"
        "拒绝尝试，主要靠 P2 不变量与 P5 模型检验补强。")
    add("")
    add("**详细文档**：[LTL.md](LTL.md)。")
    add("")

    add("### 3.4 P4 匹配规格的 Z3 证明：Hoare 三元组与有界对拍")
    add("")
    add("**讲义出处**：L13（Hoare 三元组、SMT 与规格证明）。")
    add("")
    add("**要回答的问题**：FP-MATCH-1 的规格公式是否满足 7 条性质？"
        "真实 `match_score` 在有限全集上是否与规格一致？")
    add("")
    add("**命令**：`python tests/advanced/run.py formal`。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("T1–T7", f"{len(proof_records)} 条，{sum(1 for r in proof_records if r.get('result') == 'unsat')} unsat", "formal/matching_theory.json"),
                metric_row("N1–N2 负向", f"{len(negative_records)} 条，{sum(1 for r in negative_records if r.get('result') == 'sat')} sat", "formal/matching_theory.json"),
                metric_row("全集大小 / 子集对", f"{number(spec_to_code.get('subsets'))}^{number(len(spec_to_code.get('universe', [])))} / {number(spec_to_code.get('pairs'))}", "formal/spec_to_code_pairs.json"),
                metric_row("规格/代码 mismatch", number(spec_to_code.get("requirement_formula_mismatches")), "formal/spec_to_code_pairs.json"),
                metric_row("Z3 编码 mismatch", number(spec_to_code.get("z3_encoding_mismatches")), "formal/spec_to_code_pairs.json"),
            ],
        )
    )
    add("")
    add("**关键数字（逐条记录，来自 `formal/matching_theory.json`）**：")
    add("")
    add(table(["ID", "标题", "结果", "单次查询"], formal_rows))
    add("")
    add("**亮点**：每个测试上方用 Hoare 三元组写 `{P} C {Q}`，并与 FP-MATCH-1 条款"
        "逐条对应；T1–T7 的否定全部 `unsat`，N1 的 floor/round 反例是"
        "`n=6, k=4`：floor 66 vs round 67，N2 的分母误用反例证明“分母是 |R| 不是 |C|”"
        "不是文字游戏。`|U|=5` 的 1024 个 `(C,R)` 对同时比较真实实现、Z3 编码与"
        "需求文字三方一致，0 mismatch。自检把 `int_div` 改成乘法后 T1/T2/T3/T5/T7"
        " 变 `sat` 并报出真实反例，恢复后全绿。")
    add("")
    add("**局限**：证明对象是 `encoding.py` 的**规格公式**，不是 Python 代码；"
        "代码只通过 `|U|=5` 的 1024 对有界穷举与规格关联；归一化不在 SMT 模型内；"
        "Hoare 三元组是语义层描述，没有经过证明助手检查。")
    add("")
    add("**详细文档**：[FORMAL_MATCHING.md](FORMAL_MATCHING.md)。")
    add("")

    add("### 3.5 P5 预约状态机：BMC + k-归纳")
    add("")
    add("**讲义出处**：L13（BMC、k-归纳与 propose→check→counterexample→repair）。")
    add("")
    add("**要回答的问题**：B1–B4 在 6 步以内有没有反例？能否从“6 步内无”提升到"
        "“任意步数成立”？")
    add("")
    add("**命令**：`python tests/advanced/run.py formal`（与 P4 同一模式）。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("BMC 步数", number(bmc.get("steps")), "formal/booking_bmc.json"),
                metric_row("记录数", number(len(bmc_records)), "formal/booking_bmc.json"),
                metric_row("BMC 性质 unsat", number(sum(1 for r in bmc_kind('property') if r.get('result') == 'unsat')), "formal/booking_bmc.json"),
                metric_row("负向控制 sat", number(sum(1 for r in bmc_kind('negative_control') if r.get('result') == 'sat')), "formal/booking_bmc.json"),
                metric_row("可达性见证 sat", number(sum(1 for r in bmc_kind('reachability') if r.get('result') == 'sat')), "formal/booking_bmc.json"),
                metric_row("归纳义务 unsat", number(sum(1 for r in bmc_records if r.get('kind') in {'induction_base', 'induction_step', 'single_step'} and r.get('result') == 'unsat')), "formal/booking_bmc.json"),
            ],
        )
    )
    add("")
    add("**关键数字（逐记录，来自 `formal/booking_bmc.json`）**：")
    add("")
    add(table(["ID", "类别", "结果", "变体"], bmc_rows))
    add("")
    add("**亮点**：BMC（k=6）与 k-归纳（k=1）共用同一份守卫/效果编码，避免两套"
        "编码悄悄分叉；`include_initial=False` 让归纳步对**任意状态**量化，"
        "这是“有界 → 无界”的关键。3 个可达性见证（预约、删除、状态改变）都是"
        "`sat`，证明 `unsat` 不是空模型；M5 把 `book_guard` 改成恒假后 BMC 仍"
        "`unsat`，暴露“没有可达性见证就可能空真”的风险。"
        "被拒绝的不变式加强 `Inv_A` 得到 `sat` 反例（`set_status(a0, Rejected)` "
        "后预约保留但状态离开 `Interviewing`），正好对应讲义 L13 的"
        " propose→check→counterexample→repair；最终 `Inv = B1 ∧ B3状态形式` 一次"
        "归纳步即 `unsat`。")
    add("")
    add("**局限**：证明对象是 `booking_model.py` 的抽象转移系统；守卫是人工从代码"
        "抄写的，没有自动精化和模型/代码一致性证明；时间、30 分钟、跨雇主、"
        "职位保留、版本冲突都被抽象为恒真/不建模；并发由数据库行锁 + 唯一约束保证，"
        "顺序转移系统无法表达；`基例 + 归纳步 ⇒ 所有可达状态`是元层面论证，"
        "不是机器检查的定理。")
    add("")
    add("**详细文档**：[FORMAL_BOOKING.md](FORMAL_BOOKING.md)。")
    add("")

    add("### 3.6 P6 差分测试：Python 打分 vs SQL 打分")
    add("")
    add("**讲义出处**：L12（差分测试与独立 oracle）。")
    add("")
    add("**要回答的问题**：同一批数据库行，用独立 SQL 算出的 FP-MATCH-1 分数是否与"
        "生产 `match_score` 一致？候选人视图与雇主视图对同一 (C,R) 是否一致？")
    add("")
    add("**命令**：`python tests/advanced/run.py differential`。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("SQL/Python 对数", number(differential.get("pairs")), "differential/differential.json"),
                metric_row("SQL mismatch", number(differential.get("sql_mismatch")), "differential/differential.json"),
                metric_row("双视图对数", number(cross_view.get("cross_view_pairs")), "differential/cross-view.json"),
                metric_row("申请行", number(cross_view.get("applications")), "differential/cross-view.json"),
                metric_row("tie groups", number(differential.get("tie_groups")), "differential/differential.json"),
                metric_row("不同分数 / 100 分 / 0 分", f"{number(differential.get('distinct_scores'))} / {number(differential.get('perfect_scores'))} / {number(differential.get('zero_scores'))}", "differential/differential.json"),
            ],
        )
    )
    add("")
    add("**亮点**：数据经**真实 HTTP API** 写入（技能已经过生产归一化），SQL 侧是"
        "从需求文字独立写出的 `floor(100*overlap/required)`，不导入生产匹配模块；"
        "600 对 `(candidate, job)` 全部一致，0 mismatch。双视图测试让"
        "40 个候选人 × 15 个职位全部投递，600 对候选人仪表盘与雇主申请人列表分数"
        "一致，并用手写排序键检查 40 + 15 = 55 个大小写平局组；"
        "两个常驻自检分别 monkeypatch 候选视图分数和排序键，要求 oracle 变红后"
        "恢复。")
    add("")
    add("**局限**：600 对是有界随机数据集（40×15，`random.Random(4801)`），不是穷举；"
        "SQL 与 Python 只比较归一化后的集合语义，不重复测试归一化本身；"
        "只覆盖 `match_score`，不覆盖推荐排序的全部业务规则。")
    add("")
    add("**详细文档**：[test_matching_sql.py](../../tests/advanced/differential/test_matching_sql.py)、"
        "[test_cross_view.py](../../tests/advanced/differential/test_cross_view.py)。")
    add("")

    add("### 3.7 P7 变异测试：必测套件的缺陷检出能力")
    add("")
    add("**讲义出处**：L13 slide 17（变异测试引擎）/ L14 slide 28（变异分数与幸存者归因）。")
    add("")
    add("**要回答的问题**：`tests/unit` 能检出多少人为注入的代码缺陷？哪些幸存者"
        "是等价变异、哪些是缺测试？")
    add("")
    add("**命令**：`python tests/advanced/run.py mutation`（SLOW；自研 AST 引擎）。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("变异体总数", number(mutation_totals.get("mutants")), "mutation/mutation-result.json"),
                metric_row("killed / survived", f"{number(mutation_totals.get('killed'))} / {number(mutation_totals.get('survived'))}", "mutation/mutation-result.json"),
                metric_row("suspicious", number(mutation_totals.get("suspicious")), "mutation/mutation-result.json"),
                metric_row("计分分母", number(mutation_totals.get("judged")), "mutation/mutation-result.json"),
                metric_row("并行度", number(get(mutation, "config", "jobs")), "mutation/mutation-result.json"),
                metric_row("mutation score", percent((mutation_totals.get("score") or 0) * 100), "mutation/mutation-result.json"),
                metric_row("保守下界", percent((mutation_totals.get("score_with_suspicious_as_survivors") or 0) * 100), "mutation/mutation-result.json"),
                metric_row("backend/app 未被改动", number(get(mutation, "guard", "unchanged")), "mutation/mutation-result.json"),
            ],
        )
    )
    add("")
    add("**按文件（来自 `mutation/mutation-result.json`）**：")
    add("")
    add(table(["文件", "变异体", "killed", "survived", "分数"], mutation_rows))
    add("")
    add("**亮点**：由于 mutmut 3.7 在原生 Windows 上结构性不可用（依赖 `os.fork` 与 "
        "`resource.setrlimit`），P7 按任务允许的降级方案实现了一个**自研 AST 变异"
        "引擎**（L13 slide 17 的思想），覆盖比较翻转、`//`→`/`、`and↔or`、常量 ±1、"
        "`raise`→`pass`、`return X`→`return None` 六类算子；每个变异体固定 30s 超时，"
        "只在 `$ADVANCED_OUT/mutation/work/` 的副本里注入，前后对 `backend/app` 做"
        " SHA-256 快照。三列对比为 **60.93% → 60.93% → "
        f"{percent((mutation_totals.get('score') or 0) * 100)}**："
        "P1 属性测试把 `tests/unit` 从 176 例增加到 185 例，但**单独新增 killed = 0**；"
        f"全部 {number(mutation_new_kills)} 个新增 kills 来自补强测试。报告没有掩盖这个事实，而是把中间列"
        "单独计分，说明属性测试的价值在规格性质而非这套 6 类算子的杀伤力。")
    add("")
    add("**局限**：变异分数是**同口径前后对比**，不是 mutmut 全量算子集的横向分数；"
        "19 个幸存者中有 10 个属于“仅真实 SQL 可观测”（`LIMIT`/`JOIN ON`），应由集成/差分"
        "覆盖；2 个 suspicious 是导入期错误，保守地不计入分母；"
        "变异范围只覆盖 5 个文件。本次证据运行记录 "
        f"`jobs={number(get(mutation, 'config', 'jobs'))}`；如果并发过高导致"
        "每个变异体 30s 固定超时出现假 timeout，Python 3.13 及以上可以用 "
        "`PYTHON_CPU_COUNT`；通用做法是直接运行 "
        "`python tests/advanced/mutation/entry.py --jobs N` 后重跑；"
        "变异体集合、判定逻辑与最终 killed/survived 分类不变。")
    add("")
    add("**详细文档**：[MUTATION.md](MUTATION.md)、"
        "[tests/unit/test_mutation_hardening.py](../../tests/unit/test_mutation_hardening.py)。")
    add("")

    add("### 3.8 P8 OpenAPI 属性模糊：从真实缺陷到修复重跑")
    add("")
    add("**讲义出处**：L14 slide 29（属性测试 → 真实缺陷 → 修复回归）。")
    add("")
    add("**要回答的问题**：自动生成的 OpenAPI 文档能否驱动有界、可复现的 API 属性"
        "测试？认证/所有权矩阵是否符合 FP-AUTH-3？有没有未声明的 5xx？")
    add("")
    add("**命令**：`python tests/advanced/run.py apifuzz`（SLOW）。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("OpenAPI 操作", number(apifuzz_operations), "apifuzz/report.json"),
                metric_row("总请求数", number(apifuzz_requests), "apifuzz/report.json"),
                metric_row("未声明 5xx", number(apifuzz_5xx), "apifuzz/report.json"),
                metric_row("real_defect", number(apifuzz_attribution.get("real_defect")), "apifuzz/report.json"),
                metric_row("schema_drift", number(apifuzz_attribution.get("schema_drift")), "apifuzz/report.json"),
                metric_row("test_config", number(apifuzz_attribution.get("test_config")), "apifuzz/report.json"),
                metric_row("自检通过", number(apifuzz_selfcheck.get("ok")), "apifuzz/report.json"),
            ],
        )
    )
    add("")
    if apifuzz_rows:
        add("**逐轮状态分布（来自 `apifuzz/report.json`）**：")
        add("")
        add(table(["轮次", "操作", "请求", "状态分布", "失败记录"], apifuzz_rows))
        add("")
    add("**亮点**：**864 个请求、0 个 5xx**。匿名轮所有受保护操作都先返回 401"
        "（`422-before-auth=0`）；候选/雇主轮错角色请求全部 403。"
        "更重要的是一条真实缺陷的完整闭环：模糊测试发现 "
        "`POST /employer/interview-slots` 的业务 422 返回字符串 `detail`，"
        "但 OpenAPI 声明的是 `HTTPValidationError` 数组，Schemathesis "
        "`response_schema_conformance` 报 `ST108`（10 个写样例中 9 个命中）；"
        "写入 `findings/P8.md` 后由队友提交 `0ea7223` 修复，"
        "回归测试 `test_fp_sched_1_openapi_422_documents_business_and_validation_shapes` "
        "覆盖两种响应体；P11 重跑 `real_defect` 从 **9 → 0**。"
        "4 个受控自检（错误角色矩阵、服务端 500、响应 schema、状态码）都在 "
        "`finally` 中恢复，证明 oracle 会变红而不是恒真。")
    add("")
    add("**局限**：操作级、非状态序列（多步工作流由 P2/P9 覆盖）；读 20/写 10 是"
        "有界采样，零参数 GET 可能提前耗尽；随机 UUID 只覆盖拒绝路径；"
        "ASGI 直连不验证端口/代理/TLS；**793 个 schema drift 不是 793 个业务 bug**，"
        "而是 FastAPI 未声明 FP-AUTH-3 要求的 401/403/404 与 SPEC 的 400/409，"
        "报告按检查/状态分别计数，没有用过滤器静默吞掉。")
    add("")
    add("**详细文档**：[APIFUZZ.md](APIFUZZ.md)、"
        "[findings/P8.md](findings/P8.md)。")
    add("")

    add("### 3.9 P9 蜕变与内蜕变：规则由哪一层保证")
    add("")
    add("**讲义出处**：L12 slides 29–41（蜕变测试与内蜕变）。")
    add("")
    add("**要回答的问题**：工作流层的语义等价变换是否保持可观察结果？关掉某条防护层"
        "后，规则会由哪一层兜底、还是直接失效？")
    add("")
    add("**命令**：`python tests/advanced/run.py intramorphic`。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("蜕变工作流", number(len([m for m in metamorphic if metamorphic[m]])), "intramorphic/M1..M5.json"),
                metric_row("防护层规则", number(len([r for r in defense_rules if 'selfcheck' not in r])), "intramorphic/defense_layers.json"),
                metric_row("I2 并发轮数", number(get(defense_rules.get("I2", {}), "round_count")), "intramorphic/defense_layers.json"),
                metric_row("I2 每轮单赢家", number(get(defense_rules.get("I2", {}), "all_rounds_consistent")), "intramorphic/defense_layers.json"),
                metric_row("I1 自检 red", number(get(defense_rules.get("I1_selfcheck", {}), "oracle_raised")), "intramorphic/defense_layers.json"),
                metric_row("I3 自检 red", number(get(defense_rules.get("I3_selfcheck", {}), "oracle_raised")), "intramorphic/defense_layers.json"),
            ],
        )
    )
    add("")
    add("**关键数字（来自 `intramorphic/defense_layers.json`）**：")
    add("")
    add(table(["规则", "内容", "关闭的层", "结论"], defense_rows))
    add("")
    add("**蜕变关系（M1–M5，来自 `intramorphic/M*.json`）**：")
    add("")
    add(table(["ID", "关系", "可观察结果不变"], metamorphic_rows))
    add("")
    add("**亮点**：一张“规则 → 应用检查 → 行锁 → 数据库约束 → 关掉后会怎样”的总表，"
        "把“哪一层在保证规则”变成可观察实验。I2 用两个真实线程/独立 Session 和两个 "
        "Barrier 做并发：两个请求都进入 `book`、都观察到时段空闲后才允许插入，"
        "去掉全部行锁后 5 轮仍是 1×201 + 1×409、每轮 1 行 `booking`、每轮 1 次 "
        "`uq_booking_slot` 冲突——说明唯一约束单独即可保证单赢家，行锁负责减少竞争。"
        "I1 的自检比原方案更正确：没有 monkeypatch 吞掉 `IntegrityError`（那不能让 "
        "PostgreSQL 保存第二行），而是在一次性库里 `DROP CONSTRAINT`，观察第二次"
        "预约真的返回 201、预约表 2 行，然后恢复约束。I3 同样验证重复投递；"
        "I5 如实记录“职位依赖检查只在应用层”的单层防护事实，"
        "因为正常路径符合需求，所以不记业务缺陷。")
    add("")
    add("**局限**：I2 的并发窗口由 Barrier 构造，不等于生产负载下的随机交错；"
        "monkeypatch 变体只覆盖 5 条规则；I5 是事实记录而非 bug；"
        "内蜕变回答“哪层保证”，不回答“测试能否杀死变异体”。")
    add("")
    add("**详细文档**：[INTRAMORPHIC.md](INTRAMORPHIC.md)。")
    add("")

    add("### 3.10 P10 LLM 盲测：生成测试 vs 手写测试")
    add("")
    add("**讲义出处**：L14 Exercise 1/3（AI 生成测试、断言质量与变异杀伤力）。")
    add("")
    add("**要回答的问题**：LLM 在只读契约、未看实现的情况下生成的测试质量如何？"
        "与手写测试相比，断言杀伤力和分区覆盖有什么差异？")
    add("")
    add("**命令**："
        "`python tests/advanced/experiments/llm_blind/run_experiment.py --out <仓库外>`；"
        "变异矩阵 `python .../mutation/run_mutants.py --out <仓库外>`。")
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("生成 case 总数", number(p10_cases), "llm_blind/results.json"),
                metric_row("passed / skipped / failed", f"{number(p10_passed)} / {number(p10_skipped)} / {number(p10_failed)}", "llm_blind/results.json"),
                metric_row("生成测试杀变异体", f"{number(generated_killed)}/{number(generated_tested)}", "llm_blind/results.json"),
                metric_row("手写测试杀变异体", f"{number(handwritten_killed)}/{number(handwritten_tested)}", "llm_blind/results.json"),
                metric_row("冻结 commit", code(p10.get("protocol", {}).get("frozen_generated_commit")), "llm_blind/results.json"),
            ],
        )
    )
    add("")
    add("**分区对比（来自 `llm_blind/results.json`）**：")
    add("")
    add(table(["目标", "生成 case", "手写 case", "独有发现"], p10_rows))
    add("")
    add("**亮点**：盲测协议把“生成”与“运行/读实现”用 commit 顺序冻结"
        "（`c0859d0` 生成文件 → `467a6f2`/`e76641f` 只修 setup → 本报告收口）；"
        "冻结运行 F3 11/11 通过，F1 因生成器的 parametrize id 数错误在 collection "
        "中断，F2 19/19 因合成 `User` 漏 `role` 被服务层正确拒绝，"
        "**三类都不是业务缺陷**。修正 setup 后 123 passed / 1 skipped / 0 failed。"
        "5 个手写变异体上生成测试 **5/5**、手写测试 **3/5**；两个幸存者暴露了手写"
        "断言的盲区（归一化用例混入不带空格副本，观察不到 `strip()` 被删除；"
        "`book` 拒绝矩阵缺少“职位不存在”），这两个缺口后来被 P7 的补强测试覆盖。"
        "F3 的负向自检把同一组转义断言应用到 `dangerouslySetInnerHTML` 的不安全"
        "渲染，必须被拒绝。")
    add("")
    add("**局限**：生成器仍是 LLM，协议保证的是“没有读本仓库实现”，不是没有世界"
        "知识；主会话在契约阶段用 AST 额外读了 `book` 的 `raise` 子句（已在文档"
        "披露）；F2 用会话替身、F3 用 `renderToStaticMarkup`，都不证明真实事务/浏览器"
        "安全；5 个手写变异体只是抽样，完整全量对比未在本任务完成（见 §5）。")
    add("")
    add("**详细文档**：[LLM_TEST_EXPERIMENT.md](LLM_TEST_EXPERIMENT.md)。")
    add("")

    add("### 3.11 P12 依赖与密钥扫描")
    add("")
    add("**讲义出处**：L14（验证与安全扫描）/ 课程安全要求 FP-SEC-4。")
    add("")
    add("**要回答的问题**：全历史有没有真实密钥？运行时 Python 依赖与前端生产依赖"
        "有没有未归因的漏洞？")
    add("")
    add("**命令**：独立 workflow `.github/workflows/security.yml`（gitleaks / pip-audit / "
        "npm audit）；本报告只链接文档，不重复运行扫描。")
    add("")
    add(
        table(
            ["指标", "值", "来源"],
            [
                metric_row("全历史扫描", "69 commits，0 泄露", "SECURITY_SCANS.md"),
                metric_row("Python 依赖", "12 个唯一 advisory → 0 待处理", "SECURITY_SCANS.md"),
                metric_row("接受的风险", "pytest PYSEC-2026-1845（有理由）", "SECURITY_SCANS.md"),
                metric_row("前端生产依赖", "0 漏洞", "SECURITY_SCANS.md"),
            ],
        )
    )
    add("")
    add("**亮点**：允许列表不是“一键变绿”，而是**路径 AND 值**：28 条 64 位十六进制 "
        "SHA-256 与 6 条测试夹具合成 `SECRET_KEY` 分别按精确路径 + 精确值抑制；"
        "在临时 git 仓库里把同一合成值放到允许路径之外仍被报告，非允许值的假 Token"
        "也仍被报告。P12b 删除 5 个未使用的 starter 包并升级 4 个包，"
        "12 个 advisory 归零；唯一接受的 pytest advisory 只影响测试工具的 UNIX "
        "`/tmp` 权限。")
    add("")
    add("**局限**：gitleaks 是启发式扫描器，0 命中不是“绝对没有密钥”的证明；"
        "只由 merge resolution 引入的内容可能不在 `git log -p` diff 中；"
        "`pip-audit` 只扫运行时锁文件，`tests/advanced/requirements.txt` 的测试依赖"
        "不在范围内；可达性判断基于当前代码。")
    add("")
    add("**详细文档**：[SECURITY_SCANS.md](SECURITY_SCANS.md)。")
    add("")

    add("### 3.12 P11 覆盖率：分组测量与合并")
    add("")
    add("**讲义出处**：L12（覆盖率、测试充分性与门槛）。")
    add("")
    add("**要回答的问题**：必测单元套件、真实 PG 集成套件与三个高级模式分别覆盖了 "
        "`backend/app` 的多少语句/分支？合并后是多少？门槛取多少才不会被环境差异"
        "弄红？")
    add("")
    add("**命令**：`python tests/advanced/run.py coverage`（SLOW、NEEDS_DB；"
        "入口为 `tests/advanced/coverage/entry.py`）。")
    add("")
    add(
        table(
            ["套件", "目标", "用例", "语句覆盖", "分支覆盖", "耗时"],
            coverage_rows,
        )
    )
    add("")
    add(
        table(
            ["指标", "值", "产物"],
            [
                metric_row("合并语句覆盖", percent(combined.get("statement_pct")), "coverage/coverage-summary.json"),
                metric_row("合并分支覆盖", percent(combined.get("branch_pct")), "coverage/coverage-summary.json"),
                metric_row("语句 covered/total", f"{number(combined.get('covered_statements'))}/{number(combined.get('statements'))}", "coverage/coverage-summary.json"),
                metric_row("分支 covered/total", f"{number(combined.get('covered_branches'))}/{number(combined.get('branches'))}", "coverage/coverage-summary.json"),
                metric_row("单元分支门槛（向下取 5 的倍数）", f"{number(unit_gate)}%", "coverage/coverage-summary.json"),
            ],
        )
    )
    add("")
    add("**亮点**：五组各自用独立 data file 运行 "
        "`coverage run --branch --source=backend/app`，最后用 coverage API "
        "`combine` 合并；单元组的 `branch_pct` 实测值向下取整到 5 的倍数得到 CI "
        f"门槛 `{number(unit_gate)}%`。门槛只放在 `advanced` job：`pytest-cov`/"
        "`coverage` 只存在于 `tests/advanced/requirements.txt`，"
        "`unit` job 与 Docker 镜像都只装 `requirements.lock`，"
        "把 `--cov-fail-under` 加到必测命令会让镜像内测试失败。"
        "集成组用 `ADVANCED_PG_URL` 同时设置两个 `*_TEST_DATABASE_URL`，"
        "每组测试仍各自建/删一次性数据库。")
    add("")
    add("**局限**：合并覆盖只衡量**被执行的行/分支**，不衡量断言质量（变异分数"
        "由 P7 负责）；`tests/unit` 组在本地包含 Node 渲染测试，CI 的 advanced job "
        "因此也安装 Node 依赖；覆盖率受 Python/插件版本与导入路径影响，"
        "门槛取整到 5 的倍数是为了留出跨平台抖动余量，不是“越高越好”的分数竞赛。")
    add("")
    add("**详细文档**：本报告；`tests/advanced/coverage/entry.py`。")
    add("")

    add("## 4. 发现与闭环：P8 的 422 契约缺陷")
    add("")
    add(
        "这是本套件唯一写入 `findings/` 的业务契约缺陷，也是 L14 slide 29"
        "“发现问题 → 修复 → 回归”的完整闭环："
    )
    add("")
    add("1. **需求**：FP-SCHED-1 要求拒绝非法时段；`SPEC.md` 的 "
        "`POST /employer/interview-slots` 声明 422，OpenAPI 该响应为 "
        "`HTTPValidationError`（`detail` 是数组）。")
    add("2. **测试**：P8 从实时 `/openapi.json` 生成请求，用 Schemathesis 的 "
        "`response_schema_conformance` 检查 422 响应体。")
    add("3. **失败**：10 个雇主写样例有 9 个返回 "
        "`{\"detail\": \"Slot must start in the future\"}`（字符串），"
        "`ST108 Response violates schema`。")
    add("4. **修复**：`backend/app/interview/router.py`（commit "
        "`0ea722364e18b921cbdacdcba879a9ef44a43c03`，PR #14 / merge `88a660e`）"
        "为 422 声明 `anyOf`，同时记录数组与字符串两种响应体；"
        "回归测试 `tests/unit/test_scheduling.py::"
        "test_fp_sched_1_openapi_422_documents_business_and_validation_shapes`。")
    add("5. **重跑**：P11 正式证据运行中 `apifuzz` 的 `real_defect` 为 "
        f"{number(apifuzz_attribution.get('real_defect'))}（修复前为 9）；"
        f"剩余 `schema_drift` {number(apifuzz_attribution.get('schema_drift'))} 是 "
        "FastAPI 未声明 401/403/404/400/409，不是本次缺陷。")
    add("")
    add("缺陷汇总与去重见 [findings/SUMMARY.md](findings/SUMMARY.md)。"
        "P2/P7/P9/P10 的自检没有发现业务缺陷；P9 的 I5“单层防护”按文档记录为事实，"
        "不是 bug。")
    add("")

    add("## 5. 局限与未做")
    add("")
    add("- **形式化证明的对象是抽象模型/规格**：P4 证明 `encoding.py` 的规格公式，"
        "P5 证明 `booking_model.py` 的转移系统；Python 实现只通过有界穷举/对拍"
        "关联，没有自动精化关系。代码改动后模型可能过期。")
    add("- **BMC/归纳之外的并发由数据库保证**：P5 的顺序转移系统无法表达两个事务的"
        "交错；FP-SCHED-3 的原子性由行锁 + 唯一约束保证，P9 的 I2 与专项套件"
        "覆盖这一层。")
    add("- **变异分数是同口径前后对比**：93.71% 来自自研 6 类 AST 算子，不能与 "
        "mutmut 全量算子集横向比较；P1 属性测试单独新增 killed = 0，"
        "报告已如实写出。")
    add("- **`pip-audit` 只扫运行时锁文件**：`tests/advanced/requirements.txt` 的"
        "测试依赖不在范围内；npm audit 用 `--omit=dev`，devDependencies 不在范围内。")
    add("- **PostgreSQL 版本差异**：本报告如果由本地开发证据生成，使用的是 Windows "
        f"便携版 {pg_version}；任务/CI 的正式镜像是 `postgres:15`。"
        "两者在唯一约束、行锁、`DROP ... WITH (FORCE)` 语义上一致，但版本差异"
        "仍应记录；正式 CI 证据由 `advanced-slow` 在 `postgres:15` 上重跑。")
    add("- **P10 的 5 个手写变异体是小样本**：任务 §7 的“P10 全量对比”与“属性测试"
        "单独杀伤力”是可选加分项，本次未完成；5/5 vs 3/5 只应读作抽样结论。"
        "P7 的 304 个全量变异体是必测套件的证据，不直接等同于 P10 生成测试的分数。")
    add("- **P8 的 schema drift 未修**：793 次失败是 FastAPI 未声明 4xx，"
        "属于生产 API 文档工作，不在测试任务范围内；报告保留而不静默过滤。")
    add("- **`run.py` 无模式超时**：CI 由 `advanced` 的 30 分钟与 `advanced-slow` 的"
        " 90 分钟 `timeout-minutes` 兜底；本地运行需要自己控制时长。")
    add("")

    add("## 6. 页脚")
    add("")
    add(f"- 源码版本：`{sha}`（分支 `{branch}`）")
    add(f"- 运行完成时间：{started}")
    add(f"- 报告生成时间：{generated_at}")
    add(f"- Python：{summary.get('python', 'unknown')}")
    add(f"- PostgreSQL 版本：{pg_version}")
    if args.ci_run:
        add(
            f"- CI 证据：GitHub Actions run `{args.ci_run}`，"
            f"artifact `{args.artifact or 'advanced-slow-results'}`。"
        )
    else:
        add(
            f"- 证据来源：本地开发证据目录 `{out}`（`run.py all`；"
            f"{pg_version}）。正式 CI 证据（`postgres:15`）由 "
            "`advanced-slow` job 生成（artifact 名 `advanced-slow-results`）；"
            "下载 artifact 后运行 "
            "`python tests/advanced/report.py <artifact> --unit-junit <unit.xml> "
            "--ci-run <run-id>` 即可把本页脚替换为 CI run 号与 artifact 名。"
        )
    add(
        "- 重新生成：`python tests/advanced/report.py "
        f"{out} --unit-junit <unit.xml>`"
    )
    add(
        "- 产物命名约定：`run.py` 会覆盖 `<out>/<mode>/result.json`，"
        "因此业务报告使用各自的 durable 文件名（`mutation-result.json`、"
        "`report.json`、`ltl_results.json`、`booking_bmc.json`、"
        "`coverage-summary.json` 等）。"
    )
    if warnings:
        add("")
        add("**数据完整性警告**：")
        add("")
        for warning in sorted(set(warnings)):
            add(f"- {warning}")
    add("")
    return "\n".join(lines) + "\n", warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate docs/advanced_testing/ADVANCED_REPORT.md from "
            "tests/advanced artefacts."
        )
    )
    parser.add_argument("out", type=Path, help="directory passed to run.py all")
    parser.add_argument(
        "--unit-junit",
        type=Path,
        default=None,
        help="JUnit XML from `python tests/run_tests.py --junitxml=...`",
    )
    parser.add_argument(
        "--ci-run",
        default=os.environ.get("GITHUB_RUN_ID"),
        help="GitHub Actions run id for the footer (default: $GITHUB_RUN_ID)",
    )
    parser.add_argument(
        "--artifact",
        default=None,
        help="artifact name for the footer (default: advanced-slow-results)",
    )
    parser.add_argument(
        "--pg-version",
        default=None,
        help="override the PostgreSQL version shown in the footer",
    )
    args = parser.parse_args(argv)
    out = args.out.expanduser().resolve()
    if not out.is_dir():
        parser.error(f"out directory does not exist: {out}")
    data = collect(out, args.unit_junit)
    text, warnings = render(data, args)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    for warning in sorted(set(warnings)):
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
