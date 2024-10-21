import boto3
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Form, HTTPException, Query, Depends
from math import ceil
from datetime import datetime
from app.auth import validate_token
from app.utilities_S3 import download_object, get_s3_client, S3_BUCKET_NAME, S3_REGION


faq_router = APIRouter()
s3 = get_s3_client()

# Endpoint to create an FAQ
@faq_router.post("/add-faq", dependencies=[Depends(validate_token)])
async def create_faq(
    id: str = Form(...),
    title: str = Form(...),
    answer: str = Form(...),
    draft: bool = Form(...),
):
    try:
        created_at = datetime.utcnow().isoformat()
        faq_data = {
            "id": id,
            "title": title,
            "answer": answer,
            "draft": draft,
            "created_at": created_at,
        }

        s3_json_key = f"faqs/{id}.json"
        json_data = json.dumps(faq_data, indent=4)

        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_json_key,
            Body=json_data,
            ContentType='application/json'
        )
        download_object(s3_json_key, True)	
        return {"message": "FAQ created successfully", "faq": faq_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create FAQ: {str(e)}")

# Endpoint to list FAQs
@faq_router.get("/faqs")
async def list_faqs(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50), includeDrafts: bool = Query(False)):
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="faqs/")

        faq_files = []
        for page_content in pages:
            if 'Contents' in page_content:
                faq_files.extend([file for file in page_content['Contents'] if file['Key'].endswith('.json')])

        if not faq_files:
            return {"message": "No FAQs found", "total_faqs": 0, "total_pages": 0, "faqs": []}

        total_faqs = len(faq_files)
        total_pages = ceil(total_faqs / page_size)

        if page > total_pages:
            raise HTTPException(status_code=404, detail="Page not found")

        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_faqs)
        faq_files_for_page = faq_files[start_index:end_index]

        faqs = []
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(download_object, [file['Key'] for file in faq_files_for_page]))

        for faq_data in results:
            if not includeDrafts and faq_data.get('isDraft', False):
                continue
            faqs.append(faq_data)

        total_faqs_after_filter = len(faqs)

        return {
            "message": "FAQs retrieved successfully",
            "total_faqs": total_faqs_after_filter,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "faqs": faqs,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve FAQs: {str(e)}")

# Endpoint to get FAQ details by ID
@faq_router.get("/faq/{faq_id}")
async def get_faq(faq_id: str):
    try:
        s3_json_key = f"faqs/{faq_id}.json"
        faq_data = download_object(s3_json_key)
        return {"message": "FAQ retrieved successfully", "faq": faq_data}
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="FAQ not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve FAQ: {str(e)}")

# Endpoint to delete an FAQ by ID
@faq_router.delete("/faq/{faq_id}", dependencies=[Depends(validate_token)])
async def delete_faq(faq_id: str):
    try:
        s3_json_key = f"faqs/{faq_id}.json"
        try:
            s3.head_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)
        except s3.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="FAQ not found")

        s3.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)

        return {"message": f"FAQ with ID {faq_id} deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete FAQ: {str(e)}")
