"""Simple contract validator used as the starter baseline.

The implementation intentionally covers only common deterministic checks.
Students are expected to extend it with:
- stronger type validation/coercion rules,
- freshness checks,
- cross-field/cross-table assertions,
- severity-aware actions (block/quarantine/warn),
- richer observability metadata.
"""
from __future__ import annotations

from datetime import datetime, timezone
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    passed: bool,
    details: str,
    action: str | None = None,
) -> dict[str, Any]:
    return {
        "check": check,
        "column": column,
        "severity": severity,
        "passed": bool(passed),
        "details": details,
        # An action is meaningful only when the check fails. Keeping it on the
        # issue makes the validator directly usable by an orchestrator.
        "action": "none" if passed else (action or _default_action(severity)),
    }


_SEVERITY_ACTIONS = {
    "critical": "block",
    "warning": "quarantine",
    "info": "warn",
}


def _default_action(severity: str) -> str:
    """Map a data-quality severity to the safest default operational action."""
    return _SEVERITY_ACTIONS.get(severity.lower(), "warn")


def _is_expected_type(value: Any, expected_type: str) -> bool:
    """Return whether one non-null value matches a contract type.

    Numeric-looking strings are deliberately *not* accepted as numbers or
    integers. They are a type drift even if pandas could coerce them later.
    Datetime strings are accepted because CSV is a text transport format; their
    semantic type is established by successful datetime parsing.
    """
    if expected_type == "integer":
        return isinstance(value, (Integral, np.integer)) and not isinstance(value, (bool, np.bool_))
    if expected_type == "number":
        return isinstance(value, (Real, np.number)) and not isinstance(value, (bool, np.bool_))
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "datetime":
        return not pd.isna(pd.to_datetime(value, utc=True, errors="coerce"))
    # An unknown declared type should not turn a typo in a contract into a
    # false data failure. It can be introduced as a supported type explicitly.
    return True


def _invalid_type_count(series: pd.Series, expected_type: str) -> int:
    non_null = series[series.notna()]
    return int(sum(not _is_expected_type(value, expected_type) for value in non_null))


def _freshness_reference(freshness: dict[str, Any]) -> pd.Timestamp:
    """Use an explicit reference time when supplied, otherwise use UTC now.

    The optional contract value is useful for deterministic replay/backfill
    validation without weakening the normal real-time freshness check.
    """
    reference = freshness.get("reference_time")
    if reference is None:
        return pd.Timestamp(datetime.now(timezone.utc))
    parsed = pd.to_datetime(reference, utc=True, errors="coerce")
    if pd.isna(parsed):
        raise ValueError("freshness.reference_time must be a valid datetime")
    return pd.Timestamp(parsed)


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    # `fields` is accepted for the KB contract; `columns` remains the
    # canonical name used by tabular data contracts.
    columns = contract.get("columns", contract.get("fields", {}))

    for column, rules in columns.items():
        severity = rules.get("severity", "warning")
        action = rules.get("action")
        required = bool(rules.get("required", False))

        if column not in df.columns:
            if required:
                issues.append(
                    _issue(
                        "required_column",
                        column=column,
                        severity=severity,
                        passed=False,
                        details=f"Missing required column: {column}",
                        action=action,
                    )
                )
            continue

        series = df[column]

        if required:
            null_count = int(series.isna().sum())
            issues.append(
                _issue(
                    "not_null",
                    column=column,
                    severity=severity,
                    passed=(null_count == 0),
                    details=f"null_count={null_count}",
                    action=action,
                )
            )

        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(
                _issue(
                    "unique",
                    column=column,
                    severity=severity,
                    passed=(duplicate_count == 0),
                    details=f"duplicate_rows={duplicate_count}",
                    action=action,
                )
            )

        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_mask = series.notna() & ~series.isin(accepted)
            invalid_count = int(invalid_mask.sum())
            issues.append(
                _issue(
                    "accepted_values",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; accepted={accepted}",
                    action=action,
                )
            )

        expected_type = rules.get("type")
        if expected_type:
            invalid_count = _invalid_type_count(series, str(expected_type))
            issues.append(
                _issue(
                    "type",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"expected={expected_type}; invalid_count={invalid_count}",
                    action=action,
                )
            )

        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            # A non-null value that cannot be converted is invalid for a range
            # too; do not allow coercion to hide malformed values.
            invalid = series.notna() & numeric.isna()
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(
                _issue(
                    "range",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}",
                    action=action,
                )
            )

        if "min_length" in rules:
            lengths = series.dropna().map(lambda value: len(value) if hasattr(value, "__len__") else 0)
            invalid_count = int((lengths < rules["min_length"]).sum())
            issues.append(
                _issue(
                    "min_length",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"min_length={rules['min_length']}; invalid_count={invalid_count}",
                    action=action,
                )
            )

    freshness = contract.get("freshness")
    if freshness:
        column = freshness.get("column")
        severity = freshness.get("severity", "warning")
        action = freshness.get("action")
        max_delay = freshness.get("max_delay_minutes")
        if not column or max_delay is None:
            raise ValueError("freshness requires both column and max_delay_minutes")
        if column not in df.columns:
            issues.append(
                _issue(
                    "freshness",
                    column=column,
                    severity=severity,
                    passed=False,
                    details=f"Freshness column is missing: {column}",
                    action=action,
                )
            )
        else:
            timestamps = pd.to_datetime(df[column], utc=True, errors="coerce")
            latest = timestamps.max()
            if pd.isna(latest):
                issues.append(
                    _issue(
                        "freshness",
                        column=column,
                        severity=severity,
                        passed=False,
                        details="No valid timestamp available for freshness check",
                        action=action,
                    )
                )
            else:
                reference = _freshness_reference(freshness)
                delay_minutes = (reference - latest).total_seconds() / 60
                is_future = delay_minutes < -1
                passed = not is_future and delay_minutes <= float(max_delay)
                details = (
                    f"latest={latest.isoformat()}; reference={reference.isoformat()}; "
                    f"delay_minutes={delay_minutes:.2f}; max_delay_minutes={max_delay}"
                )
                if is_future:
                    details += "; future_timestamp=true"
                issues.append(
                    _issue(
                        "freshness",
                        column=column,
                        severity=severity,
                        passed=passed,
                        details=details,
                        action=action,
                    )
                )

    return issues


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [i for i in issues if not i.get("passed", False)]
    if min_severity is None:
        return failed
    order = {"info": 0, "warning": 1, "critical": 2}
    threshold = order[min_severity]
    return [i for i in failed if order.get(i.get("severity", "warning"), 1) >= threshold]
