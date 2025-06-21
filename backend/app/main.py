from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import socketio
import os
import logging
import asyncio
from typing import Dict, Any
import time
from collections import defaultdict

from app.routers import analysis
from app.models.requests import CodeAnalysisRequest
from app.models.responses import HealthResponse, CodeAnalysisResponse
from app.services.ai_service import ai_analyzer
from app.monitoring.resource_monitor import resource_monitor
from app.utils.performance_optimizer import performance_optimizer
from app.middleware.rate_limiter import rate_limiter, rate_limit_middleware

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('socketio_debug.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)
socketio_logger = logging.getLogger('socketio')
engineio_logger = logging.getLogger('engineio')

# Set detailed logging for Socket.IO components
socketio_logger.setLevel(logging.DEBUG)
engineio_logger.setLevel(logging.DEBUG)

# Connection statistics tracking
connection_stats = {
    'total_connections': 0,
    'active_connections': 0,
    'total_disconnections': 0,
    'ping_pong_cycles': defaultdict(int),
    'connection_errors': defaultdict(int),
    'analysis_timeouts': 0,
    'client_info': {},
    'ping_times': defaultdict(list)
}

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

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Create Socket.IO server with enhanced configuration
sio = socketio.AsyncServer(
    cors_allowed_origins=origins,
    async_mode='asgi',
    logger=True,
    engineio_logger=True,
    ping_timeout=120,  # Increased from 60 to 120 seconds
    ping_interval=60,  # Increased from 25 to 60 seconds
    max_http_buffer_size=10**7,  # Increased buffer size
    allow_upgrades=True,
    transports=['websocket', 'polling']  # Explicit transport support
)

# Store active analysis sessions
active_analyses: Dict[str, Dict[str, Any]] = {}

# Socket.IO event handlers
@sio.event
async def connect(sid, environ, auth=None):
    """Handle client connection."""
    connect_time = time.time()
    client_ip = environ.get('REMOTE_ADDR', 'unknown')
    
    # Check rate limiting for connections
    if not rate_limiter.track_connection_attempt(client_ip):
        logger.warning(f"🚫 Connection rejected from {client_ip}: rate limit exceeded")
        return False  # Reject connection
    
    if not rate_limiter.check_websocket_rate_limit(client_ip, 'connect'):
        logger.warning(f"🚫 Connection rejected from {client_ip}: WebSocket rate limit exceeded")
        return False  # Reject connection
    
    client_info = {
        'sid': sid,
        'remote_addr': client_ip,
        'user_agent': environ.get('HTTP_USER_AGENT', 'unknown'),
        'connect_time': connect_time,
        'transport': environ.get('HTTP_UPGRADE', 'polling'),
        'query_params': environ.get('QUERY_STRING', ''),
        'last_ping_time': None,
        'ping_count': 0,
        'pong_count': 0,
        'connection_errors': 0
    }
    
    # Update connection statistics
    connection_stats['total_connections'] += 1
    connection_stats['active_connections'] += 1
    connection_stats['client_info'][sid] = client_info
    
    # Update resource monitor
    resource_monitor.update_connection_count(connection_stats['active_connections'])
    
    logger.info(f"✅ CLIENT_CONNECT: {sid} from {client_info['remote_addr']} via {client_info['transport']}")
    logger.info(f"📊 CONNECTION_STATS: Total={connection_stats['total_connections']}, Active={connection_stats['active_connections']}")
    logger.debug(f"🔍 CLIENT_DETAILS: {sid} - UA: {client_info['user_agent'][:100]}..., Query: {client_info['query_params']}")
    
    # Log Socket.IO server configuration for debugging
    logger.info(f"⚙️ SERVER_CONFIG: ping_timeout=120s, ping_interval=60s, transports=['websocket', 'polling']")
    # Store client info for monitoring
    active_analyses[f"client_{sid}"] = {
        'type': 'client_info',
        'info': client_info
    }
    
    await sio.emit('notification', {
        'type': 'success',
        'message': 'Connected to AI Code Reviewer',
        'server_time': asyncio.get_event_loop().time(),
        'ping_settings': {
            'ping_timeout': 120,
            'ping_interval': 60
        }
    }, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    # Get client info before cleanup
    client_key = f"client_{sid}"
    client_info = connection_stats['client_info'].get(sid, {})
    connect_time = client_info.get('connect_time', 0)
    session_duration = time.time() - connect_time if connect_time else 0
    
    # Update connection statistics
    connection_stats['active_connections'] = max(0, connection_stats['active_connections'] - 1)
    connection_stats['total_disconnections'] += 1
    
    # Update resource monitor
    resource_monitor.update_connection_count(connection_stats['active_connections'])
    
    # Log comprehensive disconnect information
    logger.info(f"🔌 CLIENT_DISCONNECT: {sid} after {session_duration:.1f}s")
    logger.info(f"📊 DISCONNECT_STATS: Active={connection_stats['active_connections']}, Total_Disconnects={connection_stats['total_disconnections']}")
    
    if client_info:
        ping_count = client_info.get('ping_count', 0)
        pong_count = client_info.get('pong_count', 0)
        last_ping = client_info.get('last_ping_time')
        errors = client_info.get('connection_errors', 0)
        
        logger.info(f"📡 PING_STATS: {sid} - Pings: {ping_count}, Pongs: {pong_count}, Last_Ping: {last_ping}, Errors: {errors}")
        
        if last_ping and time.time() - last_ping > 120:
            logger.warning(f"⚠️ STALE_CONNECTION: {sid} - Last ping was {time.time() - last_ping:.1f}s ago (>120s)")
    
    logger.debug(f"🔍 DISCONNECT_DETAILS: {sid} - Transport: {client_info.get('transport', 'unknown')}, IP: {client_info.get('remote_addr', 'unknown')}")
    
    # Cancel any active analyses for this client
    analyses_to_cancel = []
    for analysis_id, analysis_data in active_analyses.items():
        if analysis_data.get('client_id') == sid:
            analyses_to_cancel.append(analysis_id)
    
    for analysis_id in analyses_to_cancel:
        await cancel_analysis_internal(analysis_id, sid)
    
    # Clean up client info
    if client_key in active_analyses:
        del active_analyses[client_key]
    
    # Clean up from connection statistics
    if sid in connection_stats['client_info']:
        del connection_stats['client_info'][sid]
    
    # Clean up ping times
    if sid in connection_stats['ping_times']:
        del connection_stats['ping_times'][sid]

# Enhanced Socket.IO event handlers with comprehensive logging
@sio.event
async def ping(sid):
    """Handle ping from client with detailed logging."""
    current_time = time.time()
    
    # Update client ping statistics
    if sid in connection_stats['client_info']:
        client_info = connection_stats['client_info'][sid]
        client_info['ping_count'] += 1
        client_info['last_ping_time'] = current_time
        
        # Track ping timing
        connection_stats['ping_times'][sid].append(current_time)
        
        # Keep only last 10 ping times for analysis
        if len(connection_stats['ping_times'][sid]) > 10:
            connection_stats['ping_times'][sid] = connection_stats['ping_times'][sid][-10:]
        
        logger.debug(f"📡 PING_RECEIVED: {sid} - Count: {client_info['ping_count']}, Time: {current_time}")
        
        # Calculate ping interval if we have previous pings
        ping_times = connection_stats['ping_times'][sid]
        if len(ping_times) >= 2:
            interval = ping_times[-1] - ping_times[-2]
            logger.debug(f"📊 PING_INTERVAL: {sid} - {interval:.2f}s (expected: ~60s)")
            
            if interval > 75:  # More than 25% over expected 60s interval
                logger.warning(f"⚠️ SLOW_PING: {sid} - Interval {interval:.2f}s is slower than expected")
    
    connection_stats['ping_pong_cycles'][sid] += 1
    
    try:
        await sio.emit('pong', room=sid)
        logger.debug(f"📤 PONG_SENT: {sid}")
    except Exception as e:
        logger.error(f"❌ PONG_SEND_ERROR: {sid} - {str(e)}")
        if sid in connection_stats['client_info']:
            connection_stats['client_info'][sid]['connection_errors'] += 1

@sio.event
async def pong(sid):
    """Handle pong from client with detailed logging."""
    current_time = time.time()
    
    if sid in connection_stats['client_info']:
        client_info = connection_stats['client_info'][sid]
        client_info['pong_count'] += 1
        client_info['last_ping_time'] = current_time
        
        logger.debug(f"📡 PONG_RECEIVED: {sid} - Count: {client_info['pong_count']}, Time: {current_time}")
    
    logger.debug(f"📡 Pong received from client {sid}")

@sio.on('connect_error')
async def connect_error(sid, data):
    """Handle connection errors with detailed logging."""
    error_time = time.time()
    error_type = type(data).__name__ if data else 'Unknown'
    error_msg = str(data) if data else 'No error details'
    
    logger.error(f"❌ CONNECTION_ERROR: {sid} - Type: {error_type}, Details: {error_msg}")
    logger.error(f"🕐 ERROR_TIME: {error_time}, Formatted: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(error_time))}")
    
    # Track error in statistics
    connection_stats['connection_errors'][error_type] += 1
    
    # Update client error count if client exists
    if sid in connection_stats['client_info']:
        connection_stats['client_info'][sid]['connection_errors'] += 1

@sio.on('disconnect')
async def on_disconnect(sid):
    """Additional disconnect logging with reason tracking."""
    disconnect_time = time.time()
    logger.info(f"🔌 DISCONNECT_EVENT: {sid} at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(disconnect_time))}")
    
    # Log client state at disconnect
    if sid in connection_stats['client_info']:
        client_info = connection_stats['client_info'][sid]
        logger.info(f"📊 CLIENT_STATE_AT_DISCONNECT: {sid} - Pings: {client_info.get('ping_count', 0)}, Errors: {client_info.get('connection_errors', 0)}")

# Additional error monitoring
@sio.on('error')
async def on_error(sid, data):
    """Handle general Socket.IO errors."""
    logger.error(f"❌ SOCKETIO_ERROR: {sid} - {data}")
    
    if sid in connection_stats['client_info']:
        connection_stats['client_info'][sid]['connection_errors'] += 1

# Transport-specific monitoring
@sio.event
async def connect_failed(sid, environ):
    """Handle failed connection attempts."""
    logger.error(f"❌ CONNECTION_FAILED: {sid} - Remote: {environ.get('REMOTE_ADDR', 'unknown')}")
    logger.error(f"🔍 FAILED_CONNECTION_DETAILS: Transport: {environ.get('HTTP_UPGRADE', 'polling')}, UA: {environ.get('HTTP_USER_AGENT', 'unknown')[:100]}...")

@sio.event
async def start_analysis(sid, data):
    """Handle code analysis request via WebSocket."""
    try:
        analysis_id = data.get('analysisId')
        logger.info(f"🚀 Starting analysis for client {sid}: {analysis_id}")
        
        # Get client IP for rate limiting
        client_info = connection_stats['client_info'].get(sid, {})
        client_ip = client_info.get('remote_addr', 'unknown')
        
        # Check WebSocket rate limits for analysis
        if not rate_limiter.check_websocket_rate_limit(client_ip, 'analysis'):
            await sio.emit('analysis_error', {
                'analysisId': analysis_id or 'unknown',
                'error': 'Analysis rate limit exceeded. Please wait before submitting another analysis.'
            }, room=sid)
            logger.warning(f"⚠️ Analysis {analysis_id} rejected for {client_ip}: rate limit exceeded")
            return
        
        # Check resource limits before starting analysis
        if not await performance_optimizer.check_resource_limits():
            await sio.emit('analysis_error', {
                'analysisId': analysis_id or 'unknown',
                'error': 'Server is currently overloaded. Please try again in a few moments.'
            }, room=sid)
            logger.warning(f"⚠️ Analysis {analysis_id} rejected due to resource limits")
            return
        
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
        
        # Update resource monitor
        resource_monitor.update_analysis_count(len(active_analyses))
        
        # Create async task for analysis with performance optimization
        task = asyncio.create_task(run_analysis_with_optimization(
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

async def run_analysis_with_optimization(
    analysis_id: str, sid: str, code: str, language: str, 
    filename: str, analysis_type: str, severity_threshold: str,
    include_suggestions: bool, include_explanations: bool, config: Any
):
    """Run analysis with performance optimization and resource management."""
    # Apply semaphore limiting for concurrent analyses
    async with performance_optimizer.analysis_semaphore:
        return await run_analysis_with_progress(
            analysis_id, sid, code, language, filename, 
            analysis_type, severity_threshold, include_suggestions, 
            include_explanations, config
        )

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
            
            # Special handling for AI model loading with circuit breaker
            if stage_key == "model_loading":
                if not ai_analyzer.model_loaded:
                    await sio.emit('analysis_progress', {
                        'analysisId': analysis_id,
                        'progress': 12,
                        'message': 'Loading AI model (this may take a moment)...',
                        'stage': stage_key
                    }, room=sid)
                    
                    # Load model with circuit breaker protection
                    circuit_breaker = performance_optimizer.get_circuit_breaker(
                        'ai_model_loading', failure_threshold=3, recovery_timeout=300
                    )
                    
                    try:
                        # Apply AI operation semaphore and circuit breaker
                        async with performance_optimizer.ai_semaphore:
                            await circuit_breaker.call(
                                lambda: asyncio.wait_for(
                                    ai_analyzer.load_model(),
                                    timeout=60.0
                                )
                            )
                    except asyncio.TimeoutError:
                        logger.error("❌ Model loading timed out after 1 minute")
                        await sio.emit('analysis_error', {
                            'analysisId': analysis_id,
                            'error': 'Model loading timed out. Please try again.'
                        }, room=sid)
                        return
                    except Exception as e:
                        logger.error(f"❌ Model loading failed: {e}")
                        await sio.emit('analysis_error', {
                            'analysisId': analysis_id,
                            'error': 'Failed to load AI model. Please try again later.'
                        }, room=sid)
                        return
                    
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
        
        # Perform the actual analysis with caching, circuit breaker, and timeout protection
        await sio.emit('analysis_progress', {
            'analysisId': analysis_id,
            'progress': 98,
            'message': 'Running AI analysis...',
            'stage': 'ai_processing'
        }, room=sid)
        
        # Check cache first
        cache_key = f"analysis_{hash(code)}_{language}_{analysis_type}_{severity_threshold}"
        cached_result = performance_optimizer.get_cached_result(cache_key)
        
        if cached_result:
            logger.info(f"📊 Using cached result for analysis {analysis_id}")
            result = cached_result
        else:
            # Get circuit breaker for AI analysis
            ai_circuit_breaker = performance_optimizer.get_circuit_breaker(
                'ai_analysis', failure_threshold=5, recovery_timeout=180
            )
            
            try:
                # Perform analysis with circuit breaker and semaphore protection
                async with performance_optimizer.ai_semaphore:
                    result = await ai_circuit_breaker.call(
                        lambda: asyncio.wait_for(
                            ai_analyzer.analyze_code(request),
                            timeout=120.0  # 2 minute timeout
                        )
                    )
                
                # Cache the result for future use (5 minute TTL)
                performance_optimizer.cache_operation_result(cache_key, result, ttl=300)
                logger.debug(f"📊 Cached analysis result for {analysis_id}")
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Analysis {analysis_id} timed out after 2 minutes")
                await sio.emit('analysis_error', {
                    'analysisId': analysis_id,
                    'error': 'Analysis timed out. Please try with a smaller code sample.'
                }, room=sid)
                return
            except Exception as e:
                if "Circuit breaker is open" in str(e):
                    logger.error(f"❌ AI analysis circuit breaker open for {analysis_id}")
                    await sio.emit('analysis_error', {
                        'analysisId': analysis_id,
                        'error': 'AI analysis service is temporarily unavailable. Please try again later.'
                    }, room=sid)
                else:
                    logger.error(f"❌ AI analysis failed for {analysis_id}: {e}")
                    await sio.emit('analysis_error', {
                        'analysisId': analysis_id,
                        'error': 'Analysis failed due to an internal error.'
                    }, room=sid)
                return
        
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
            'result': result
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
            # Update resource monitor
            resource_monitor.update_analysis_count(len(active_analyses))
            
    except asyncio.CancelledError:
        logger.info(f"🛑 Analysis {analysis_id} was cancelled")
        if analysis_id in active_analyses:
            del active_analyses[analysis_id]
            # Update resource monitor
            resource_monitor.update_analysis_count(len(active_analyses))
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
            # Update resource monitor
            resource_monitor.update_analysis_count(len(active_analyses))

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

# Periodic connection monitoring
async def periodic_connection_monitoring():
    """Periodic task to monitor connection health and log statistics."""
    while True:
        try:
            await asyncio.sleep(300)  # Log every 5 minutes
            
            current_time = time.time()
            active_count = connection_stats['active_connections']
            
            if active_count > 0:
                logger.info(f"📊 CONNECTION_HEALTH_CHECK: {active_count} active connections")
                
                # Check for stale connections
                stale_connections = []
                for sid, client_info in connection_stats['client_info'].items():
                    last_ping = client_info.get('last_ping_time')
                    if last_ping and current_time - last_ping > 120:
                        stale_connections.append(sid)
                
                if stale_connections:
                    logger.warning(f"⚠️ STALE_CONNECTIONS_DETECTED: {len(stale_connections)} connections without recent ping")
                    for sid in stale_connections:
                        client_info = connection_stats['client_info'][sid]
                        last_ping = client_info.get('last_ping_time', 0)
                        logger.warning(f"📡 STALE_CLIENT: {sid} - Last ping: {current_time - last_ping:.1f}s ago")
                
                # Log summary statistics
                total_pings = sum(connection_stats['ping_pong_cycles'].values())
                total_errors = sum(connection_stats['connection_errors'].values())
                logger.info(f"📈 STATISTICS_SUMMARY: Total pings: {total_pings}, Total errors: {total_errors}, Total disconnects: {connection_stats['total_disconnections']}")
            else:
                logger.debug("📊 CONNECTION_HEALTH_CHECK: No active connections")
                
        except Exception as e:
            logger.error(f"❌ Error in connection monitoring: {e}")

# Periodic performance cleanup
async def periodic_performance_cleanup():
    """Periodic task to perform performance optimization and cleanup."""
    while True:
        try:
            await asyncio.sleep(180)  # Run every 3 minutes
            
            # Perform periodic cleanup
            await performance_optimizer.periodic_cleanup()
            
            # Log performance statistics every 15 minutes
            if int(time.time()) % 900 == 0:  # Every 15 minutes
                perf_stats = performance_optimizer.get_performance_stats()
                logger.info(f"📊 PERFORMANCE_STATS: {perf_stats}")
                
                # Check for performance issues
                current_usage = perf_stats['current_usage']
                limits = perf_stats['resource_limits']
                
                if current_usage['active_analyses'] >= limits['max_concurrent_analyses']:
                    logger.warning("⚠️ Analysis queue at maximum capacity")
                    
                if current_usage['active_ai_operations'] >= limits['max_concurrent_ai_operations']:
                    logger.warning("⚠️ AI operations at maximum capacity")
                    
        except Exception as e:
            logger.error(f"❌ Error in performance cleanup: {e}")

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("🚀 Starting AI Code Review Assistant...")
    
    # Start resource monitoring
    await resource_monitor.start_monitoring()
    logger.info("📊 Started comprehensive resource monitoring")
    
    # Start periodic connection monitoring
    asyncio.create_task(periodic_connection_monitoring())
    logger.info("📊 Started periodic connection monitoring (every 5 minutes)")
    
    # Start periodic performance optimization cleanup
    asyncio.create_task(periodic_performance_cleanup())
    logger.info("🧹 Started periodic performance cleanup")
    
    # Ensure AI model is loaded at startup to prevent blocking during requests
    if not ai_analyzer.model_loaded:
        logger.info("🤖 Loading AI model on startup...")
        try:
            start_time = time.time()
            await ai_analyzer.load_model()
            load_time = time.time() - start_time
            if ai_analyzer.model_loaded:
                logger.info(f"✅ AI model loaded successfully in {load_time:.2f}s")
            else:
                logger.warning("⚠️ Failed to load AI model on startup")
        except Exception as e:
            logger.error(f"❌ Error loading AI model: {e}")
    
    logger.info("🔌 Socket.IO server initialized and ready for connections")
    logger.info(f"📡 WebSocket endpoint: ws://localhost:8000/socket.io/")
    logger.info(f"📖 API documentation: http://localhost:8000/docs")
    logger.info(f"📊 Connection statistics: http://localhost:8000/api/socket-stats")
    logger.info(f"📊 Resource monitoring: http://localhost:8000/api/resource-stats")

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
        "active_analyses": len(active_analyses),
        "active_connections": connection_stats['active_connections']
    }

@app.get("/api/resource-stats")
async def get_resource_statistics():
    """Get comprehensive resource usage statistics and performance metrics."""
    try:
        resource_summary = resource_monitor.get_metrics_summary()
        current_metrics = resource_monitor.get_current_metrics()
        
        # Add AI service information
        ai_info = {
            "model_loaded": ai_analyzer.model_loaded,
            "model_path": getattr(ai_analyzer, 'model_path', 'unknown') if hasattr(ai_analyzer, 'model_path') else 'unknown',
            "loading_status": "loaded" if ai_analyzer.model_loaded else "not_loaded"
        }
        
        return {
            **resource_summary,
            "ai_service": ai_info,
            "active_analyses_details": len(active_analyses),
            "server_uptime": time.time() - getattr(startup_event, '_start_time', time.time()),
            "monitoring_status": "active" if resource_monitor.is_monitoring else "inactive"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting resource statistics: {e}")
        return {
            "error": str(e),
            "timestamp": time.time(),
            "status": "error"
        }

@app.get("/api/performance-stats")
async def get_performance_statistics():
    """Get detailed performance optimization statistics."""
    try:
        perf_stats = performance_optimizer.get_performance_stats()
        
        # Add additional context
        perf_stats['memory_cleanup'] = {
            'last_cleanup_time': performance_optimizer.last_cleanup_time,
            'cleanup_interval': performance_optimizer.cleanup_interval,
            'memory_cleanup_threshold_mb': performance_optimizer.memory_cleanup_threshold
        }
        
        # Add active operations info
        perf_stats['active_operations'] = {
            'semaphore_available_analyses': performance_optimizer.analysis_semaphore._value,
            'semaphore_available_ai_ops': performance_optimizer.ai_semaphore._value,
            'total_active_analyses': len(active_analyses)
        }
        
        return perf_stats
        
    except Exception as e:
        logger.error(f"❌ Error getting performance statistics: {e}")
        return {
            "error": str(e),
            "timestamp": time.time(),
            "status": "error"
        }

@app.get("/api/rate-limit-stats")
async def get_rate_limit_statistics():
    """Get detailed rate limiting statistics."""
    try:
        return rate_limiter.get_rate_limit_stats()
    except Exception as e:
        logger.error(f"❌ Error getting rate limit statistics: {e}")
        return {
            "error": str(e),
            "timestamp": time.time(),
            "status": "error"
        }

@app.get("/api/socket-stats")
async def get_socket_statistics():
    """Get detailed WebSocket connection statistics for debugging."""
    current_time = time.time()
    
    # Calculate ping statistics
    healthy_connections = 0
    stale_connections = 0
    error_connections = 0
    
    for sid, client_info in connection_stats['client_info'].items():
        last_ping = client_info.get('last_ping_time')
        errors = client_info.get('connection_errors', 0)
        
        if errors > 3:
            error_connections += 1
        elif last_ping and current_time - last_ping > 120:
            stale_connections += 1
        else:
            healthy_connections += 1
    
    return {
        "timestamp": current_time,
        "formatted_time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time)),
        "connection_summary": {
            "total_connections_ever": connection_stats['total_connections'],
            "active_connections": connection_stats['active_connections'],
            "total_disconnections": connection_stats['total_disconnections'],
            "healthy_connections": healthy_connections,
            "stale_connections": stale_connections,
            "error_connections": error_connections
        },
        "ping_statistics": {
            "total_ping_cycles": dict(connection_stats['ping_pong_cycles']),
            "connection_errors_by_type": dict(connection_stats['connection_errors']),
            "analysis_timeouts": connection_stats['analysis_timeouts']
        },
        "active_clients": {
            sid: {
                "remote_addr": info.get('remote_addr'),
                "transport": info.get('transport'),
                "connect_time": info.get('connect_time'),
                "session_duration": current_time - info.get('connect_time', current_time),
                "ping_count": info.get('ping_count', 0),
                "pong_count": info.get('pong_count', 0),
                "last_ping_time": info.get('last_ping_time'),
                "time_since_last_ping": current_time - info.get('last_ping_time', current_time) if info.get('last_ping_time') else None,
                "connection_errors": info.get('connection_errors', 0)
            }
            for sid, info in connection_stats['client_info'].items()
        },
        "server_config": {
            "ping_timeout": 120,
            "ping_interval": 60,
            "max_http_buffer_size": 10**7,
            "transports": ['websocket', 'polling']
        }
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