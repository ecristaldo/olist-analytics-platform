-- One row per order: how much was paid, in how many payments, and by what method.
--
-- main_payment_type is the payment type that covers the most money in the order
-- (two credit-card payments of 30 beat one voucher of 50). Ties go to the type that
-- was used first. payment_sequential is a STRING in staging, so it is cast before
-- sorting; as text "10" would sort before "2".

with payments as (

    select
        order_id,
        payment_sequential,
        payment_type,
        payment_amount
    from {{ ref('stg_olist__order_payments') }}

),

totals as (

    select
        order_id,
        sum(payment_amount) as total_paid,
        count(*) as payment_count
    from payments
    group by order_id

),

by_type as (

    select
        order_id,
        payment_type,
        sum(payment_amount) as type_amount,
        min(cast(payment_sequential as int64)) as first_sequential
    from payments
    group by order_id, payment_type

),

ranked_types as (

    select
        order_id,
        payment_type,
        row_number() over (
            partition by order_id
            order by type_amount desc, first_sequential
        ) as type_rank
    from by_type

),

main_payment as (

    select
        order_id,
        payment_type as main_payment_type
    from ranked_types
    where type_rank = 1

)

select
    totals.order_id,
    totals.total_paid,
    totals.payment_count,
    main_payment.main_payment_type
from totals
inner join main_payment
    on main_payment.order_id = totals.order_id
