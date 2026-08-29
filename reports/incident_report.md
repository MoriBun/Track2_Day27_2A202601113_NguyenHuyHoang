# Incident Report — Practice Scenario: Stale Knowledge Base

> This is an evidence-driven report for the lab's public `stale_kb` rehearsal,
> not the final mystery incident supplied by the instructor. Replace it when a
> mystery input is provided.

## Severity

P2 — Support Agent may provide outdated policy information, but the orders
pipeline and CEO revenue dashboard are unaffected.

## Summary

The active knowledge base exceeded its 60-minute `published_at` freshness
contract. The documents' content length remained normal, so a content-shape
metric alone would not have detected the risk. The freshness gate quarantines
the stale KB batch rather than treating it as safe to index.

## Detection

- Signal: KB freshness contract failure and RAG freshness SLO breach.
- First observed time: first post-fault baseline run on 2026-08-29 UTC.

## Root Cause

The newest KB `published_at` timestamp was approximately 190 minutes old,
which is 130 minutes beyond the 60-minute contract. Evidence is consistent
with a delayed or failed KB publishing/re-indexing workflow. The public
rehearsal deliberately simulated this condition; a real incident would verify
the specific upstream job failure before closing the RCA.

## Evidence

1. Healthy baseline: 0 KB contract failures and KB freshness approximately 10
   minutes.
2. Incident baseline: 1 KB contract failure and KB freshness approximately
   190 minutes; the freshness rule is configured at 60 minutes.
3. KB text-length anomaly remained `False`, while orders contract failures
   remained 0. Therefore, the incident was freshness-specific rather than an
   orders issue or a document-length shift.

## Blast Radius

```text
kb_documents
-> kb_active_docs
-> rag_index
-> support_agent
```

Potential user impact: Support Agent can retrieve and answer from an outdated
refund or policy document.

## Mitigation

1. Quarantine the stale KB batch; do not promote it to `kb_active_docs`.
2. Continue serving the last known-good RAG index while the KB publish job is
   repaired.
3. Re-ingest the source documents and rebuild the RAG index after freshness
   returns within the contract limit.

## Recovery

`reset_lab.py` re-anchored the lab KB timestamps. The subsequent healthy
baseline recorded KB freshness of about 10 minutes, 0 KB contract failures,
and a healthy RAG freshness SLO.

## Verification

- [x] Orders and KB contracts healthy after reset.
- [x] dbt build previously passed 18/18 resources; this incident did not
  modify orders/customers transformations.
- [x] KB text-length signal stayed in its expected range.
- [x] RAG freshness SLO healthy after recovery.
- [ ] Execute a Support Agent policy-query smoke test against the rebuilt RAG
  index before declaring a production recovery.

Note: the row-count anomaly is an unrelated known baseline/calendar mismatch
in this synthetic lab and is not evidence for the KB incident.

## Prevention / Action Items

| Action | Owner | Deadline | Why |
|---|---|---|---|
| Block promotion when KB freshness exceeds 60 minutes | Support AI | 2026-09-01 | Prevent stale documents entering the active index |
| Alert at 45 minutes of KB freshness age | Data Platform | 2026-09-01 | Leave time to repair before the SLO is breached |
| Add an automated policy retrieval smoke test after indexing | Support AI QA | 2026-09-05 | Confirm the retrieved answer reflects the newest policy |
| Record publisher and index-run IDs in baseline evidence | Data Platform | 2026-09-05 | Shorten root-cause investigation in a real incident |
