from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_token
from app.schemas.market import MarketCoverageRequest, MarketCoverageResponse
from app.services.market_coverage import compute_market_coverage

router = APIRouter()


@router.post("/coverage", dependencies=[Depends(require_token)])
async def market_coverage(payload: MarketCoverageRequest, db: Session = Depends(get_db)):
    data = compute_market_coverage(db, payload)
    return MarketCoverageResponse(**data).model_dump()
