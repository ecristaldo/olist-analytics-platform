with source as (

    select * from {{ source('olist', 'olist_products') }}

),

renamed as (

    select
        product_id,
        product_category_name,
        product_name_lenght as product_name_length,
        product_description_lenght as product_description_length,
        CAST(product_weight_g as int64) as product_weight_g,
        CAST(product_length_cm as int64) as product_length_cm,
        CAST(product_height_cm as int64) as product_height_cm,
        CAST(product_width_cm as int64) as product_width_cm,
        _loaded_at,
        COUNT(CAST(product_photos_qty as int64)) as product_photos_qty

    from source
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9

)

select * from renamed