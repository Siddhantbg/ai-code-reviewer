from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class SupportedLanguage(str, Enum):
    """Supported programming languages for code analysis."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    GO = "go"
    RUST = "rust"
    PHP = "php"
    RUBY = "ruby"


class AnalysisType(str, Enum):
    """Types of analysis to perform on the code."""
    FULL = "full"  # Complete analysis including bugs, security, performance
    BUGS_ONLY = "bugs_only"  # Only bug detection
    SECURITY_ONLY = "security_only"  # Only security analysis
    PERFORMANCE_ONLY = "performance_only"  # Only performance suggestions
    STYLE_ONLY = "style_only"  # Only code style suggestions


class CodeAnalysisRequest(BaseModel):
    """Request model for code analysis endpoint."""
    
    code: str = Field(
        ...,
        description="The source code to analyze",
        min_length=1,
        max_length=50000  # Limit code size to prevent abuse
    )
    
    language: SupportedLanguage = Field(
        ...,
        description="Programming language of the code"
    )
    
    analysis_type: AnalysisType = Field(
        default=AnalysisType.FULL,
        description="Type of analysis to perform"
    )
    
    filename: Optional[str] = Field(
        default=None,
        description="Optional filename for context",
        max_length=255
    )
    
    include_suggestions: bool = Field(
        default=True,
        description="Whether to include improvement suggestions"
    )
    
    include_explanations: bool = Field(
        default=True,
        description="Whether to include detailed explanations for issues"
    )
    
    severity_threshold: Optional[str] = Field(
        default="low",
        description="Minimum severity level to report (low, medium, high, critical)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "code": "def hello_world():\n    print('Hello, World!')\n    return True",
                "language": "python",
                "analysis_type": "full",
                "filename": "hello.py",
                "include_suggestions": True,
                "include_explanations": True,
                "severity_threshold": "low"
            }
        }