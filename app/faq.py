import boto3
import json
from uuid import uuid4
from fastapi import APIRouter, Form, HTTPException, Query
from math import ceil
from datetime import datetime


# AWS S3 Configuration
S3_BUCKET_NAME = "medicare-blogs"
S3_REGION = "us-east-1"
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
)

faq_router = APIRouter()

# Endpoint to create an FAQ
@faq_router.post("/add-faq")
async def create_faq(
    id: str = Form(...),
    title: str = Form(...),
    answer: str = Form(...),
    draft: bool = Form(...)
):
    try:
        created_at = datetime.utcnow().isoformat()
        # Create FAQ data
        faq_data = {
            "id": id,
            "title": title,
            "answer": answer,
            "draft": draft,
            "created_at": created_at,
        }

        # Serialize FAQ data as JSON and store in S3
        s3_json_key = f"faqs/{id}.json"
        json_data = json.dumps(faq_data, indent=4)

        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_json_key,
            Body=json_data,
            ContentType='application/json'
        )

        return {"message": "FAQ created successfully", "faq": faq_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create FAQ: {str(e)}")

@faq_router.get("/faqs")
async def list_faqs(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50), includeDrafts: bool = Query(False)):
    try:
        # List all FAQ JSON files from the S3 bucket
        response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix="faqs/")
        
        if 'Contents' not in response:
            return {"message": "No FAQs found", "total_faqs": 0, "total_pages": 0, "faqs": []}

        faq_files = [file for file in response['Contents'] if file['Key'].endswith('.json')]

        faqs = []
        for file in faq_files:
            s3_object = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file['Key'])
            faq_data = json.loads(s3_object['Body'].read().decode('utf-8'))
            
            # Apply draft filter based on the includeDrafts parameter
            if not includeDrafts and faq_data.get('isDraft', False):
                continue  # Skip drafts if includeDrafts is False
            
            faqs.append(faq_data)

        # Now, calculate pagination details after filtering drafts
        total_faqs = len(faqs)
        total_pages = ceil(total_faqs / page_size)

        # Handle out of range pages
        if page > total_pages:
            raise HTTPException(status_code=404, detail="Page not found")

        # Paginate the results
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_faqs = faqs[start_index:end_index]

        return {
            "message": "FAQs retrieved successfully",
            "total_faqs": total_faqs,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "faqs": paginated_faqs,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve FAQs: {str(e)}")

    

# Endpoint to get FAQ details by ID
@faq_router.get("/faq/{faq_id}")
async def get_faq(faq_id: str):
    try:
        # Construct the S3 key using the FAQ ID
        s3_json_key = f"faqs/{faq_id}.json"

        # Fetch the object from S3
        s3_object = s3.get_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)
        faq_data = json.loads(s3_object['Body'].read().decode('utf-8'))

        return {"message": "FAQ retrieved successfully", "faq": faq_data}

    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="FAQ not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve FAQ: {str(e)}")


# Endpoint to delete an FAQ by ID
@faq_router.delete("/faq/{faq_id}")
async def delete_faq(faq_id: str):
    try:
        # Construct the S3 key using the FAQ ID
        s3_json_key = f"faqs/{faq_id}.json"

        # Check if the file exists before attempting to delete it
        try:
            s3.head_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)
        except s3.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="FAQ not found")

        # Delete the FAQ from S3
        s3.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_json_key)

        return {"message": f"FAQ with ID {faq_id} deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete FAQ: {str(e)}")
