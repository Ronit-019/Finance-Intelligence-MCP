from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

from main import get_pool
from src.auth import create_user, authenticate_user, get_user_from_token


load_dotenv()

app = FastAPI(
    title="Finance Intelligence API",
    description="Authentication and application API for Finance Intelligence MCP",
    version="1.0.0"
)

security = HTTPBearer()


# ============================================================
# REQUEST MODELS
# ============================================================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    username: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ============================================================
# AUTHENTICATION DEPENDENCY
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Extract the Bearer token and resolve the authenticated user.
    """

    token = credentials.credentials

    db_pool = await get_pool()

    async with db_pool.acquire() as conn:

        user = await get_user_from_token(
            conn,
            token
        )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token."
        )

    return user


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Finance Intelligence API",
        "version": "1.0.0"
    }


# ============================================================
# SIGNUP
# ============================================================

@app.post("/auth/signup")
async def signup(request: SignupRequest):

    db_pool = await get_pool()

    async with db_pool.acquire() as conn:

        try:

            result = await create_user(
                conn=conn,
                email=request.email,
                password=request.password,
                username=request.username
            )

        except ValueError as e:

            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        except Exception as e:

            # PostgreSQL unique constraint protection
            if "duplicate key" in str(e).lower():

                raise HTTPException(
                    status_code=400,
                    detail="An account with this information already exists."
                )

            raise HTTPException(
                status_code=500,
                detail="Unable to create account."
            )

    return {
        "status": "ok",
        "message": "Account created successfully.",
        "user": {
            "id": result["user_id"],
            "username": result["username"],
            "email": result["email"]
        },
        "token": result["token"]
    }


# ============================================================
# LOGIN
# ============================================================

@app.post("/auth/login")
async def login(request: LoginRequest):

    db_pool = await get_pool()

    async with db_pool.acquire() as conn:

        try:

            result = await authenticate_user(
                conn=conn,
                email=request.email,
                password=request.password
            )

        except ValueError as e:

            raise HTTPException(
                status_code=401,
                detail=str(e)
            )

        except Exception:

            raise HTTPException(
                status_code=500,
                detail="Unable to authenticate user."
            )

    return {
        "status": "ok",
        "message": "Login successful.",
        "user": {
            "id": result["user_id"],
            "username": result["username"],
            "email": result["email"]
        },
        "token": result["token"]
    }


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/auth/me")
async def me(
    user=Depends(get_current_user)
):

    return {
        "status": "ok",
        "user": user
    }