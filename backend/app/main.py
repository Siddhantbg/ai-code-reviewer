from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
from typing import Dict, Any

from app.routers import analysis
from app.models.requests import CodeAnalysisRequest
from app.models.responses import HealthResponse, CodeAnalysisResponse
from app.services.ai_service import ai_analyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize FastAPI app
app = FastAPI(
    title="AI Code Review Assistant",
    description="An AI-powered code review assistant that analyzes code for bugs, improvements, and security issues",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
origins = [
    "http://localhost:3000",  # Next.js default
    "http://127.0.0.1:3000",
    "http://localhost:3001",  # Alternative port
]

# Add CORS origins from environment if available
cors_origins = os.getenv("CORS_ORIGINS", "")
if cors_origins:
    origins.extend(cors_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    # Ensure AI model is loaded
    if not ai_analyzer.model_loaded:
        logging.info("Loading AI model on startup...")
        ai_analyzer.load_model()
        if ai_analyzer.model_loaded:
            logging.info("AI model loaded successfully")
        else:
            logging.warning("Failed to load AI model on startup")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint to verify the API is running."""
    # Include AI model status in health check
    ai_status = "loaded" if ai_analyzer.model_loaded else "not loaded"
    
    return HealthResponse(
        status="healthy",
        message=f"AI Code Review Assistant is running",
        version="1.0.0",
        ai_model_loaded=ai_analyzer.model_loaded,
        ai_model_path="./models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf"
    )


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with basic API information."""
    return {
        "message": "Welcome to AI Code Review Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )