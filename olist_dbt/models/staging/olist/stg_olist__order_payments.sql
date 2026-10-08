with source as (

    select * from {{ source('olist', 'olist_order_payments') }}

),

renamed as (

    select
        order_id,
        payment_sequential,
        payment_type,
        CAST(payment_value as numeric) as payment_amount,
        _loaded_at,
        CAST(payment_installments as int64) as payment_installments

    from source
    
)

select * from renamed