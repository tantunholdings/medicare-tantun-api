import boto3
import json
import redis
from fastapi import HTTPException

# AWS S3 Configuration
S3_BUCKET_NAME = "medicare-blogs"
S3_REGION = "us-east-1"
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
)

# Redis Configuration
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)  # Adjust host/port/db as needed

# Utility function to download an object from S3 or Redis
def download_object(file_key: str, skip_cache : bool = False, s3_bucket_name: str = S3_BUCKET_NAME) -> dict:
    try:
        if not skip_cache:
            # Check if the object is cached in Redis
            cached_data = redis_client.get(file_key)
            if cached_data:
                print(f"FAQ {file_key} found in Redis cache.")
                return json.loads(cached_data)

        # If not cached, fetch it from S3
        print(f"FAQ {file_key} not found in Redis. Fetching from S3.")
        s3_object = s3.get_object(Bucket=s3_bucket_name, Key=file_key)
        faq_data = json.loads(s3_object['Body'].read().decode('utf-8'))

        # Store the object in Redis for future requests (with an expiration time, e.g., 1 hour)
        redis_client.setex(file_key, 3600, json.dumps(faq_data))  # Cache for 3600 seconds (1 hour)

        return faq_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download object: {str(e)}")


def get_s3_client():
    return s3
