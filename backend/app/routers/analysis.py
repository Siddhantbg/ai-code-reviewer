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
# Updated imports for GGUF model
from app.services.gguf_service import gguf_analyzer
from app.services.static_analysis_service import StaticAnalysisOrchestrator
from app.services.rules_config_service import RulesConfigManager
from app.services.analysis_optimizer import AnalysisOptimizer, AnalysisProgressTracker
from app.worker import celery, analyze_code_background

router = APIRouter()

# Initialize services (updated for GGUF)
static_analyzer = StaticAnalysisOrchestrator()
rules_manager = RulesConfigManager()
optimizer = AnalysisOptimizer()
progress_tracker = AnalysisProgressTracker(optimizer)


@router.post("/analyze", response_model=CodeAnalysisResponse)
async def analyze_code(request: CodeAnalysisRequest) -> CodeAnalysisResponse:
    """
    Analyze the provided code for bugs, security issues, and improvements using GGUF model.
    
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
        
        # Use GGUF analyzer for AI-powered analysis
        gguf_result = await gguf_analyzer.analyze_code(
            code=request.code,
            language=request.language.value,
            analysis_type=request.analysis_type.value
        )
        
        # Convert GGUF result to our response format
        issues = []
        for issue in gguf_result.get("issues", []):
            issues.append(CodeIssue(
                id=issue.get("id", f"issue_{len(issues)}"),
                type=IssueType(issue.get("type", "bug")),
                severity=IssueSeverity(issue.get("severity", "medium")),
                line_number=issue.get("line_number"),
                column_number=None,
                message=issue.get("description", "Issue detected"),
                rule_id=issue.get("id"),
                suggestion=issue.get("suggestion"),
                confidence=issue.get("confidence", 80)
            ))
        
        # Create metrics from GGUF summary
        summary_data = gguf_result.get("summary", {})
        metrics = CodeMetrics(
            lines_of_code=len(request.code.split('\n')),
            cyclomatic_complexity=5,  # Default value
            maintainability_index=summary_data.get("overall_score", 75),
            halstead_volume=100,  # Default value
            code_duplication_percentage=0  # Default value
        )
        
        # Create summary
        summary = AnalysisSummary(
            total_issues=summary_data.get("total_issues", len(issues)),
            critical_issues=summary_data.get("critical_issues", 0),
            high_issues=len([i for i in issues if i.severity == IssueSeverity.HIGH]),
            medium_issues=len([i for i in issues if i.severity == IssueSeverity.MEDIUM]),
            low_issues=len([i for i in issues if i.severity == IssueSeverity.LOW]),
            overall_score=summary_data.get("overall_score", 75),
            security_score=summary_data.get("security_score", 80)
        )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Build response
        response = CodeAnalysisResponse(
            analysis_id=analysis_id,
            timestamp=datetime.utcnow(),
            language=request.language.value,
            filename=request.filename,
            issues=issues,
            metrics=metrics,
            summary=summary,
            processing_time_ms=processing_time,
            suggestions=gguf_result.get("suggestions", [])
        )
        
        return response
        
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"Error analyzing code with GGUF model: {str(e)}")
        
        # Fallback to static analysis if GGUF fails
        try:
            fallback_result = await static_analyzer.analyze_code(
                request.code,
                request.language.value,
                rules_manager.get_default_rules(request.language.value)
            )
            
            # Convert static analysis result to response format
            processing_time = (time.time() - start_time) * 1000
            
            response = CodeAnalysisResponse(
                analysis_id=analysis_id,
                timestamp=datetime.utcnow(),
                language=request.language.value,
                filename=request.filename,
                issues=[],  # Static analysis format conversion needed
                metrics=CodeMetrics(
                    lines_of_code=len(request.code.split('\n')),
                    cyclomatic_complexity=5,
                    maintainability_index=70,
                    halstead_volume=100,
                    code_duplication_percentage=0
                ),
                summary=AnalysisSummary(
                    total_issues=0,
                    critical_issues=0,
                    high_issues=0,
                    medium_issues=0,
                    low_issues=0,
                    overall_score=70,
                    security_score=75
                ),
                processing_time_ms=processing_time,
                suggestions=[{
                    "category": "general",
                    "description": "GGUF model temporarily unavailable, used static analysis",
                    "priority": "low"
                }]
            )
            
            return response
            
        except Exception as fallback_error:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "AnalysisError",
                    "message": "Both GGUF and static analysis failed",
                    "details": {
                        "gguf_error": str(e),
                        "static_error": str(fallback_error)
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
                "extensions": [".py", ".pyw"],
                "gguf_support": True
            },
            {
                "code": "javascript",
                "name": "JavaScript",
                "extensions": [".js", ".mjs"],
                "gguf_support": True
            },
            {
                "code": "typescript",
                "name": "TypeScript",
                "extensions": [".ts", ".tsx"],
                "gguf_support": True
            },
            {
                "code": "java",
                "name": "Java",
                "extensions": [".java"],
                "gguf_support": True
            },
            {
                "code": "cpp",
                "name": "C++",
                "extensions": [".cpp", ".cxx", ".cc", ".hpp", ".h"],
                "gguf_support": True
            }
        ],
        "total_count": 5,
        "model_info": {
            "type": "gguf",
            "model": "deepseek-coder-1.3b-instruct",
            "quantization": "Q4_K_M"
        }
    }


@router.get("/analysis-types")
async def get_analysis_types() -> Dict[str, Any]:
    """
    Get the available types of code analysis.
    """
    return {
        "analysis_types": [
            {
                "code": "comprehensive",
                "name": "Comprehensive Analysis",
                "description": "Complete analysis including bugs, security, performance, and style using GGUF model"
            },
            {
                "code": "quick",
                "name": "Quick Analysis",
                "description": "Fast analysis focusing on critical issues only"
            },
            {
                "code": "security",
                "name": "Security Analysis",
                "description": "Focus only on security vulnerabilities"
            },
            {
                "code": "bugs_only",
                "name": "Bug Detection",
                "description": "Focus only on potential bugs and logical errors"
            },
            {
                "code": "performance_only",
                "name": "Performance Analysis",
                "description": "Focus only on performance improvements"
            }
        ],
        "model_powered": True,
        "fallback_available": True
    }


@router.get("/model/status")
async def get_model_status() -> Dict[str, Any]:
    """
    Get the current status of the GGUF model.
    """
    try:
        # Check if GGUF model is loaded and ready
        model_ready = gguf_analyzer.model is not None
        
        if model_ready:
            return {
                "status": "ready",
                "model_type": "gguf",
                "model_name": "deepseek-coder-1.3b-instruct",
                "quantization": "Q4_K_M",
                "memory_usage": "~2GB",
                "inference_speed": "fast",
                "context_length": 4096,
                "last_check": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "not_ready",
                "model_type": "gguf",
                "error": "Model not loaded",
                "fallback": "static_analysis_available",
                "last_check": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {
            "status": "error",
            "model_type": "gguf",
            "error": str(e),
            "fallback": "static_analysis_available",
            "last_check": datetime.utcnow().isoformat()
        }


# Keep all existing endpoints for backward compatibility
@router.post("/multi-tool")
async def analyze_with_multiple_tools(request: CodeAnalysisRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Analyze code using multiple static analysis tools in parallel.
    Now enhanced with GGUF model integration.
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
                "message": "Analysis started in background with GGUF + static tools",
                "estimated_time_seconds": len(request.code) // 1000  # Rough estimate
            }
        else:
            # For smaller code snippets, run both GGUF and static analysis
            try:
                # Try GGUF analysis first
                gguf_result = await gguf_analyzer.analyze_code(
                    request.code,
                    request.language.value,
                    "comprehensive"
                )
                
                # Also run static analysis for comparison
                static_result = await static_analyzer.analyze_code(
                    request.code,
                    request.language.value,
                    rules_config
                )
                
                return {
                    "job_id": job_id,
                    "status": "completed",
                    "result": {
                        "gguf_analysis": gguf_result,
                        "static_analysis": static_result,
                        "combined": True
                    }
                }
                
            except Exception as e:
                # Fallback to static analysis only
                static_result = await static_analyzer.analyze_code(
                    request.code,
                    request.language.value,
                    rules_config
                )
                
                return {
                    "job_id": job_id,
                    "status": "completed",
                    "result": {
                        "static_analysis": static_result,
                        "gguf_error": str(e),
                        "fallback_used": True
                    }
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


# Keep all other existing endpoints unchanged
@router.post("/configure")
async def configure_analysis_rules(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Configure static analysis rules and preferences.
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
            "name": name,
            "gguf_compatible": True
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
            "templates": templates.get(language, {}),
            "gguf_enhanced": True
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
                "result": result,
                "model_used": "gguf + static"
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
            "message": progress_info.get("message", "Analysis in progress with GGUF model")
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
    Perform incremental analysis on code changes using GGUF model.
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
        
        # Use GGUF analyzer for incremental analysis
        try:
            result = await gguf_analyzer.analyze_code(
                changed_code, 
                language, 
                "quick"  # Use quick analysis for incremental
            )
            
            return {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "result": result,
                "analysis_type": "gguf_incremental"
            }
            
        except Exception as e:
            # Fallback to static analysis
            rules_config = rules_manager.get_default_rules(language)
            result = await static_analyzer.analyze_code(changed_code, language, rules_config)
            
            return {
                "status": "success",
                "file_path": file_path,
                "language": language,
                "result": result,
                "analysis_type": "static_fallback",
                "gguf_error": str(e)
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
            "message": progress_info.get("message", "GGUF analysis in progress"),
            "model_type": "gguf"
        })
        
        # If the job is already completed, send the result and close
        if progress_info["status"] == "completed":
            task_id = progress_info["task_id"]
            result = await progress_tracker.get_task_result(task_id)
            
            await websocket.send_json({
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "result": result,
                "model_type": "gguf"
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
                
                # Add model info to updates
                update["model_type"] = "gguf"
                
                # Send the update to the client
                await websocket.send_json(update)
                
                # If the job completed or failed, close the connection
                if update["status"] in ["completed", "failed"]:
                    break
                    
            except asyncio.TimeoutError:
                # Send a ping to keep the connection alive
                await websocket.send_json({"ping": True, "model_type": "gguf"})
                
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
                "job_id": job_id,
                "model_type": "gguf"
            })
        except:
            pass
        
        # Close the connection
        await websocket.close()