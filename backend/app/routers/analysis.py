from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect, Query, Path
from typing import Dict, List, Any, Optional
import uuid
import time
from datetime import datetime
import json
import asyncio

from app.models.requests import CodeAnalysisRequest, SupportedLanguage, AnalysisType
from app.models.responses import (
    CodeAnalysisResponse,
    CodeIssue,
    CodeMetrics,
    AnalysisSummary,
    IssueSeverity,
    IssueType
)
from app.services.analyzer import CodeAnalyzerService
from app.services.static_analysis_service import StaticAnalysisOrchestrator
from app.services.rules_config_service import RulesConfigManager
from app.services.analysis_optimizer import AnalysisOptimizer, AnalysisProgressTracker
from app.worker import celery, analyze_code_background

router = APIRouter()

# Initialize services
analyzer_service = CodeAnalyzerService()
static_analyzer = StaticAnalysisOrchestrator()
rules_manager = RulesConfigManager()
optimizer = AnalysisOptimizer()
progress_tracker = AnalysisProgressTracker(optimizer)


@router.post("/analyze", response_model=CodeAnalysisResponse)
async def analyze_code(request: CodeAnalysisRequest) -> CodeAnalysisResponse:
    """
    Analyze the provided code for bugs, security issues, and improvements.
    
    This endpoint accepts code in various programming languages and returns
    a comprehensive analysis including:
    - Detected issues with severity levels
    - Code quality metrics
    - Improvement suggestions
    - Overall quality score
    """
    start_time = time.time()
    
    try:
        # Generate unique analysis ID
        analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"
        
        # Perform code analysis (stub implementation for Sprint 1)
        analysis_result = await analyzer_service.analyze_code(
            code=request.code,
            language=request.language,
            analysis_type=request.analysis_type,
            filename=request.filename,
            include_suggestions=request.include_suggestions,
            include_explanations=request.include_explanations,
            severity_threshold=request.severity_threshold
        )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Build response
        response = CodeAnalysisResponse(
            analysis_id=analysis_id,
            timestamp=datetime.utcnow(),
            language=request.language.value,
            filename=request.filename,
            issues=analysis_result["issues"],
            metrics=analysis_result["metrics"],
            summary=analysis_result["summary"],
            processing_time_ms=processing_time,
            suggestions=analysis_result["suggestions"]
        )
        
        return response
        
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"Error analyzing code: {str(e)}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AnalysisError",
                "message": "Failed to analyze the provided code",
                "details": {
                    "reason": str(e)
                }
            }
        )


@router.get("/supported-languages")
async def get_supported_languages() -> Dict[str, Any]:
    """
    Get the list of supported programming languages for code analysis.
    """
    return {
        "languages": [
            {
                "code": "python",
                "name": "Python",
                "extensions": [".py", ".pyw"]
            },
            {
                "code": "javascript",
                "name": "JavaScript",
                "extensions": [".js", ".mjs"]
            },
            {
                "code": "typescript",
                "name": "TypeScript",
                "extensions": [".ts", ".tsx"]
            },
            {
                "code": "java",
                "name": "Java",
                "extensions": [".java"]
            },
            {
                "code": "cpp",
                "name": "C++",
                "extensions": [".cpp", ".cxx", ".cc", ".hpp", ".h"]
            }
        ],
        "total_count": 5
    }


@router.get("/analysis-types")
async def get_analysis_types() -> Dict[str, Any]:
    """
    Get the available types of code analysis.
    """
    return {
        "analysis_types": [
            {
                "code": "full",
                "name": "Full Analysis",
                "description": "Complete analysis including bugs, security, performance, and style"
            },
            {
                "code": "bugs_only",
                "name": "Bug Detection",
                "description": "Focus only on potential bugs and logical errors"
            },
            {
                "code": "security_only",
                "name": "Security Analysis",
                "description": "Focus only on security vulnerabilities"
            },
            {
                "code": "performance_only",
                "name": "Performance Analysis",
                "description": "Focus only on performance improvements"
            },
            {
                "code": "style_only",
                "name": "Style Analysis",
                "description": "Focus only on code style and formatting"
            }
        ]
    }


# New endpoints for Sprint 3

@router.post("/multi-tool")
async def analyze_with_multiple_tools(request: CodeAnalysisRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Analyze code using multiple static analysis tools in parallel.
    
    This endpoint runs various language-specific static analysis tools and merges the results.
    For longer analyses, it runs in the background and provides a job ID for tracking progress.
    """
    try:
        # Generate a unique job ID
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        
        # Get language-specific rules configuration
        rules_config = rules_manager.get_default_rules(request.language.value)
        
        # Check if code is large enough to warrant background processing
        if len(request.code) > 5000:  # If code is larger than ~5KB
            # Start background task
            task = analyze_code_background.delay(
                request.code,
                request.language.value,
                rules_config
            )
            
            # Register the task for progress tracking
            await progress_tracker.register_task(job_id, task.id)
            
            return {
                "job_id": job_id,
                "status": "processing",
                "message": "Analysis started in background",
                "estimated_time_seconds": len(request.code) // 1000  # Rough estimate
            }
        else:
            # For smaller code snippets, run analysis synchronously
            result = await static_analyzer.analyze_code(
                request.code,
                request.language.value,
                rules_config
            )
            
            return {
                "job_id": job_id,
                "status": "completed",
                "result": result
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AnalysisError",
                "message": "Failed to start multi-tool analysis",
                "details": {"reason": str(e)}
            }
        )


@router.post("/configure")
async def configure_analysis_rules(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Configure static analysis rules and preferences.
    
    This endpoint allows setting custom rules for different languages and tools,
    as well as applying predefined rule presets.
    """
    try:
        # Extract configuration details
        language = config.get("language")
        preset = config.get("preset")
        custom_rules = config.get("rules", {})
        name = config.get("name", "custom")
        
        if not language:
            raise HTTPException(
                status_code=400,
                detail={"error": "ValidationError", "message": "Language is required"}
            )
        
        # Apply preset if specified
        if preset:
            preset_rules = rules_manager.apply_preset(language, preset)
            if not preset_rules:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "NotFoundError", "message": f"Preset '{preset}' not found for {language}"}
                )
            
            # Merge preset with custom rules if provided
            if custom_rules:
                final_rules = rules_manager.merge_rule_sets(preset_rules, custom_rules)
            else:
                final_rules = preset_rules
        else:
            # Use custom rules directly
            final_rules = custom_rules
        
        # Validate the rules
        for tool, tool_rules in final_rules.items():
            if not rules_manager.validate_custom_rules(tool_rules, language, tool):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "ValidationError",
                        "message": f"Invalid rules for {tool}"
                    }
                )
        
        # Save the configuration
        success = rules_manager.save_rules(final_rules, language, name)
        if not success:
            raise HTTPException(
                status_code=500,
                detail={"error": "SaveError", "message": "Failed to save configuration"}
            )
        
        return {
            "status": "success",
            "message": f"Configuration '{name}' saved for {language}",
            "language": language,
            "preset": preset,
            "name": name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ConfigurationError",
                "message": "Failed to configure analysis rules",
                "details": {"reason": str(e)}
            }
        )


@router.get("/rules/{language}")
async def get_available_rules(language: str) -> Dict[str, Any]:
    """
    Get available static analysis rules for a specific language.
    
    This endpoint returns default rules, available presets, and any saved custom configurations.
    """
    try:
        # Get default rules
        default_rules = rules_manager.get_default_rules(language)
        if not default_rules:
            raise HTTPException(
                status_code=404,
                detail={"error": "NotFoundError", "message": f"No rules found for {language}"}
            )
        
        # Get available presets
        presets = rules_manager.get_rule_presets(language)
        
        # Get rule templates
        templates = rules_manager.get_rule_templates()
        
        return {
            "language": language,
            "default_rules": default_rules,
            "available_presets": list(presets.keys()) if presets else [],
            "templates": templates.get(language, {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "RulesError",
                "message": f"Failed to get rules for {language}",
                "details": {"reason": str(e)}
            }
        )


@router.get("/progress/{job_id}")
async def get_analysis_progress(job_id: str = Path(..., description="The job ID to track")) -> Dict[str, Any]:
    """
    Track the progress of a background analysis job.
    
    This endpoint returns the current status, progress percentage, and result (if completed).
    """
    try:
        # Get progress information
        progress_info = await progress_tracker.get_progress(job_id)
        
        if not progress_info:
            raise HTTPException(
                status_code=404,
                detail={"error": "NotFoundError", "message": f"Job {job_id} not found"}
            )
        
        # If the job is complete, include the result
        if progress_info["status"] == "completed":
            # Get the result from the task
            task_id = progress_info["task_id"]
            result = await progress_tracker.get_task_result(task_id)
            
            return {
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "result": result
            }
        
        # If the job failed, include the error
        if progress_info["status"] == "failed":
            return {
                "job_id": job_id,
                "status": "failed",
                "error": progress_info.get("error", "Unknown error")
            }
        
        # If the job is still running, return progress information
        return {
            "job_id": job_id,
            "status": progress_info["status"],
            "progress": progress_info["progress"],
            "message": progress_info.get("message", "Analysis in progress")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ProgressError",
                "message": "Failed to get analysis progress",
                "details": {"reason": str(e)}
            }
        )


@router.post("/incremental")
async def analyze_incremental(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform incremental analysis on code changes.
    
    This endpoint analyzes only the changed portions of code, making it faster for large codebases.
    It requires the original code, changed code, and file path.
    """
    try:
        # Extract request data
        original_code = request.get("original_code", "")
        changed_code = request.get("changed_code", "")
        file_path = request.get("file_path", "")
        language = request.get("language", "")
        
        # Validate request
        if not changed_code or not language:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ValidationError",
                    "message": "Changed code and language are required"
                }
            )
        
        # Determine language from file extension if not specified
        if not language and file_path:
            extension = file_path.split(".")[-1].lower()
            language_map = {
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "java": "java",
                "cpp": "cpp",
                "cc": "cpp",
                "h": "cpp",
                "hpp": "cpp"
            }
            language = language_map.get(extension, "")
        
        if not language:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ValidationError",
                    "message": "Could not determine language from file extension"
                }
            )
        
        # Get default rules for the language
        rules_config = rules_manager.get_default_rules(language)
        
        # If there's original code, analyze only the differences
        if original_code:
            # TODO: Implement diff-based analysis
            # For now, just analyze the changed code
            result = await static_analyzer.analyze_code(changed_code, language, rules_config)
        else:
            # If no original code, analyze the entire changed code
            result = await static_analyzer.analyze_code(changed_code, language, rules_config)
        
        return {
            "status": "success",
            "file_path": file_path,
            "language": language,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AnalysisError",
                "message": "Failed to perform incremental analysis",
                "details": {"reason": str(e)}
            }
        )


@router.websocket("/ws/progress/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time progress updates.
    
    This endpoint sends progress updates for a background analysis job in real-time.
    """
    await websocket.accept()
    
    try:
        # Check if the job exists
        progress_info = await progress_tracker.get_progress(job_id)
        
        if not progress_info:
            await websocket.send_json({
                "error": "Job not found",
                "job_id": job_id
            })
            await websocket.close()
            return
        
        # Send initial progress
        await websocket.send_json({
            "job_id": job_id,
            "status": progress_info["status"],
            "progress": progress_info["progress"],
            "message": progress_info.get("message", "Analysis in progress")
        })
        
        # If the job is already completed, send the result and close
        if progress_info["status"] == "completed":
            task_id = progress_info["task_id"]
            result = await progress_tracker.get_task_result(task_id)
            
            await websocket.send_json({
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "result": result
            })
            
            await websocket.close()
            return
        
        # If the job failed, send the error and close
        if progress_info["status"] == "failed":
            await websocket.send_json({
                "job_id": job_id,
                "status": "failed",
                "error": progress_info.get("error", "Unknown error")
            })
            
            await websocket.close()
            return
        
        # Subscribe to progress updates
        queue = asyncio.Queue()
        await progress_tracker.subscribe(job_id, queue)
        
        # Send progress updates until the job completes or the connection closes
        while True:
            try:
                # Wait for an update with a timeout
                update = await asyncio.wait_for(queue.get(), timeout=5.0)
                
                # Send the update to the client
                await websocket.send_json(update)
                
                # If the job completed or failed, close the connection
                if update["status"] in ["completed", "failed"]:
                    break
                    
            except asyncio.TimeoutError:
                # Send a ping to keep the connection alive
                await websocket.send_json({"ping": True})
                
            except WebSocketDisconnect:
                # Client disconnected
                break
        
        # Unsubscribe from progress updates
        await progress_tracker.unsubscribe(job_id, queue)
        
    except Exception as e:
        # Send error and close connection
        try:
            await websocket.send_json({
                "error": str(e),
                "job_id": job_id
            })
        except:
            pass
        
        # Close the connection
        await websocket.close()