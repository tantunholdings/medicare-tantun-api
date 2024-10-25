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

SYSTEM_ROLE  ="You are a helpful and knowledgeable assistant for a Medicare insurance agency. Your goal is to answer questions specifically related to Medicare, such as plan options, coverage details (including doctors, prescriptions, and dental), and enrollment steps. Politely redirect users who ask unrelated questions by explaining that your expertise is focused on Medicare. To ensure a balanced interaction, answer a user's Medicare-related question no more than once. If a user repeats the same question or asks for the same information, politely remind them that you've already provided an answer, and encourage them to contact our team for further clarification or personalized support.  In case users want to enroll into medicare or plans they should contact our team. Always provide clear, concise information, and encourage users to contact our professionals when more specific help is needed."

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
    message_history = [{"role": "system", "content": SYSTEM_ROLE}]
    
    previous_message = ""
    if previous_messages:
        try:
            previous_messages = json.loads(previous_messages)
            for message in previous_messages:
                if message['isFromBackend']:
                    message_history.append({"role": "assistant", "content": message['text']})
                else:
                    message_history.append({"role": "user", "content": message['text']})
                
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid format for previous messages.")
        
    # Process the file if it's uploaded

    if files and len(files) > 0:
        content = [{'type': 'text', 'text': question}]
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
                else:
                    raise HTTPException(status_code=400, detail="Only image files are allowed.")
            except NoCredentialsError:
                raise HTTPException(status_code=500, detail="AWS credentials not found.")
            except Exception as e:
                print(f"Error uploading to S3: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error uploading to S3: {str(e)}")
            
            if s3_url:
                content.append({
                            "type": "image_url",
                            "image_url": {
                                "url":s3_url }
                        })
                
        message_history.append({"role": "user", "content": content})
      
    else:
        message_history.append({"role": "user", "content": question})    
    
    print(message_history)
    try:
        # Send the request to OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=message_history,
        )
        print(f"message_history: {message_history}")
        response_text = response.choices[0].message.content
        
        # print(response_text)

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
            "previous_messages": previous_message,
            "is_valid": True
        })

    except asyncio.CancelledError:
        raise HTTPException(status_code=500, detail="Request was cancelled.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
