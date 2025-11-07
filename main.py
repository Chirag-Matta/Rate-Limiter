from fastapi import FastAPI, Request, Response
import time , asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from typing import Dict
from redis import asyncio as aioredis
from core.rate_limiter import RateLimiter
from core.config import ConfigManager
from middleware.rate_limiter_mw import RateLimiterMiddleware

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Initialize shared Redis client and rate limiter
    app.state.redis = await aioredis.from_url("redis://localhost")
    app.state.rate_limiter = RateLimiter(app.state.redis)
    print("[INIT] Redis connected & middleware added ✅")
    
app.add_middleware(RateLimiterMiddleware, rate_limiter=None, config_manager=None)


@app.on_event("shutdown")
async def shutdown_event():
    redis = app.state.redis
    await redis.close()
    await redis.connection_pool.disconnect()
    print("[SHUTDOWN] Redis connection closed ✅")



@app.get("/")
async def root():
    return {"message": "main endpoint working!"}
