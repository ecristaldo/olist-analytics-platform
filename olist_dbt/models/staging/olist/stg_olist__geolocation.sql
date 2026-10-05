with source as (

    select * from {{ source('olist', 'olist_geolocation') }}

),

renamed as (

    select
        geolocation_zip_code_prefix as zip_code_prefix,
        geolocation_state as state_code,
        geolocation_city as city_name,
        geolocation_lat as latitude,
        geolocation_lng as longitude,
        _loaded_at

    from source

)

select * from renamed