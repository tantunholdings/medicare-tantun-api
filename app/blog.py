import boto3
import json

from fastapi import APIRouter, Form, File, UploadFile, HTTPException, Query, Depends
from typing import Optional
from io import BytesIO
from math import ceil
import uuid
from concurrent.futures import ThreadPoolExecutor
from app.auth import validate_token
from app.utilities_S3 import download_object, get_s3_client, S3_BUCKET_NAME, S3_REGION

s3 = get_s3_client()
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
    prev_image_url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
):
    try:
        image_url = prev_image_url
        if image:
            print(f"Uploading image: {image.filename}")
            
            image_bytes = await image.read()
            random_filename = str(uuid.uuid4())
            s3_image_key = f"blog-images/{random_filename}"
            
            s3.upload_fileobj(
                BytesIO(image_bytes),
                S3_BUCKET_NAME,
                s3_image_key
            )
            
            image_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_image_key}"
            print(f"Image uploaded successfully: {image_url}")
        
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
        
        download_object(s3_json_key, True)

        return {"message": "Post created successfully", "post": blog_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")



@blog_router.get("/blogs")
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    tag: str = Query("All"),
    includeDrafts: bool = Query(False)
):
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

        # Use ThreadPoolExecutor to download posts concurrently
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(download_object, [file['Key'] for file in blog_files]))

        # Filter by drafts
        filtered_posts = [
            post_data for post_data in results
            if includeDrafts or not post_data.get('draft', False)
        ]

        # Handle the "Latest" tag by sorting posts by date (assuming each post has a 'date' field)
        if tag == "Latest":
            filtered_posts.sort(key=lambda x: x.get('date', ''), reverse=True)
        else:
            # Filter by the specified tag if it's not "All"
            if tag != "All":
                filtered_posts = [
                    post_data for post_data in filtered_posts
                    if tag in post_data.get('tags', [])
                ]

        # Calculate total posts after filtering
        total_posts = len(filtered_posts)
        total_pages = ceil(total_posts / page_size)

        # Handle out of range pages
        if page > total_pages:
            raise HTTPException(status_code=404, detail="Page not found")

        # Calculate start and end index for the current page
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_posts)

        # Select the posts for the current page
        posts_for_page = filtered_posts[start_index:end_index]

        print("Posts retrieved successfully")

        return {
            "message": "Posts retrieved successfully",
            "total_posts": total_posts,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "posts": posts_for_page,
        }

    except Exception as e:
        print(f"Failed to retrieve posts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve posts: {str(e)}")




# Endpoint to get Blog details by ID
@blog_router.get("/blog/{blog_id}")
async def get_blog(blog_id: str):
    try:
        # Construct the S3 key using the Blog ID
        s3_json_key = f"blogs/{blog_id}.json"

        blog_data = download_object(s3_json_key)

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
