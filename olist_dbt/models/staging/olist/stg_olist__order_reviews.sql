with source as (

    select * from {{ source('olist', 'olist_order_reviews') }}

),

renamed as (

    select
        review_id,
        order_id,
        CAST(review_score as int64) as review_score,
        review_comment_title,
        review_comment_message,
        CAST(review_creation_date as date) as review_creation_date,
        CAST(review_answer_timestamp as date) as review_answer_timestamp,
        _loaded_at

    from source

)

select * from renamed