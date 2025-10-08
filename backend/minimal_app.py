#!/usr/bin/env python3
"""
MINIMAL TEST APPLICATION - FOR DEVELOPMENT/TESTING ONLY

This is a minimal FastAPI app with only basic endpoints for testing purposes.
DO NOT USE IN PRODUCTION - Use app.py for the full application.

This app only provides:
- /health - Health check
- /api/test - Basic test endpoint  
- /api/version - Version info

Missing all the production endpoints that the frontend expects:
- /api/age-groups, /api/divisions, /api/seasons, /api/table, etc.
- Authentication endpoints
- Database integration
- Security monitoring

To run the full application, use: uvicorn app:app
"""

import os
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
load_dotenv('.env.local', override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Missing Table Sports League API - MINIMAL TEST VERSION", 
    version="1.4.0",
    description="⚠️  MINIMAL TEST VERSION - Use app.py for full functionality"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.4.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "warning": "This is a minimal test version - use app.py for full functionality"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Missing Table Sports League API - MINIMAL TEST VERSION",
        "version": "1.4.0",
        "docs": "/docs",
        "health": "/health",
        "warning": "⚠️  This is a minimal test version - use app.py for full functionality",
        "missing_endpoints": [
            "/api/age-groups", "/api/divisions", "/api/seasons", "/api/table",
            "/api/auth/*", "/api/teams", "/api/games", "and many more..."
        ]
    }

# Basic API endpoints
@app.get("/api/test")
async def test_endpoint():
    """Test endpoint"""
    return {
        "message": "API is working!",
        "timestamp": datetime.now().isoformat(),
        "note": "This is the minimal test version - many endpoints are missing"
    }

@app.get("/api/version")
async def get_version():
    """Get API version"""
    return {
        "version": "1.4.0",
        "build_date": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "type": "minimal-test-version"
    }

if __name__ == "__main__":
    import uvicorn
    print("⚠️  WARNING: Running minimal test version")
    print("   For full functionality, use: uvicorn app:app")
    uvicorn.run(
        "minimal_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )