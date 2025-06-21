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

logger = logging.getLogger(__name__)

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
    "http://127.0.0.1:3001",
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

# Create Socket.IO server with enhanced configuration
sio = socketio.AsyncServer(
    cors_allowed_origins=origins,
    async_mode='asgi',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Store active analysis sessions
active_analyses: Dict[str, Dict[str, Any]] = {}

# Socket.IO event handlers
@sio.event
async def connect(sid, environ, auth=None):
    """Handle client connection."""
    logger.info(f"✅ Client {sid} connected")
    await sio.emit('notification', {
        'type': 'success',
        'message': 'Connected to AI Code Reviewer'
    }, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    logger.info(f"🔌 Client {sid} disconnected")
    
    # Cancel any active analyses for this client
    analyses_to_cancel = []
    for analysis_id, analysis_data in active_analyses.items():
        if analysis_data.get('client_id') == sid:
            analyses_to_cancel.append(analysis_id)
    
    for analysis_id in analyses_to_cancel:
        await cancel_analysis_internal(analysis_id, sid)

@sio.event
async def start_analysis(sid, data):
    """Handle code analysis request via WebSocket."""
    try:
        analysis_id = data.get('analysisId')
        logger.info(f"🚀 Starting analysis for client {sid}: {analysis_id}")
        
        # Extract analysis parameters
        code = data.get('code')
        language = data.get('language', 'python')
        filename = data.get('filename')
        analysis_type = data.get('analysis_type', 'comprehensive')
        severity_threshold = data.get('severity_threshold', 'low')
        include_suggestions = data.get('include_suggestions', True)
        include_explanations = data.get('include_explanations', True)
        config = data.get('config')
        
        # Validate required fields
        if not code or not analysis_id:
            await sio.emit('analysis_error', {
                'analysisId': analysis_id or 'unknown',
                'error': 'Code and analysisId are required'
            }, room=sid)
            return
        
        # Store analysis session
        active_analyses[analysis_id] = {
            'client_id': sid,
            'data': data,
            'status': 'running',
            'task': None
        }
        
        # Create async task for analysis
        task = asyncio.create_task(run_analysis_with_progress(
            analysis_id, sid, code, language, filename, 
            analysis_type, severity_threshold, include_suggestions, 
            include_explanations, config
        ))
        
        active_analyses[analysis_id]['task'] = task
        
        # Send initial notification
        await sio.emit('notification', {
            'type': 'info',
            'message': f'Analysis {analysis_id[:8]}... started'
        }, room=sid)
        
    except Exception as e:
        logger.error(f"❌ Error starting analysis for client {sid}: {str(e)}")
        await sio.emit('analysis_error', {
            'analysisId': data.get('analysisId', 'unknown'),
            'error': str(e)
        }, room=sid)

async def run_analysis_with_progress(
    analysis_id: str, sid: str, code: str, language: str, 
    filename: str, analysis_type: str, severity_threshold: str,
    include_suggestions: bool, include_explanations: bool, config: Any
):
    """Run analysis with detailed progress updates."""
    try:
        # Progress stages with more realistic timing
        stages = [
            ("Initializing analysis", "initialization", 5),
            ("Loading AI model", "model_loading", 15),
            ("Parsing code structure", "parsing", 25),
            ("Running static analysis", "static_analysis", 45),
            ("AI-powered bug detection", "ai_analysis", 65),
            ("Security vulnerability scan", "security_scan", 80),
            ("Generating suggestions", "suggestions", 90),
            ("Finalizing results", "finalization", 95)
        ]
        
        for stage_name, stage_key, progress in stages:
            # Check if analysis was cancelled
            if analysis_id not in active_analyses:
                logger.info(f"🛑 Analysis {analysis_id} was cancelled during {stage_name}")
                return
            
            # Send progress update
            await sio.emit('analysis_progress', {
                'analysisId': analysis_id,
                'progress': progress,
                'message': stage_name,
                'stage': stage_key
            }, room=sid)
            
            # Simulate processing time based on analysis type
            if analysis_type == 'quick':
                await asyncio.sleep(0.3)
            elif analysis_type == 'comprehensive':
                await asyncio.sleep(0.8)
            else:  # custom
                await asyncio.sleep(0.5)
            
            # Special handling for AI model loading
            if stage_key == "model_loading":
                if not ai_analyzer.model_loaded:
                    await sio.emit('analysis_progress', {
                        'analysisId': analysis_id,
                        'progress': 12,
                        'message': 'Loading AI model (this may take a moment)...',
                        'stage': stage_key
                    }, room=sid)
                    
                    ai_analyzer.load_model()
                    
                    if ai_analyzer.model_loaded:
                        await sio.emit('analysis_progress', {
                            'analysisId': analysis_id,
                            'progress': 15,
                            'message': 'AI model loaded successfully',
                            'stage': stage_key
                        }, room=sid)
                    else:
                        await sio.emit('analysis_error', {
                            'analysisId': analysis_id,
                            'error': 'Failed to load AI model'
                        }, room=sid)
                        return
        
        # Create analysis request
        request = CodeAnalysisRequest(
            code=code,
            language=language,
            filename=filename,
            analysis_type=analysis_type,
            include_suggestions=include_suggestions,
            include_explanations=include_explanations,
            severity_threshold=severity_threshold
        )
        
        # Perform the actual analysis
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'progress': 98,
            'message': 'Running AI analysis...',
            'stage': 'ai_processing'
        }, room=sid)
        
        result = await ai_analyzer.analyze_code(request)
        
        # Final progress update
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'progress': 100,
            'message': 'Analysis completed successfully',
            'stage': 'completed'
        }, room=sid)
        
        # Send completion with result
        await sio.emit('analysis_complete', {
            'analysisId': analysis_id,
            'result': result.dict()
        }, room=sid)
        
        # Send success notification
        await sio.emit('notification', {
            'type': 'success',
            'message': f'Analysis {analysis_id[:8]}... completed successfully'
        }, room=sid)
        
        logger.info(f"✅ Analysis completed for client {sid}: {analysis_id}")
        
        # Clean up
        if analysis_id in active_analyses:
            del active_analyses[analysis_id]
            
    except asyncio.CancelledError:
        logger.info(f"🛑 Analysis {analysis_id} was cancelled")
        if analysis_id in active_analyses:
            del active_analyses[analysis_id]
        raise
        
    except Exception as e:
        logger.error(f"❌ Analysis error for {analysis_id}: {str(e)}")
        await sio.emit('analysis_error', {
            'analysisId': analysis_id,
            'error': str(e)
        }, room=sid)
        
        await sio.emit('notification', {
            'type': 'error',
            'message': f'Analysis {analysis_id[:8]}... failed: {str(e)}'
        }, room=sid)
        
        if analysis_id in active_analyses:
            del active_analyses[analysis_id]

