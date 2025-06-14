from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import uuid
import time
from datetime import datetime

from app.models.requests import CodeAnalysisRequest
from app.models.responses import (
    CodeAnalysisResponse,
    CodeIssue,
    CodeMetrics,
    AnalysisSummary,
    IssueSeverity,
    IssueType
)
from app.services.analyzer import CodeAnalyzerService

router = APIRouter()

# Initialize the analyzer service
analyzer_service = CodeAnalyzerService()


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