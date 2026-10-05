with source as (

    select * from {{ source('olist', 'olist_order_items') }}

),

renamed as (

    select
        order_id,
        order_item_id,
        product_id,
        seller_id,
        CAST(shipping_limit_date as date) as shipping_limit_date,
        CAST(price as numeric) as item_price,
        CAST(freight_value as numeric) as freight_value,
        _loaded_at

    from source

)

select * from renamed