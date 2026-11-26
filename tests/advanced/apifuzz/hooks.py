"""Checks and reporting helpers for the P8 OpenAPI property-fuzz mode.

This module keeps the pieces that are easy to unit-test away from the runner:

* :func:`make_expected_status_check` builds a Schemathesis custom check from
  the FP-AUTH-3 expectation matrix;
* :func:`classify_failure` attributes a Schemathesis failure to one of the
  three categories required by the task (real defect / schema drift / test
  configuration);
* :func:`redact_text` / :func:`redact_curl` strip credentials before a failure
  is written to ``report.json`` or printed to the console.

The expected status sets are hand-written from ``docs/REQUIREMENTS.md`` and
``SPEC.md``; they are not derived from the application's generated OpenAPI
document.  That keeps the oracle independent from the implementation under
test.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from schemathesis.core.failures import CustomFailure

__all__ = [
    "SCHEMA_DRIFT",
    "REAL_DEFECT",
    "TEST_CONFIG",
    "classify_failure",
    "failure_check_name",
    "make_expected_status_check",
    "redact_curl",
    "redact_text",
]

REAL_DEFECT = "real_defect"
SCHEMA_DRIFT = "schema_drift"
TEST_CONFIG = "test_config"

_REDACTED = "[REDACTED]"

# Cookie / Set-Cookie headers, CSRF headers and bearer tokens.  Schemathesis
# already replaces known secret values with "[Filtered]" in its curl output;
# these patterns are a second, local guarantee for messages produced by the
# checks or by transport errors.
_HEADER_PATTERNS = (
    re.compile(r"(?i)(\bset-cookie\s*:\s*)([^'\r\n]+)"),
    re.compile(r"(?i)(\bcookie\s*:\s*)([^'\r\n]+)"),
    re.compile(r"(?i)(\bx-csrf-token\s*:\s*)([^\s,;']+)"),
    re.compile(r"(?i)(\bauthorization\s*:\s*)([^'\r\n]+)"),
)

# JSON / form style keys that carry credentials.  Keep the quotes so the
# redacted value still looks like a JSON value in failure messages.
_JSON_SECRET_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])"
    r"([\"']?(?:password|passwd|csrf_token|session|access_token|"
    r"refresh_token|token)[\"']?\s*:\s*)"
    r"([\"'])(.*?)\2"
)

# The same keys in a bare `key=value` form (query strings, cookie pairs).
_BARE_SECRET_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])"
    r"([\"']?(?:password|passwd|csrf_token|session|access_token|"
    r"refresh_token|token)[\"']?\s*[:=]\s*)"
    r"([^\s,;&\"']+)"
)

# Query-string / cookie-pair values.  Keep the key, drop the value.
_COOKIE_PAIR_PATTERN = re.compile(
    r"(?i)\b(session|csrf_token|access_token|refresh_token)=([^\s&;'\"\]\)]+)"
)


def redact_text(text: object) -> str:
    """Return *text* with cookie, CSRF, password and token values removed.

    The output is safe to write to a report or a log.  The function is
    deliberately conservative: over-redaction is harmless, a leaked synthetic
    session token is not.
    """

    if text is None:
        return ""
    value = str(text)
    if not value:
        return value
    for pattern in _HEADER_PATTERNS:
        value = pattern.sub(rf"\1{_REDACTED}", value)
    value = _JSON_SECRET_PATTERN.sub(rf"\1\2{_REDACTED}\2", value)
    value = _BARE_SECRET_PATTERN.sub(rf"\1{_REDACTED}", value)
    value = _COOKIE_PAIR_PATTERN.sub(rf"\1={_REDACTED}", value)
    return value


def redact_curl(command: object) -> str:
    """Redact a Schemathesis curl command before it reaches the report."""

    return redact_text(command)


def make_expected_status_check(
    allowed: Iterable[int], *, label: str
):
    """Return a Schemathesis response check enforcing a status-code set.

    ``label`` is included in the assertion message so a failure identifies the
    operation even when Schemathesis collapses several cases together.
    """

    statuses = frozenset(int(status) for status in allowed)
    ordered = sorted(statuses)

    def check(_ctx, response, _case):
        if response.status_code not in statuses:
            raise AssertionError(
                f"{label}: expected one of {ordered}, "
                f"got {response.status_code}"
            )

    # Schemathesis uses the function name as the check name in its report.
    check.__name__ = "expected_status_matrix"
    return check


def failure_check_name(failure: BaseException) -> str:
    """Best-effort name of the Schemathesis check that produced *failure*."""

    checks = getattr(failure, "checks", ())
    if checks:
        return str(checks[0])
    if isinstance(failure, CustomFailure):
        return "expected_status_matrix"
    return "unknown"


def classify_failure(
    failure: BaseException, *, status_code: int, expected: frozenset[int]
) -> str:
    """Attribute a Schemathesis failure to the task's reporting categories.

    ``status_code_conformance`` reports statuses that are not declared in the
    OpenAPI document.  When the status is nevertheless part of the hand-written
    expectation matrix (for example the required 401/403/404 of FP-AUTH-3) the
    mismatch is a documentation gap, not a behavioural defect.  Every other
    failure is a real defect; transport or harness failures are classified by
    the caller as test configuration.
    """

    name = failure_check_name(failure)
    if name == "status_code_conformance":
        return SCHEMA_DRIFT if status_code in expected else REAL_DEFECT
    if name == "response_schema_conformance":
        return REAL_DEFECT
    if name == "not_a_server_error":
        return REAL_DEFECT
    if isinstance(failure, CustomFailure):
        return REAL_DEFECT
    # Any check we did not explicitly enable should not fire.  Treat it as a
    # real response problem rather than silently dropping it.
    return REAL_DEFECT
