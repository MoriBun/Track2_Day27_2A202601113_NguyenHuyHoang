#!/usr/bin/env python3
"""Run the orders data contract through a reusable GX validation workflow.

The script creates an Expectation Suite, ties it to the dataframe Batch with a
Validation Definition, and executes both through a Checkpoint. Its custom
Action records the severity-aware operational decision locally, which keeps
the lab self-contained while demonstrating where a pager/quarantine workflow
would integrate in production.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from typing_extensions import override

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import great_expectations as gx
    from great_expectations.checkpoint import (
        ActionContext,
        CheckpointResult,
        ValidationAction,
    )
except ImportError as exc:  # friendlier classroom failure
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc


_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
_SEVERITY_ACTION = {
    "info": "warn",
    "warning": "quarantine",
    "critical": "block",
}


def _validation_results(checkpoint_result: CheckpointResult) -> list[Any]:
    """Read GX result objects across supported CheckpointResult layouts."""
    results: list[Any] = []
    for value in checkpoint_result.run_results.values():
        # GX Core 1.21 stores ExpectationSuiteValidationResult objects. The
        # dictionary branch also keeps this action compatible with older GX.
        results.append(value.get("validation_result") if isinstance(value, dict) else value)
    return results


def _severity_from_result(result: Any) -> str:
    config = getattr(result, "expectation_config", None)
    severity = getattr(config, "severity", "critical")
    value = getattr(severity, "value", severity)
    value = str(value).lower()
    return value if value in _SEVERITY_RANK else "critical"


class LocalSeverityAction(ValidationAction):
    """Persist a safe local action decision after a GX Checkpoint run."""

    type: Literal["local_severity_action"] = "local_severity_action"
    output_path: str

    @override
    def run(
        self,
        checkpoint_result: CheckpointResult,
        action_context: ActionContext | None = None,
    ) -> dict[str, Any]:
        failed_severities: list[str] = []
        for suite_result in _validation_results(checkpoint_result):
            for result in suite_result.results:
                if not bool(result.success):
                    failed_severities.append(_severity_from_result(result))

        highest = max(failed_severities, key=_SEVERITY_RANK.get, default=None)
        payload = {
            "checkpoint_success": bool(checkpoint_result.success),
            "failed_expectations": len(failed_severities),
            "highest_failure_severity": highest,
            "action": _SEVERITY_ACTION[highest] if highest else "accept",
        }
        path = Path(self.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload


def build_checkpoint(df: pd.DataFrame) -> gx.Checkpoint:
    """Create the Suite -> Validation Definition -> Checkpoint workflow."""
    context = gx.get_context()

    data_source = context.data_sources.add_pandas("orders_pandas")
    asset = data_source.add_dataframe_asset(name="orders_dataframe")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_orders")

    suite = context.suites.add(gx.ExpectationSuite(name="orders_contract_suite"))
    for expectation in [
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="order_id", severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="order_id", severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="amount", min_value=0, severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="currency", value_set=["USD", "VND"], severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="status",
            value_set=["pending", "completed", "refunded", "cancelled"],
            severity="warning",
        ),
    ]:
        suite.add_expectation(expectation)

    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="orders_contract_validation",
            data=batch_definition,
            suite=suite,
        )
    )
    return context.checkpoints.add(
        gx.Checkpoint(
            name="orders_contract_checkpoint",
            validation_definitions=[validation_definition],
            actions=[
                LocalSeverityAction(
                    name="record_severity_action",
                    output_path=str(ROOT / "reports" / "gx_latest_action.json"),
                )
            ],
            result_format={"result_format": "SUMMARY"},
        )
    )


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "incoming" / "orders.csv")
    checkpoint = build_checkpoint(df)
    result = checkpoint.run(batch_parameters={"dataframe": df})

    for suite_result in _validation_results(result):
        for expectation_result in suite_result.results:
            config = expectation_result.expectation_config
            print(
                f"{config.type:<40} success={expectation_result.success} "
                f"severity={_severity_from_result(expectation_result)}"
            )

    action_path = ROOT / "reports" / "gx_latest_action.json"
    action = json.loads(action_path.read_text(encoding="utf-8"))
    print("\nGX checkpoint result:", "PASS" if result.success else "FAIL")
    print("Operational action:", action["action"])
    print("Action report:", action_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
