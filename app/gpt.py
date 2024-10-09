import os
import asyncio
from openai import OpenAI
from fastapi import FastAPI, APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from typing import Optional
import json

app = FastAPI()

gpt_router = APIRouter()

# Define a fixed prompt for validating questions
VALIDATION_PROMPT = """
This is a medical insurance blog application. Ensure that the following question and additional file content (if applicable) are relevant to medical insurance topics, such as health coverage, claims, policies, or any other health services related to insurance. If the question is not relevant, respond with an error message saying "Invalid question. Please ask a question related to medical insurance. Also answer greetings such as Hello with a polite message.".
"""

# Load your OpenAI API key from environment variables or another source
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

@gpt_router.post("/ask-question")
async def ask_question(
    question: str = Form(...),
    previous_messages: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)  # File is optional here
):
    # Parse the previous messages if they are provided, handle empty or missing cases
    previous_message = ""
    if previous_messages:
        try:
            previous_messages = json.loads(previous_messages)
            for message in previous_messages:
                if message.get("isFromBackend"):
                    previous_message += f"ChatGPT: {message['text']}\n"
                else:
                    previous_message += f"User: {message['text']}\n"
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid format for previous messages.")

    # Initialize an empty file content placeholder
    file_content = ""

    # Process the file if it's uploaded (only if it's not None)
    if file is not None:
        try:
            file_bytes = await file.read()  # Async file read
            file_content = file_bytes.decode('utf-8')
        except asyncio.CancelledError:
            # Handle task cancellation during file read
            raise HTTPException(status_code=500, detail="File read was cancelled.")
        except Exception as e:
            raise HTTPException(status_code=400, detail="Unable to read the file. Ensure it's a valid text file.")

    # Construct the final prompt for OpenAI API, including previous messages
    final_prompt = f"{VALIDATION_PROMPT} \nPrevious conversation: {previous_message}\nUser question: '{question}'"

    # If there's a file, append the content to the prompt
    if file_content:
        final_prompt += f"\n\nFile content:\n{file_content}"

    try:
        # Send the request to OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": final_prompt,
                }
            ],
        )
        
        # Extract the response text from OpenAI API
        response_text = response.choices[0].message.content

        # Check if the response indicates an invalid question
        if "Invalid question" in response_text:
            return JSONResponse(content={
                "message": "Invalid question. Please ask a question related to medical insurance.",
                "question": question,
                "is_valid": False
            })

        # Return the response and any file info
        return JSONResponse(content={
            "message": "Your question has been processed successfully.",
            "question": question,
            "response_from_openai": response_text,
            "file_info": {
                "filename": file.filename if file else None,
                "content": file_content if file else None
            },
            "previous_messages": previous_message,  # Include previous conversation for continuity
            "is_valid": True
        })

    except asyncio.CancelledError:
        # Handle task cancellation when querying OpenAI API
        raise HTTPException(status_code=500, detail="Request was cancelled.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


# Lifespan event handlers to gracefully handle shutdowns
@app.on_event("startup")
async def startup_event():
    try:
        # Perform any startup logic here
        print("Starting up...")
    except asyncio.CancelledError:
        # Handle task cancellation during startup
        pass

@app.on_event("shutdown")
async def shutdown_event():
    try:
        # Perform any shutdown logic here
        print("Shutting down...")
    except asyncio.CancelledError:
        # Handle task cancellation during shutdown
        pass

# Add the router to the main FastAPI app
app.include_router(gpt_router)
