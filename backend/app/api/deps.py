from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != settings.API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
