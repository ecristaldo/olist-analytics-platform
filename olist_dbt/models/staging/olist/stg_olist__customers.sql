with source as (

    select * from {{ source('olist', 'olist_customers') }}

),

renamed as (

    select
        customer_id as customer_id,
        customer_unique_id as customer_uid,
        customer_zip_code_prefix,
        customer_city as customer_city_name,
        customer_state as customer_state_code,
        _loaded_at

    from source

)

select * from renamed