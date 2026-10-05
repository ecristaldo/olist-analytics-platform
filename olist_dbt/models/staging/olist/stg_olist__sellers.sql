with source as (

    select * from {{ source('olist', 'olist_sellers') }}

),

renamed as (

    select
        seller_id,
        seller_zip_code_prefix,
        seller_city as seller_city_name,
        seller_state as seller_state_code,
        _loaded_at

    from source

)

select * from renamed