from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from typing import Optional

# Define your FastAPI router
auth_router = APIRouter()

# AWS Cognito configurations
AWS_REGION = "us-east-1"
USER_POOL_ID = "us-east-1_BLvT00Vuc"
CLIENT_ID = "4fbts6s8gikqt541msvqo13n2d"

# Initialize the Cognito client
cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)

# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models for data validation
class Token(BaseModel):
    access_token: Optional[str]  # Change to Optional
    token_type: Optional[str]     # Change to Optional
    challenge_name: Optional[str] = None  # Include challenge name
    session: Optional[str] = None  # Include session for password reset

@auth_router.post("/token", response_model=Token)
async def login_for_access_token(username: str = Query(...), password: str = Query(...)):
    try:
        print(f"Logging in user: {username}")
        response = cognito_client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            ClientId=CLIENT_ID,
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
            }
        )
        print(response)
        if 'ChallengeName' in response and response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
            return {
                "access_token": None,
                "token_type": None,
                "challenge_name": "NEW_PASSWORD_REQUIRED",
                "session": response['Session']
            }
        
        access_token = response['AuthenticationResult']['AccessToken']
        return {"access_token": access_token, "token_type": "Bearer", "challenge_name": None, "session": None}

    except ClientError as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))



# Endpoint to handle new password
@auth_router.post("/new-password")
async def set_new_password(
    username: str = Query(...),
    new_password: str = Query(...),
    session: str = Query(...)
):
    try:
        response = cognito_client.respond_to_auth_challenge(
            ClientId=CLIENT_ID,
            ChallengeName='NEW_PASSWORD_REQUIRED',
            Session=session,
            ChallengeResponses={
                'NEW_PASSWORD': new_password,
                'USERNAME': username,
            }
        )
        return {"message": "Password updated successfully."}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Token validation route
@auth_router.get("/auth/validate")
async def validate_token(token: str = Depends(oauth2_scheme)):
    try:
        response = cognito_client.get_user(
            AccessToken=token
        )
        username = response['Username']
        return {"authenticated": True, "user": username}

    except ClientError as e:
        raise HTTPException(status_code=401, detail="Token validation failed: " + str(e))
