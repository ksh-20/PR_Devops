from requests.auth import HTTPBasicAuth
import jwt
from datetime import datetime, timedelta, UTC
from fastapi import HTTPException, Header

from core.config import pat
from core.config import secret, algorithm, expiry


auth = HTTPBasicAuth("", pat)

def create_access_token(data: dict):
    payload = data.copy()

    expire = datetime.now(UTC) + timedelta(minutes=expiry)

    payload.update({"exp": expire})

    token = jwt.encode(payload, secret,algorithm=algorithm)

    return token


def verify_token(token):
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token Expired"
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Token"
        )
    
def get_current_user(authorization):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.split(" ")[1]

    return verify_token(token)