with source as (

    select * from {{ source('olist', 'olist_orders') }}

),

renamed as (

    select
        order_id,
        customer_id,
        order_status,
        timestamp(order_purchase_timestamp, 'America/Sao_Paulo') as purchased_at,
        timestamp(order_approved_at, 'America/Sao_Paulo') as approved_at,
        timestamp(order_delivered_carrier_date, 'America/Sao_Paulo') as delivered_carrier_at,
        timestamp(order_delivered_customer_date, 'America/Sao_Paulo') as delivered_customer_at,
        date(timestamp(order_estimated_delivery_date, 'America/Sao_Paulo')) as estimated_delivery_date,
        _loaded_at

    from source

)

select * from renamed