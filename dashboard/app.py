from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "latest_metrics.json"
HISTORY = ROOT / "data" / "history" / "metrics_history.csv"

st.set_page_config(page_title="Data Reliability Lab", layout="wide")
st.title("Data Reliability Game Day")
st.caption("Starter dashboard - improve it only if it helps incident decisions.")

if not REPORT.exists():
    st.warning("Run `make baseline` first to generate reports/latest_metrics.json")
    st.stop()

report = json.loads(REPORT.read_text(encoding="utf-8"))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders rows", report["orders_rows"])
c2.metric("Freshness (min)", f"{report['freshness_minutes']:.1f}")
c3.metric("Contract failures", report["failed_contract_checks"])
c4.metric("Critical failures", report["critical_contract_failures"])

st.subheader("Current signals")
st.json({
    "row_count_anomaly": report["row_count_anomaly"],
    "kb_contract_failures": report.get("kb_failed_contract_checks", 0),
    "kb_freshness_minutes": report.get("kb_freshness_minutes"),
    "kb_freshness_failed": report.get("kb_freshness_failed", False),
    "kb_text_length_signal": report["kb_text_length_signal"],
    "contract_slo": report["contract_slo"],
    "rag_freshness_slo": report.get("rag_freshness_slo"),
})

history = pd.read_csv(HISTORY)
st.subheader("Historical row count")
st.line_chart(history.set_index("date")[["row_count"]])

st.subheader("Example blast radius")
st.write("stg_orders -> " + " -> ".join(report["sample_blast_radius_from_stg_orders"]))

st.info("TODO: add SLO target, remaining error budget, burn-rate windows, owner/runbook links, and incident status.")
