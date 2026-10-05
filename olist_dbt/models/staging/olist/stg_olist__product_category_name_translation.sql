with source as (

    select * from {{ source('olist', 'olist_product_category_name_translation') }}

),

renamed as (

    select
        product_category_name,
        product_category_name_english as product_category_name_en,
        _loaded_at

    from source

)

select * from renamed