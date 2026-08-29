# AI Agent Decision Log

Khong can copy full conversation. Ghi cac decision quan trong.

## Decision 1
- Hypothesis: Passing not-null, uniqueness, and range checks alone does not
  prove that the orders batch is safe to consume.
- Prompt / request to agent: Add contract type validation, freshness, and
  operational actions while preserving the stable validation API.
- Agent proposal: Reject type drift without silently coercing values; compare
  the newest `updated_at` against the contract freshness threshold; derive
  block/quarantine/warn actions from severity with contract-level overrides.
- Evidence/test: The healthy lab dataset has zero contract failures. After
  `duplicate_pk`, the validator reports one critical uniqueness failure; the
  reset returns it to zero. Manual malformed records also trigger type,
  range, accepted-values, and freshness checks with the expected actions.
- Accept / reject / revise: Accept.
- Why: A failed check should result in an actionable operating decision, not
  merely a log message.

## Decision 2
- Hypothesis: A customer SCD defect containing two active rows for one
  customer can silently fan out the orders-to-customers join and inflate
  revenue.
- Prompt / request to agent: Add dbt data tests, a business reconciliation
  test, and the smallest unit test that exposes join fan-out.
- Agent proposal: Enforce one mart row per date, reconcile the mart against
  completed staging orders, and use distinct active customer keys before the
  join. The unit fixture supplies two active customer versions.
- Evidence/test: `dbt build` passed 18/18 resources, including the
  reconciliation singular test and the duplicate-active-customer unit test.
- Accept / reject / revise: Accept.
- Why: A non-null and non-negative revenue value can still be wrong if it was
  multiplied by a join.

## Decision 3
- Hypothesis: A mean/std baseline is distorted by seasonality and historical
  outliers, so it can either create noisy alerts or miss a partial ingestion.
- Prompt / request to agent: Make the stable anomaly API context-aware while
  retaining the z-score method for simple cases.
- Agent proposal: In auto mode, prefer same-weekday history when provided and
  score against its median/MAD; otherwise use full-history MAD and finally a
  z-score fallback. Treat zero-MAD baselines deterministically.
- Evidence/test: Existing anomaly tests pass. The injected `volume_drop`
  batch (150 instead of 600 rows) is flagged by `auto:mad_same_segment` with
  score 5.53; reset restores the 600-row dataset.
- Accept / reject / revise: Accept.
- Why: Similar historical periods are a more valid comparison than an
  arbitrary global mean.

## Decision 4
- Hypothesis: An incident needs transitive, not merely direct, lineage to
  identify every affected user-facing asset or output column.
- Prompt / request to agent: Implement the stable column-level blast-radius
  API and verify the `stg_orders` impact path.
- Agent proposal: Use breadth-first traversal with a visited set for dataset
  and column lineage; this produces deterministic order and prevents cycles
  or shared descendants from duplicating results.
- Evidence/test: The public lineage test passes. `stg_orders` resolves to
  `fct_daily_revenue` and `ceo_revenue_dashboard`; the amount column resolves
  through staging and mart to the dashboard revenue column. A cyclic graph
  terminates without duplicate output.
- Accept / reject / revise: Accept.
- Why: Stopping at direct children would omit the CEO dashboard and any later
  consumer from incident scope.

## Decision 5
- Hypothesis: A single short-window burn spike is too noisy to page, whereas
  high burn observed in both short and long windows is sustained and urgent.
- Prompt / request to agent: Implement the stable `multiwindow_burn` API with
  a policy that distinguishes transient from sustained incidents.
- Agent proposal: Page critical at short >=14.4x and long >=6x; page warning
  at short >=6x and long >=3x; otherwise retain a non-paging warning if one
  window is elevated.
- Evidence/test: Public SLO tests pass. At 99.5% SLO with 2 bad checks of
  100, bad rate is 2%, allowed rate is 0.5%, burn is 4x, and the SLO is
  breached. A 20x/0.5x transient does not page; 20x/8x sustained burn pages
  critical.
- Accept / reject / revise: Accept.
- Why: Paging requires corroboration across time windows so operators receive
  actionable alerts rather than a notification for every transient spike.

## Decision 6
- Hypothesis: A stale knowledge base can cause old support-policy answers even
  when order contracts and text-length drift checks remain healthy.
- Prompt / request to agent: Use the public stale-KB scenario as an
  evidence-driven incident rehearsal.
- Agent proposal: Validate the KB contract, measure `published_at` freshness,
  calculate its SLO, and add the resulting signals to the baseline report.
- Evidence/test: Healthy KB has zero contract failures and a 10-minute
  freshness age. In the stale-KB rehearsal, the KB contract reports one
  failure at 190 minutes while text-length drift remains false; reset restores
  the healthy state.
- Accept / reject / revise: Accept.
- Why: Content shape is not a proxy for content freshness; a stale policy can
  retain normal length and embeddings while being operationally unsafe.

## Decision 7
- Hypothesis: Individual GX calls are hard to operate repeatedly because they
  do not preserve a named contract or translate failures into an action.
- Prompt / request to agent: Build a reusable GX Suite, Validation Definition,
  Checkpoint, and severity-aware Action without relying on external services.
- Agent proposal: Define a named orders expectation suite, connect it to the
  dataframe batch with a validation definition, execute it through a
  checkpoint, and persist accept/warn/quarantine/block to a local JSON action
  report.
- Evidence/test: The healthy GX Checkpoint passes all five Expectations and
  writes `accept`. With the duplicate-key fault it fails the critical
  uniqueness expectation and writes `block`; reset restores the 600-row
  healthy dataset.
- Accept / reject / revise: Accept.
- Why: GX configuration and downstream incident automation need a stable
  boundary, rather than an ad-hoc loop over individual Expectations.

## Decision 8
- Hypothesis: Mean-only monitoring can miss distribution or embedding-pipeline
  drift even when the average remains similar.
- Prompt / request to agent: Complete the stable distribution and embedding
  drift APIs without downloading an embedding model.
- Agent proposal: Compare q10/q50/q90 against the baseline and normalize the
  maximum displacement by baseline IQR; reuse this detector for embedding
  norms.
- Evidence/test: Public distribution/RAG tests pass. Identical embedding
  norms score 0 with no anomaly; a 0.66 norm batch against a 1.00 baseline
  scores 6.8 and is flagged.
- Accept / reject / revise: Accept.
- Why: Embedding norms provide a lightweight signal for model/normalization
  regressions, while quantiles detect shape changes that a mean ratio loses.
