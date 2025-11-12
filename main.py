from fastapi import FastAPI, Request, Response, HTTPException, Header
from pydantic import BaseModel
import time
import os
from typing import Optional
from redis import asyncio as aioredis
from core.rate_limiter import RateLimiter
from core.config import ConfigManager
from core.health import SystemHealthManager, SystemHealth
from middleware.rate_limiter_mw import RateLimiterMiddleware

app = FastAPI()

# Admin authentication token (load from environment variable)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin_secret_token_change_in_production")

# Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class HealthStatusUpdate(BaseModel):
    status: SystemHealth

@app.on_event("startup")
async def startup_event():
    # Initialize shared Redis client with retry logic
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            app.state.redis = await aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
            # Test connection
            await app.state.redis.ping()
            print(f"[INIT] Redis connected successfully at {REDIS_URL} ✅")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[INIT] Redis connection attempt {attempt + 1} failed: {e}")
                print(f"[INIT] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"[INIT] Failed to connect to Redis after {max_retries} attempts ❌")
                raise
    
    # Initialize config manager
    app.state.config_manager = ConfigManager()
    
    # Initialize system health manager
    app.state.health_manager = SystemHealthManager(app.state.redis)
    
    # Initialize rate limiter with system health awareness
    app.state.rate_limiter = RateLimiter(
        redis_client=app.state.redis,
        config_manager=app.state.config_manager,
        health_manager=app.state.health_manager,
        default_tier="free"
    )
    
    # Set initial system health to NORMAL
    await app.state.health_manager.set_health(SystemHealth.NORMAL)
    
    print("[INIT] Components initialized ✅")
    print("[INIT] System health set to NORMAL ✅")

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
    return {"message": "API is running!", "timestamp": time.time()}

@app.get("/health")
async def health():
    health = await app.state.health_manager.get_health()
    return {
        "status": "healthy",
        "redis": "connected",
        "health": health.value
    }

@app.post("/system/health")
async def update_health(
    health_update: HealthStatusUpdate,
    x_admin_token: Optional[str] = Header(None)
):
    """
    Protected admin endpoint to update system health status.
    
    Usage:
        curl -X POST http://localhost:8000/system/health \
             -H "Content-Type: application/json" \
             -H "X-Admin-Token: admin_secret_token_change_in_production" \
             -d '{"status": "DEGRADED"}'
    """
    
    # Verify admin token
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    # Update system health
    success = await app.state.health_manager.set_health(health_update.status)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update system health")
    
    print(f"[ADMIN] System health updated to {health_update.status.value} ✅")
    
    return {
        "message": "System health updated successfully",
        "previous_status": (await app.state.health_manager.get_health()).value,
        "new_status": health_update.status.value,
        "timestamp": time.time()
    }

@app.get("/system/health")
async def get_health():
    """
    Public endpoint to check current system health status.
    """
    health = await app.state.health_manager.get_health()
    return {
        "health": health.value,
        "timestamp": time.time()
    }

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify rate limiting is working."""
    return {
        "message": "Request successful!",
        "timestamp": time.time()
    }