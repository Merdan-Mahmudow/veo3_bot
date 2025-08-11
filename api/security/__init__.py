from fastapi import Header, HTTPException, status
from config import ENV
env = ENV()
API_KEY = env.bot_api_token

async def require_bot_service(x_api_key: str | None = Header(None)):
    if not API_KEY:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="API key not configured")
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service key")
    return True