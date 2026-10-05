with source as (

    select * from {{ source('olist', 'olist_orders') }}

),

renamed as (

    select
        order_id,
        customer_id,
        order_status,
        timestamp(order_purchase_timestamp, 'America/Sao_Paulo') as purchased_at,
        cast(order_approved_at as timestamp) as approved_at,
        cast(order_delivered_carrier_date as timestamp) as delivered_carrier_at,
        cast(order_delivered_customer_date as timestamp) as delivered_customer_at,
        date(cast(order_estimated_delivery_date as timestamp)) as estimated_delivery_date,
        _loaded_at

    from source

)

select * from renamed