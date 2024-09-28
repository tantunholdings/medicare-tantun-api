from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from datetime import datetime, timezone

# Define your FastAPI router
auth_router = APIRouter()

# Secret key and algorithm
SECRET_KEY = "your_secret_key_here"  # Use a strong key from environment variables
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory database for demo purposes
users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("password"),
    }
}

# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Pydantic models for data validation
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str


# Helper functions for password hashing and token generation
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    user = db.get(username)
    return user

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user or not verify_password(password, user["hashed_password"]):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Login route to issue JWT
@auth_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=400, detail="Incorrect username or password"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# Token validation route
@auth_router.get("/auth/validate")
async def validate_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Validate the 'sub' claim (user identity)
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Token does not contain a valid subject (sub)")

        exp = payload.get("exp")
        if not exp or datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Token has expired")

        return {"authenticated": True, "user": username}

    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=401, detail="Token validation failed")
