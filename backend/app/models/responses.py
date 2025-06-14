from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class IssueSeverity(str, Enum):
    """Severity levels for code issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueType(str, Enum):
    """Types of code issues."""
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    MAINTAINABILITY = "maintainability"
    COMPLEXITY = "complexity"


class CodeIssue(BaseModel):
    """Represents a single code issue found during analysis."""
    
    id: str = Field(..., description="Unique identifier for the issue")
    type: IssueType = Field(..., description="Type of the issue")
    severity: IssueSeverity = Field(..., description="Severity level of the issue")
    title: str = Field(..., description="Brief title of the issue")
    description: str = Field(..., description="Detailed description of the issue")
    
    line_number: Optional[int] = Field(
        default=None,
        description="Line number where the issue occurs"
    )
    
    column_number: Optional[int] = Field(
        default=None,
        description="Column number where the issue occurs"
    )
    
    code_snippet: Optional[str] = Field(
        default=None,
        description="Code snippet showing the problematic code"
    )
    
    suggestion: Optional[str] = Field(
        default=None,
        description="Suggested fix or improvement"
    )
    
    explanation: Optional[str] = Field(
        default=None,
        description="Detailed explanation of why this is an issue"
    )
    
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence level of the analysis (0.0 to 1.0)"
    )


class CodeMetrics(BaseModel):
    """Code quality metrics."""
    
    lines_of_code: int = Field(..., description="Total lines of code")
    complexity_score: float = Field(..., description="Cyclomatic complexity score")
    maintainability_index: float = Field(..., description="Maintainability index (0-100)")
    test_coverage: Optional[float] = Field(
        default=None,
        description="Test coverage percentage if available"
    )
    duplication_percentage: float = Field(
        default=0.0,
        description="Code duplication percentage"
    )


class AnalysisSummary(BaseModel):
    """Summary of the code analysis results."""
    
    total_issues: int = Field(..., description="Total number of issues found")
    critical_issues: int = Field(..., description="Number of critical issues")
    high_issues: int = Field(..., description="Number of high severity issues")
    medium_issues: int = Field(..., description="Number of medium severity issues")
    low_issues: int = Field(..., description="Number of low severity issues")
    
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Overall code quality score (0-10)"
    )
    
    recommendation: str = Field(
        ...,
        description="Overall recommendation based on analysis"
    )


class CodeAnalysisResponse(BaseModel):
    """Response model for code analysis endpoint."""
    
    analysis_id: str = Field(..., description="Unique identifier for this analysis")
    timestamp: datetime = Field(..., description="When the analysis was performed")
    
    language: str = Field(..., description="Programming language analyzed")
    filename: Optional[str] = Field(default=None, description="Filename if provided")
    
    issues: List[CodeIssue] = Field(
        default=[],
        description="List of issues found in the code"
    )
    
    metrics: CodeMetrics = Field(..., description="Code quality metrics")
    summary: AnalysisSummary = Field(..., description="Analysis summary")
    
    processing_time_ms: float = Field(
        ...,
        description="Time taken to process the analysis in milliseconds"
    )
    
    suggestions: List[str] = Field(
        default=[],
        description="General improvement suggestions"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "analysis_123456",
                "timestamp": "2024-01-15T10:30:00Z",
                "language": "python",
                "filename": "hello.py",
                "issues": [
                    {
                        "id": "issue_001",
                        "type": "style",
                        "severity": "low",
                        "title": "Missing docstring",
                        "description": "Function lacks documentation",
                        "line_number": 1,
                        "suggestion": "Add a docstring to describe the function",
                        "confidence": 0.9
                    }
                ],
                "metrics": {
                    "lines_of_code": 3,
                    "complexity_score": 1.0,
                    "maintainability_index": 85.0,
                    "duplication_percentage": 0.0
                },
                "summary": {
                    "total_issues": 1,
                    "critical_issues": 0,
                    "high_issues": 0,
                    "medium_issues": 0,
                    "low_issues": 1,
                    "overall_score": 8.5,
                    "recommendation": "Good code quality with minor improvements needed"
                },
                "processing_time_ms": 150.5,
                "suggestions": [
                    "Consider adding type hints for better code documentation",
                    "Add unit tests to improve code reliability"
                ]
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    
    status: str = Field(..., description="Health status of the service")
    message: str = Field(..., description="Health check message")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "AI Code Review Assistant is running",
                "version": "1.0.0",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the error occurred"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid input provided",
                "details": {
                    "field": "code",
                    "issue": "Code cannot be empty"
                },
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }