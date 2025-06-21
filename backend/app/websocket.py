# backend/app/websocket.py
import asyncio
import logging
from typing import Dict, Any
import socketio
from fastapi import FastAPI
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    logger=True,
    engineio_logger=True
)

# Store active analysis sessions
active_analyses: Dict[str, Dict[str, Any]] = {}

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger.info(f"Client {sid} connected")
    await sio.emit('notification', {
        'type': 'success',
        'message': 'Connected to analysis server'
    }, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client {sid} disconnected")
    
    # Cancel any active analyses for this client
    analyses_to_cancel = []
    for analysis_id, analysis_data in active_analyses.items():
        if analysis_data.get('client_id') == sid:
            analyses_to_cancel.append(analysis_id)
    
    for analysis_id in analyses_to_cancel:
        await cancel_analysis_internal(analysis_id, sid)

@sio.event
async def start_analysis(sid, data):
    """Handle analysis start request"""
    try:
        analysis_id = data.get('analysisId')
        if not analysis_id:
            await sio.emit('analysis_error', {
                'analysisId': 'unknown',
                'error': 'Missing analysis ID'
            }, room=sid)
            return

        logger.info(f"Starting analysis {analysis_id} for client {sid}")
        
        # Store analysis session
        active_analyses[analysis_id] = {
            'client_id': sid,
            'data': data,
            'status': 'running',
            'task': None
        }
        
        # Start the analysis task
        task = asyncio.create_task(run_analysis(analysis_id, data, sid))
        active_analyses[analysis_id]['task'] = task
        
        await sio.emit('notification', {
            'type': 'info',
            'message': f'Analysis {analysis_id[:8]}... started'
        }, room=sid)
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        await sio.emit('analysis_error', {
            'analysisId': data.get('analysisId', 'unknown'),
            'error': str(e)
        }, room=sid)

@sio.event
async def cancel_analysis(sid, data):
    """Handle analysis cancellation request"""
    analysis_id = data.get('analysisId')
    if not analysis_id:
        return
    
    await cancel_analysis_internal(analysis_id, sid)

async def cancel_analysis_internal(analysis_id: str, sid: str):
    """Internal function to cancel analysis"""
    if analysis_id in active_analyses:
        analysis_data = active_analyses[analysis_id]
        
        # Cancel the task if it exists
        task = analysis_data.get('task')
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled analysis {analysis_id}")
        
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

async def run_analysis(analysis_id: str, data: Dict[str, Any], client_id: str):
    """Run the actual code analysis with progress updates"""
    try:
        code = data.get('code', '')
        language = data.get('language', 'python')
        analysis_type = data.get('analysis_type', 'comprehensive')
        
        # Simulation of analysis stages with progress updates
        stages = [
            ("Parsing code structure", 10),
            ("Running static analysis", 25),
            ("Checking for security vulnerabilities", 45),
            ("Analyzing code quality", 65),
            ("Generating suggestions", 80),
            ("Compiling results", 95),
            ("Finalizing report", 100)
        ]
        
        for stage, progress in stages:
            # Check if analysis was cancelled
            if analysis_id not in active_analyses:
                logger.info(f"Analysis {analysis_id} was cancelled")
                return
            
            # Send progress update
            await sio.emit('analysis_progress', {
                'analysisId': analysis_id,
                'progress': progress,
                'message': stage,
                'stage': stage.lower().replace(' ', '_')
            }, room=client_id)
            
            # Simulate processing time
            await asyncio.sleep(0.5 if analysis_type == 'quick' else 1.0)
        
        # Import your analysis service here
        # For now, we'll create a mock result
        result = {
            'analysis_id': analysis_id,
            'timestamp': '2024-01-01T00:00:00Z',
            'language': language,
            'summary': {
                'overall_score': 85.5,
                'total_issues': 3,
                'critical_issues': 0,
                'high_issues': 1,
                'medium_issues': 1,
                'low_issues': 1,
                'lines_of_code': len(code.split('\n')),
                'complexity_score': 2.3
            },
            'issues': [
                {
                    'id': 'issue_1',
                    'type': 'style',
                    'severity': 'high',
                    'line_number': 5,
                    'column_number': 12,
                    'description': 'Variable name should be in snake_case',
                    'suggestion': 'Rename variable to follow Python naming conventions',
                    'rule_id': 'naming_convention',
                    'category': 'style'
                },
                {
                    'id': 'issue_2',
                    'type': 'performance',
                    'severity': 'medium',
                    'line_number': 12,
                    'column_number': 8,
                    'description': 'Consider using list comprehension for better performance',
                    'suggestion': 'Replace loop with list comprehension: [x*2 for x in items]',
                    'rule_id': 'list_comprehension',
                    'category': 'performance'
                },
                {
                    'id': 'issue_3',
                    'type': 'maintainability',
                    'severity': 'low',
                    'line_number': 20,
                    'column_number': 1,
                    'description': 'Function is too long and should be split',
                    'suggestion': 'Consider breaking this function into smaller, more focused functions',
                    'rule_id': 'function_length',
                    'category': 'maintainability'
                }
            ],
            'metrics': {
                'cyclomatic_complexity': 3,
                'maintainability_index': 75.2,
                'technical_debt_ratio': 0.15
            },
            'suggestions': [
                {
                    'type': 'refactoring',
                    'description': 'Consider extracting common functionality into utility functions',
                    'impact': 'medium'
                }
            ]
        }
        
        # Send completion
        await sio.emit('analysis_complete', {
            'analysisId': analysis_id,
            'result': result
        }, room=client_id)
        
        await sio.emit('notification', {
            'type': 'success',
            'message': f'Analysis {analysis_id[:8]}... completed successfully'
        }, room=client_id)
        
        # Clean up
        if analysis_id in active_analyses:
            del active_analyses[analysis_id]
            
    except asyncio.CancelledError:
        logger.info(f"Analysis {analysis_id} was cancelled")
        if analysis_id in active_analyses:
            del active_analyses[analysis_id]
    except Exception as e:
        logger.error(f"Error in analysis {analysis_id}: {e}")
        await sio.emit('analysis_error', {
            'analysisId': analysis_id,
            'error': str(e)
        }, room=client_id)
        
        if analysis_id in active_analyses:
            del active_analyses[analysis_id]

def create_socket_app() -> socketio.ASGIApp:
    """Create and return the Socket.IO ASGI app"""
    return socketio.ASGIApp(sio)

def setup_websocket(app: FastAPI):
    """Setup WebSocket with FastAPI app"""
    # Mount the Socket.IO app
    socket_app = create_socket_app()
    app.mount("/socket.io", socket_app)
    
    logger.info("WebSocket server setup complete")
    return sio