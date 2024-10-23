import os
import json
import boto3
from botocore.exceptions import NoCredentialsError
from fastapi import  APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
import asyncio
from openai import OpenAI


gpt_router = APIRouter()

# Define a system role for the OpenAI API to answer user prompts

SYSTEM_ROLE  ="You are a medicare insurance consultant.  Ask questions one at a time. You should ask no more than 3 questions and announce that process to the client. The questions should help narrow down the choices and plans. The most important parameters are network of doctors and prescriptions. Suggest only low costs plans and don’t ask about budget preferences . In your final recommendations write at least 3 providers add our phone number: 910345678 to consult our tantun brokers for more detailed information."

# Load your OpenAI API key from environment variables
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    
)

# S3 configuration
S3_BUCKET_NAME = "medicare-blogs"
S3_REGION = "us-east-1"


# Initialize the S3 client
s3_client = boto3.client(
    "s3",
    region_name=S3_REGION,
)

@gpt_router.post("/ask-question")
async def ask_question(
    question: str = Form(...),
    previous_messages: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None)
):
    
    
    messages = [{"role": "system", "content": SYSTEM_ROLE}]

    # Add previous messages to the API call if they exist
    if previous_messages:
        try:
            previous_messages = json.loads(previous_messages)
            for message in previous_messages:
                # Assuming each 'message' contains 'role' and 'text'
                messages.append({"role": message['role'], "content": message['text']})
                
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid format for previous messages.")
        
    messages.append({"role": "user", "content": question})  
    
    
    # Process the uploaded files if it's uploaded (images only)
    
    if files and len(files) > 0:
        for file in files:
            s3_url = None
            try:
                if file.content_type.startswith("image/"):
                    # Upload the file to S3
                    s3_file_key = f"chat-images/{file.filename}"  # Define where to store the file
                    s3_client.upload_fileobj(file.file, S3_BUCKET_NAME, s3_file_key)
                    
                    # Generate a pre-signed URL for the uploaded file
                    s3_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_file_key},
                        ExpiresIn=3600  # URL valid for 1 hour
                    )
                    
                    print(f"Image uploaded successfully: {s3_url}")
                     
                    # Append the image URL to content
                    messages.append({
                        "role":"user",
                        "content":{
                            "type": "image_url",
                            "image_url": s3_url
                        }
                        
                    })


                else:
                    raise HTTPException(status_code=400, detail="Only image files are allowed.")
            except NoCredentialsError:
                raise HTTPException(status_code=500, detail="AWS credentials not found.")
            except Exception as e:
                print(f"Error uploading to S3: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error uploading to S3: {str(e)}")
     
    
  
    print(messages)
    try:
        # Send the request to OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        
        response_text = response.choices[0].message.content
        
        print(response_text)

        # Check if the response indicates an invalid question
        if "Invalid question" in response_text:
            print("Invalid question detected.")
            return JSONResponse(content={
                "message": "Invalid question. Please ask a question related to medical insurance.",
                "question": question,
                "is_valid": False
            })

        return JSONResponse(content={
            "message": "Your question has been processed successfully.",
            "question": question,
            "response_from_openai": response_text,
            "previous_messages": previous_messages,
            "is_valid": True
        })

    except asyncio.CancelledError:
        raise HTTPException(status_code=500, detail="Request was cancelled.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
