from models.handle_logging import get_logging_conf
logging = get_logging_conf()
from fastapi import APIRouter, HTTPException

from core.auth import create_access_token
from core.config import username, password
from schemas.login import LoginRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Mock Login
@router.post("/login")
async def login(credentials: LoginRequest):
    logger.info("[AuthRoutes] Login attempt for user: %s", credentials.username)
    if (credentials.username != username or credentials.password != password):
        logger.warning("[AuthRoutes] Failed login attempt for user: %s", credentials.username)
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = create_access_token({"username": credentials.username})
    logger.info("[AuthRoutes] Login successful for user: %s", credentials.username)
    return {
        "access_token": token,
        "token_type": "bearer"
    }
