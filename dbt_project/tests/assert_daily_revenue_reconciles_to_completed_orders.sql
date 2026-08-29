-- A singular business test: every fct row must reconcile exactly to completed
-- staging orders. It catches an accidental fan-out in a dimension join even
-- when daily_revenue remains non-null and non-negative.
with expected as (
    select
        order_date,
        count(*) as expected_completed_order_rows,
        sum(amount_usd) as expected_daily_revenue
    from {{ ref('stg_orders') }}
    where status = 'completed'
    group by 1
),
actual as (
    select
        order_date,
        completed_order_rows,
        daily_revenue
    from {{ ref('fct_daily_revenue') }}
)
select
    coalesce(actual.order_date, expected.order_date) as order_date,
    actual.completed_order_rows,
    expected.expected_completed_order_rows,
    actual.daily_revenue,
    expected.expected_daily_revenue
from actual
full outer join expected using (order_date)
where coalesce(actual.completed_order_rows, 0) != coalesce(expected.expected_completed_order_rows, 0)
   or abs(coalesce(actual.daily_revenue, 0) - coalesce(expected.expected_daily_revenue, 0)) > 0.0001
