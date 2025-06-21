from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import socketio
import os
import logging
import asyncio
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

# Configure CORS origins
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

# Create Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins=origins,
    async_mode='asgi',
    logger=True,
    engineio_logger=True
)

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    logging.info(f"Client {sid} connected")
    await sio.emit('connected', {'message': 'Connected to AI Code Reviewer'}, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    logging.info(f"Client {sid} disconnected")

@sio.event
async def start_analysis(sid, data):
    """Handle code analysis request via WebSocket."""
    try:
        logging.info(f"Starting analysis for client {sid}: {data.get('analysisId')}")
        
        # Extract analysis parameters
        analysis_id = data.get('analysisId')
        code = data.get('code')
        language = data.get('language', 'python')
        filename = data.get('filename')
        analysis_type = data.get('analysis_type', 'comprehensive')
        severity_threshold = data.get('severity_threshold', 'low')
        
        # Validate required fields
        if not code or not analysis_id:
            await sio.emit('analysis_error', {
                'analysisId': analysis_id,
                'error': 'Code and analysisId are required'
            }, room=sid)
            return
        
        # Send progress updates
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'tool': 'AI Analyzer',
            'status': 'running',
            'progress': 10,
            'message': 'Initializing analysis...',
            'overallStatus': 'initializing'
        }, room=sid)
        
        # Create analysis request
        request = CodeAnalysisRequest(
            code=code,
            language=language,
            filename=filename,
            analysis_type=analysis_type,
            include_suggestions=True,
            include_explanations=True,
            severity_threshold=severity_threshold
        )
        
        # Send progress update
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'tool': 'AI Analyzer',
            'status': 'running',
            'progress': 30,
            'message': 'Loading AI model...',
            'overallStatus': 'analyzing'
        }, room=sid)
        
        # Ensure AI model is loaded
        if not ai_analyzer.model_loaded:
            ai_analyzer.load_model()
        
        # Send progress update
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'tool': 'AI Analyzer',
            'status': 'running',
            'progress': 50,
            'message': 'Analyzing code...',
            'overallStatus': 'analyzing'
        }, room=sid)
        
        # Perform analysis
        result = await ai_analyzer.analyze_code(request)
        
        # Send progress update
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'tool': 'AI Analyzer',
            'status': 'running',
            'progress': 90,
            'message': 'Finalizing results...',
            'overallStatus': 'analyzing'
        }, room=sid)
        
        # Send completion
        await sio.emit('analysis_complete', {
            'analysisId': analysis_id,
            'result': result.dict()
        }, room=sid)
        
        # Final progress update
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'tool': 'AI Analyzer',
            'status': 'completed',
            'progress': 100,
            'message': 'Analysis completed successfully',
            'overallStatus': 'completed'
        }, room=sid)
        
        logging.info(f"Analysis completed for client {sid}: {analysis_id}")
        
    except Exception as e:
        logging.error(f"Analysis error for client {sid}: {str(e)}")
        await sio.emit('analysis_error', {
            'analysisId': data.get('analysisId'),
            'error': str(e)
        }, room=sid)

@sio.event
async def cancel_analysis(sid, data):
    """Handle analysis cancellation."""
    analysis_id = data.get('analysisId')
    logging.info(f"Analysis cancelled for client {sid}: {analysis_id}")
    
    await sio.emit('analysis_cancelled', {
        'analysisId': analysis_id,
        'message': 'Analysis cancelled successfully'
    }, room=sid)

# Mount Socket.IO to FastAPI
socket_app = socketio.ASGIApp(sio, app)

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
    
    logging.info("Socket.IO server initialized and ready for connections")

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint to verify the API is running."""
    # Include AI model status in health check
    ai_status = "loaded" if ai_analyzer.model_loaded else "not loaded"
    
    return HealthResponse(
        status="healthy",
        message=f"AI Code Review Assistant is running with WebSocket support",
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
        "health": "/health",
        "websocket": "Socket.IO enabled on /socket.io/"
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

# Export the socket app for ASGI server
if __name__ == "__main__":
    import uvicorn
    # Use socket_app instead of app to enable Socket.IO
    uvicorn.run(
        socket_app,  # Changed from app to socket_app
        host="0.0.0.0",
        port=8000,
        reload=True
    )