@sio.event
async def cancel_analysis(sid, data):
    """Handle analysis cancellation."""
    analysis_id = data.get('analysisId')
    if not analysis_id:
        return
    
    await cancel_analysis_internal(analysis_id, sid)

async def cancel_analysis_internal(analysis_id: str, sid: str):
    """Internal function to cancel analysis."""
    if analysis_id in active_analyses:
        analysis_data = active_analyses[analysis_id]
        
        # Cancel the task if it exists
        task = analysis_data.get('task')
        if task and not task.done():
            task.cancel()
            logger.info(f"🛑 Cancelled analysis task {analysis_id}")
        
        # Remove from active analyses
        del active_analyses[analysis_id]
        
        # Notify client
        await sio.emit('analysis_cancelled', {
            'analysisId': analysis_id
        }, room=sid)
        
        await sio.emit('notification', {
            'type': 'warning',
            'message': f'Analysis {analysis_id[:8]}... cancelled'
        }, room=sid)

# Mount Socket.IO to FastAPI
socket_app = socketio.ASGIApp(sio, app)

# Include routers
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("🚀 Starting AI Code Review Assistant...")
    
    # Ensure AI model is loaded
    if not ai_analyzer.model_loaded:
        logger.info("🤖 Loading AI model on startup...")
        try:
            ai_analyzer.load_model()
            if ai_analyzer.model_loaded:
                logger.info("✅ AI model loaded successfully")
            else:
                logger.warning("⚠️ Failed to load AI model on startup")
        except Exception as e:
            logger.error(f"❌ Error loading AI model: {e}")
    
    logger.info("🔌 Socket.IO server initialized and ready for connections")
    logger.info(f"📡 WebSocket endpoint: ws://localhost:8000/socket.io/")
    logger.info(f"📖 API documentation: http://localhost:8000/docs")

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

@app.get("/api/health")
async def api_health_check():
    """Alternative health check endpoint for API."""
    return {
        "status": "healthy", 
        "websocket": "enabled",
        "ai_model_loaded": ai_analyzer.model_loaded,
        "active_analyses": len(active_analyses)
    }

@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with basic API information."""
    return {
        "message": "Welcome to AI Code Review Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "websocket": "Socket.IO enabled on /socket.io/",
        "features": [
            "Real-time code analysis",
            "WebSocket support",
            "AI-powered bug detection",
            "Security vulnerability scanning",
            "Code quality assessment"
        ]
    }

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Export the socket app for ASGI server
if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting server...")
    # Use socket_app instead of app to enable Socket.IO
    uvicorn.run(
        socket_app,  # Changed from app to socket_app
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )