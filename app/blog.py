import boto3
import json

from fastapi import APIRouter, Form, File, UploadFile, HTTPException, Query, Depends
from typing import Optional
from io import BytesIO
from math import ceil

from concurrent.futures import ThreadPoolExecutor
from app.auth import validate_token


S3_BUCKET_NAME = "medicare-blogs"
S3_REGION = "us-east-1"
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
)

blog_router = APIRouter()

@blog_router.post("/add-blog", dependencies=[Depends(validate_token)])
async def create_post(
    id: str = Form(...),
    title: str = Form(...),
    subtitle: str = Form(...),
    author: str = Form(...),
    tags: str = Form(...),
    content: str = Form(...),
    draft: bool = Form(...),
    image: Optional[UploadFile] = File(None),
):
    try:
        image_url = None
        if image:
            print(f"Uploading image: {image.filename}")
            image_bytes = await image.read()
            s3_image_key = f"blog-images/{image.filename}"
            
            s3.upload_fileobj(
                BytesIO(image_bytes),
                S3_BUCKET_NAME,
                s3_image_key
            )
            
            image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_image_key}"

        blog_data = {
            "id": id,
            "title": title,
            "subtitle": subtitle,
            "author": author,
            "tags": tags.split(","),
            "content": content,
            "draft": draft,
            "image_url": image_url,
        }

        s3_json_key = f"blogs/{id}.json"
        json_data = json.dumps(blog_data, indent=4)

        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_json_key,
            Body=json_data,
            ContentType='application/json'
        )

        return {"message": "Post created successfully", "post": blog_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")




@blog_router.get("/blogs")
async def list_posts(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50), includeDrafts: bool = Query(False)):
    print("Listing posts")
    try:
        # Use paginator for listing objects in chunks
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="blogs/")

        blog_files = []

        # Collect all the blog files from all pages (just the keys, no download yet)
        for page_content in pages:
            if 'Contents' in page_content:
                blog_files.extend([file for file in page_content['Contents'] if file['Key'].endswith('.json')])

        if not blog_files:
            return {"message": "No posts found", "total_posts": 0, "total_pages": 0, "posts": []}

        # Calculate total posts and total pages
        total_posts = len(blog_files)
        total_pages = ceil(total_posts / page_size)

        # Handle out of range pages
        if page > total_pages:
            raise HTTPException(status_code=404, detail="Page not found")

        # Calculate start and end index for the current page
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_posts)

        # Select the blog files that correspond to the requested page
        blog_files_for_page = blog_files[start_index:end_index]

        posts = []

        def download_object(file_key):
            # Download and process each blog post
            s3_object = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
            post_data = json.loads(s3_object['Body'].read().decode('utf-8'))
            return post_data

        # Use ThreadPoolExecutor to download posts concurrently
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(download_object, [file['Key'] for file in blog_files_for_page]))

        # Apply draft filter based on the includeDrafts parameter
        for post_data in results:
            if not includeDrafts and post_data.get('draft', False):
                continue
            posts.append(post_data)

        # Calculate the actual number of posts after filtering (if applicable)
        total_posts_after_filter = len(posts)
        
        print("Posts retrieved successfully")

        return {
            "message": "Posts retrieved successfully",
            "total_posts": total_posts_after_filter,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "posts": posts,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve posts: {str(e)}")


# Endpoint to get Blog details by ID
@blog_router.get("/blog/{blog_id}")
async def get_blog(blog_id: str):
    try:
        # Construct the S3 key using the Blog ID
        s3_json_key = f"blogs/{blog_id}.json"

        # Fetch the object from S3
        s3_object = s3.get_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)
        blog_data = json.loads(s3_object['Body'].read().decode('utf-8'))

        return {"message": "Blog retrieved successfully", "blog": blog_data}

    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Blog not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve Blog: {str(e)}")

# Endpoint to delete a Blog by ID
@blog_router.delete("/blog/{blog_id}", dependencies=[Depends(validate_token)])
async def delete_blog(blog_id: str):
    try:
        # Construct the S3 key using the Blog ID
        s3_json_key = f"blogs/{blog_id}.json"

        # Check if the file exists before attempting to delete it
        try:
            s3.head_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)
        except s3.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="Blog not found")

        # Delete the Blog from S3
        s3.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)

        return {"message": f"Blog with ID {blog_id} deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete Blog: {str(e)}")
