from fastapi import FastAPI, Request, Response
import time
from redis import asyncio as aioredis
from core.rate_limiter import RateLimiter
from core.config import ConfigManager
from middleware.rate_limiter_mw import RateLimiterMiddleware

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Initialize shared Redis client, config manager, and rate limiter
    app.state.redis = await aioredis.from_url("redis://localhost")
    app.state.config_manager = ConfigManager()
    app.state.rate_limiter = RateLimiter(
        redis_client=app.state.redis,
        config_manager=app.state.config_manager,
        default_tier="free"
    )
    print("[INIT] Redis connected & components initialized ✅")

# Add middleware after defining app
app.add_middleware(RateLimiterMiddleware)

@app.on_event("shutdown")
async def shutdown_event():
    redis = app.state.redis
    await redis.close()
    await redis.connection_pool.disconnect()
    print("[SHUTDOWN] Redis connection closed ✅")

@app.get("/")
async def root():
    return {"message": "main endpoint working!"}

@app.get("/health")
async def health():
    return {"status": "healthy", "redis": "connected"}