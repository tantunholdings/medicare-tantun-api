from fastapi import APIRouter, HTTPException, Form, Depends, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import EmailStr
from boto3 import client, exceptions

# Initialize the SES client and Limiter
ses_client = client("ses", region_name="us-east-1") 
limiter = Limiter(key_func=get_remote_address)

contact_router = APIRouter()

# Rate limit: Max 5 requests per minute per IP
@contact_router.post("/contact-us")
@limiter.limit("5/minute")
async def contact_us(
    request: Request,
    name: str = Form(...),
    email: EmailStr = Form(...),
    message: str = Form(...),
):
    try:
        # Validate input length to avoid spamming
        if len(message) > 1000:
            raise HTTPException(status_code=400, detail="Message is too long")

        # Send email via AWS SES
        response = ses_client.send_email(
            Source="gennadiyshnayderman@gmail.com",  # Verified SES email
            Destination={
                "ToAddresses": ["gennadiyshnayderman@gmail.com"]  # Admin or support email
            },
            Message={
                "Subject": {"Data": f"New Contact Us Message from {name}"},
                "Body": {
                    "Text": {
                        "Data": f"Name: {name}\nEmail: {email}\nMessage:\n{message}"
                    }
                },
            },
        )
        return JSONResponse(
            status_code=200,
            content={"message": "Email sent successfully", "message_id": response["MessageId"]},
        )

    except exceptions.Boto3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

