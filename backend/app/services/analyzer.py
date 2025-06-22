from typing import Dict, List, Any, Optional
import re
import uuid
import logging
from datetime import datetime

from app.models.requests import SupportedLanguage, AnalysisType
from app.models.responses import (
    CodeIssue,
    CodeMetrics,
    AnalysisSummary,
    IssueSeverity,
    IssueType
)
from app.services.ai_service import ai_analyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeAnalyzerService:
    """
    Service class for analyzing code quality, bugs, and security issues.
    This is a stub implementation for Sprint 1 - will be enhanced with AI in future sprints.
    """
    
    def __init__(self):
        self.language_patterns = {
            SupportedLanguage.PYTHON: {
                "common_issues": [
                    (r"print\(", "Consider using logging instead of print statements", IssueType.STYLE, IssueSeverity.LOW),
                    (r"except:\s*$", "Avoid bare except clauses", IssueType.BUG, IssueSeverity.MEDIUM),
                    (r"eval\(", "Avoid using eval() - CRITICAL security risk: arbitrary code execution", IssueType.SECURITY, IssueSeverity.CRITICAL),
                    (r"exec\(", "Avoid using exec() - CRITICAL security risk: arbitrary code execution", IssueType.SECURITY, IssueSeverity.CRITICAL),
                    (r"import \*", "Avoid wildcard imports", IssueType.STYLE, IssueSeverity.LOW),
                ]
            },
            SupportedLanguage.JAVASCRIPT: {
                "common_issues": [
                    # Security patterns
                    (r"eval\(", "Avoid using eval() - CRITICAL security risk: arbitrary code execution. Use JSON.parse() for data or safer alternatives.", IssueType.SECURITY, IssueSeverity.CRITICAL),
                    (r"innerHTML\s*=.*\+", "Potential XSS vulnerability - user input in innerHTML. Use textContent, createElement, or sanitize input properly.", IssueType.SECURITY, IssueSeverity.HIGH),
                    (r"document\.write\(", "Avoid document.write() as it can introduce XSS vulnerabilities and affects performance. Use DOM manipulation instead.", IssueType.SECURITY, IssueSeverity.MEDIUM),
                    (r"location\.href\s*=.*\+", "Potential open redirect vulnerability. Validate URLs before redirecting.", IssueType.SECURITY, IssueSeverity.MEDIUM),
                    
                    # Performance patterns
                    (r"getElementById.*for.*\(", "DOM query inside loop - cache element reference outside loop for better performance.", IssueType.PERFORMANCE, IssueSeverity.MEDIUM),
                    (r"querySelector.*for.*\(", "DOM query inside loop - cache element reference outside loop for better performance.", IssueType.PERFORMANCE, IssueSeverity.MEDIUM),
                    (r"addEventListener.*function\s*\(", "Consider using arrow functions to maintain lexical 'this' context in event handlers.", IssueType.STYLE, IssueSeverity.LOW),
                    
                    # Modern JavaScript practices
                    (r"var\s+", "Consider using 'const' for constants or 'let' for variables instead of 'var' to avoid hoisting issues and improve scope control.", IssueType.STYLE, IssueSeverity.LOW),
                    (r"==\s*[^=]", "Use strict equality (===) instead of loose equality (==) to avoid unexpected type coercion.", IssueType.BUG, IssueSeverity.MEDIUM),
                    (r"function\s+\w+\s*\([^)]*\)\s*\{[^}]*\breturn\b", "Consider using arrow function syntax for concise function expressions.", IssueType.STYLE, IssueSeverity.LOW),
                    
                    # Error handling and best practices
                    (r"fetch\((?![^)]*\.catch)", "Fetch call missing error handling - add .catch() or use try/catch with async/await.", IssueType.BUG, IssueSeverity.MEDIUM),
                    (r"Promise\.(?!all|race).*(?!\.catch)", "Promise missing error handling - always include .catch() for proper error handling.", IssueType.BUG, IssueSeverity.MEDIUM),
                    (r"setTimeout\(\s*function", "Consider using arrow functions with setTimeout for cleaner syntax and lexical 'this' binding.", IssueType.STYLE, IssueSeverity.LOW),
                    
                    # Code quality patterns
                    (r"console\.log\(", "Remove console.log statements in production code. Use a proper logging library for production applications.", IssueType.STYLE, IssueSeverity.LOW),
                    (r"alert\(", "Avoid alert() in production - use proper UI notifications or modal dialogs.", IssueType.STYLE, IssueSeverity.LOW),
                    (r"confirm\(", "Consider using custom modal dialogs instead of browser confirm() for better UX.", IssueType.STYLE, IssueSeverity.LOW),
                    
                    # Memory and resource management
                    (r"addEventListener.*(?!removeEventListener)", "Remember to remove event listeners to prevent memory leaks, especially in SPAs.", IssueType.MAINTAINABILITY, IssueSeverity.MEDIUM),
                    (r"setInterval\(.*(?!clearInterval)", "Ensure intervals are cleared with clearInterval() to prevent memory leaks.", IssueType.BUG, IssueSeverity.MEDIUM),
                    (r"setTimeout\(.*(?!clearTimeout)", "Consider clearing timeouts with clearTimeout() when component unmounts or when no longer needed.", IssueType.MAINTAINABILITY, IssueSeverity.LOW),
                    
                    # Constructive suggestions for clean code
                    (r"function\s+\w+\s*\([^)]*\)\s*\{[^}]*\}", "Great function structure! Consider adding JSDoc documentation with @param, @returns, and @example tags for better maintainability.", IssueType.STYLE, IssueSeverity.LOW),
                    (r"^(?!.*\/\*\*).*function", "Consider adding JSDoc comments to document function purpose, parameters, and return values.", IssueType.MAINTAINABILITY, IssueSeverity.LOW),
                    (r"function.*\{[^}]*return[^}]*\}(?!.*catch)", "Consider adding error handling with try-catch blocks to make the function more robust.", IssueType.MAINTAINABILITY, IssueSeverity.LOW),
                ]
            },
            SupportedLanguage.TYPESCRIPT: {
                "common_issues": [
                    (r"console\.log\(", "Remove console.log statements in production", IssueType.STYLE, IssueSeverity.LOW),
                    (r"any\s*[;,)]", "Avoid using 'any' type - use specific types", IssueType.STYLE, IssueSeverity.MEDIUM),
                    (r"@ts-ignore", "Avoid @ts-ignore - fix the underlying issue", IssueType.MAINTAINABILITY, IssueSeverity.MEDIUM),
                ]
            },
            SupportedLanguage.JAVA: {
                "common_issues": [
                    (r"System\.out\.print", "Use logging framework instead of System.out", IssueType.STYLE, IssueSeverity.LOW),
                    (r"catch\s*\([^)]*\)\s*\{\s*\}", "Empty catch block - handle exceptions properly", IssueType.BUG, IssueSeverity.HIGH),
                    (r"==\s*null", "Consider using Objects.equals() for null-safe comparison", IssueType.BUG, IssueSeverity.MEDIUM),
                ]
            },
            SupportedLanguage.CPP: {
                "common_issues": [
                    (r"malloc\(", "Consider using smart pointers instead of malloc", IssueType.MAINTAINABILITY, IssueSeverity.MEDIUM),
                    (r"free\(", "Ensure proper memory management with free()", IssueType.BUG, IssueSeverity.HIGH),
                    (r"gets\(", "Avoid gets() - use fgets() instead", IssueType.SECURITY, IssueSeverity.CRITICAL),
                    (r"strcpy\(", "Avoid strcpy() - HIGH risk: buffer overflow vulnerability. Use strncpy() or safer alternatives.", IssueType.SECURITY, IssueSeverity.HIGH),
                ]
            }
        }
    
    async def analyze_code(
        self,
        code: str,
        language: SupportedLanguage,
        analysis_type: AnalysisType = AnalysisType.FULL,
        filename: Optional[str] = None,
        include_suggestions: bool = True,
        include_explanations: bool = True,
        severity_threshold: Optional[str] = "low"
    ) -> Dict[str, Any]:
        """
        Analyze the provided code and return issues, metrics, and suggestions.
        Uses the DeepSeek Coder AI model for comprehensive code analysis.
        """
        try:
            # Use AI model for code analysis
            logger.info(f"Analyzing code with AI model: {language.value}, analysis type: {analysis_type.value}")
            
            # Create a proper request object for the AI analyzer
            from app.models.requests import CodeAnalysisRequest
            request = CodeAnalysisRequest(
                code=code,
                language=language,
                filename=filename,
                analysis_type=analysis_type,
                include_suggestions=include_suggestions,
                include_explanations=include_explanations,
                severity_threshold=severity_threshold or "low"
            )
            
            ai_result = await ai_analyzer.analyze_code(request)
            
            # If AI analysis succeeded, return the result
            if ai_result and "issues" in ai_result:
                logger.info(f"AI analysis completed successfully with {len(ai_result['issues'])} issues")
                return ai_result
            
            # If AI analysis failed, fall back to pattern matching
            logger.warning("AI analysis failed, falling back to pattern matching")
        except Exception as e:
            logger.error(f"Error during AI analysis: {str(e)}")
            logger.warning("Falling back to pattern matching due to AI error")
        
        # Fallback: Basic code analysis using pattern matching
        issues = self._detect_issues(code, language, analysis_type)
        metrics = self._calculate_metrics(code, language)
        summary = self._generate_summary(issues, metrics)
        suggestions = self._generate_suggestions(code, language, issues) if include_suggestions else []
        
        return {
            "issues": issues,
            "metrics": metrics,
            "summary": summary,
            "suggestions": suggestions
        }
    
    def _detect_issues(self, code: str, language: SupportedLanguage, analysis_type: AnalysisType) -> List[CodeIssue]:
        """Detect issues in the code using pattern matching."""
        issues = []
        lines = code.split('\n')
        
        # Get language-specific patterns
        patterns = self.language_patterns.get(language, {}).get("common_issues", [])
        
        for line_num, line in enumerate(lines, 1):
            for pattern, description, issue_type, severity in patterns:
                if re.search(pattern, line):
                    # Filter by analysis type
                    if self._should_include_issue(issue_type, analysis_type):
                        issue = CodeIssue(
                            id=f"issue_{uuid.uuid4().hex[:8]}",
                            type=issue_type,
                            severity=severity,
                            title=description,
                            description=f"Found on line {line_num}: {description}",
                            line_number=line_num,
                            code_snippet=line.strip(),
                            suggestion=self._get_suggestion_for_issue(pattern, issue_type),
                            explanation=self._get_explanation_for_issue(pattern, issue_type),
                            confidence=0.8
                        )
                        issues.append(issue)
        
        # Add some general issues based on code characteristics
        issues.extend(self._detect_general_issues(code, language))
        
        return issues
    
    def _should_include_issue(self, issue_type: IssueType, analysis_type: AnalysisType) -> bool:
        """Determine if an issue should be included based on analysis type."""
        if analysis_type == AnalysisType.FULL:
            return True
        elif analysis_type == AnalysisType.BUGS_ONLY:
            return issue_type == IssueType.BUG
        elif analysis_type == AnalysisType.SECURITY_ONLY:
            return issue_type == IssueType.SECURITY
        elif analysis_type == AnalysisType.PERFORMANCE_ONLY:
            return issue_type == IssueType.PERFORMANCE
        elif analysis_type == AnalysisType.STYLE_ONLY:
            return issue_type == IssueType.STYLE
        return True
    
    def _detect_general_issues(self, code: str, language: SupportedLanguage) -> List[CodeIssue]:
        """Detect general code quality issues."""
        issues = []
        lines = code.split('\n')
        
        # Check for very long lines
        for line_num, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append(CodeIssue(
                    id=f"issue_{uuid.uuid4().hex[:8]}",
                    type=IssueType.STYLE,
                    severity=IssueSeverity.LOW,
                    title="Line too long",
                    description=f"Line {line_num} exceeds 120 characters ({len(line)} chars)",
                    line_number=line_num,
                    code_snippet=line[:50] + "..." if len(line) > 50 else line,
                    suggestion="Consider breaking this line into multiple lines",
                    confidence=0.9
                ))
        
        # Check for missing documentation (functions without docstrings/comments)
        if language == SupportedLanguage.PYTHON:
            func_pattern = r"^\s*def\s+\w+\s*\("
            for line_num, line in enumerate(lines, 1):
                if re.search(func_pattern, line):
                    # Check if next few lines have docstring
                    has_docstring = False
                    for i in range(line_num, min(line_num + 3, len(lines))):
                        if '"""' in lines[i] or "'''" in lines[i]:
                            has_docstring = True
                            break
                    
                    if not has_docstring:
                        issues.append(CodeIssue(
                            id=f"issue_{uuid.uuid4().hex[:8]}",
                            type=IssueType.STYLE,
                            severity=IssueSeverity.LOW,
                            title="Missing function documentation",
                            description=f"Function on line {line_num} lacks documentation",
                            line_number=line_num,
                            code_snippet=line.strip(),
                            suggestion="Add a docstring to describe the function's purpose, parameters, and return value",
                            confidence=0.7
                        ))
        
        return issues
    
    def _calculate_metrics(self, code: str, language: SupportedLanguage) -> CodeMetrics:
        """Calculate basic code metrics."""
        lines = code.split('\n')
        
        # Count non-empty lines
        lines_of_code = len([line for line in lines if line.strip()])
        
        # Simple complexity calculation (count of control structures)
        complexity_keywords = ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'with']
        complexity_score = 1.0  # Base complexity
        
        for line in lines:
            for keyword in complexity_keywords:
                if re.search(rf'\b{keyword}\b', line):
                    complexity_score += 0.5
        
        # Calculate maintainability index (simplified)
        # Real formula is more complex, this is a stub
        maintainability_index = max(0, min(100, 100 - (complexity_score * 2) - (lines_of_code * 0.1)))
        
        return CodeMetrics(
            lines_of_code=lines_of_code,
            complexity_score=complexity_score,
            maintainability_index=maintainability_index,
            duplication_percentage=0.0  # Stub - would need more sophisticated analysis
        )
    
    def _generate_summary(self, issues: List[CodeIssue], metrics: CodeMetrics) -> AnalysisSummary:
        """Generate analysis summary."""
        # Count issues by severity
        critical_count = len([i for i in issues if i.severity == IssueSeverity.CRITICAL])
        high_count = len([i for i in issues if i.severity == IssueSeverity.HIGH])
        medium_count = len([i for i in issues if i.severity == IssueSeverity.MEDIUM])
        low_count = len([i for i in issues if i.severity == IssueSeverity.LOW])
        
        # Calculate overall score (0-10) with more reasonable penalties
        base_score = 10.0
        score_deduction = (critical_count * 2) + (high_count * 1) + (medium_count * 0.4) + (low_count * 0.1)
        
        # More gradual scoring for clean code
        if score_deduction == 0:
            overall_score = 8.0  # Clean code gets 8/10
        elif score_deduction <= 0.5:
            overall_score = 7.5  # Minor issues get 7.5/10
        else:
            overall_score = max(4.0, min(10.0, base_score - score_deduction))  # Minimum 4.0 for working code
        
        # Generate recommendation
        if overall_score >= 8:
            recommendation = "Excellent code quality with minimal issues"
        elif overall_score >= 6:
            recommendation = "Good code quality with some improvements needed"
        elif overall_score >= 4:
            recommendation = "Moderate code quality - several issues should be addressed"
        else:
            recommendation = "Poor code quality - significant improvements required"
        
        return AnalysisSummary(
            total_issues=len(issues),
            critical_issues=critical_count,
            high_issues=high_count,
            medium_issues=medium_count,
            low_issues=low_count,
            overall_score=overall_score,
            recommendation=recommendation
        )
    
    def _generate_suggestions(self, code: str, language: SupportedLanguage, issues: List[CodeIssue]) -> List[str]:
        """Generate general improvement suggestions."""
        suggestions = []
        
        # Language-specific suggestions
        if language == SupportedLanguage.PYTHON:
            suggestions.extend([
                "Consider adding type hints for better code documentation and IDE support",
                "Use virtual environments to manage dependencies",
                "Follow PEP 8 style guidelines for consistent formatting"
            ])
        elif language == SupportedLanguage.JAVASCRIPT:
            # Prioritize actionable suggestions based on code analysis
            code_lines = len(code.split('\n'))
            if "/**" not in code and "function" in code:
                suggestions.append("Add JSDoc comments to document function parameters and return values")
            if "try" not in code.lower() and ("fetch" in code or "async" in code):
                suggestions.append("Implement proper error handling with try-catch blocks for async operations")
            if code_lines > 20:
                suggestions.append("Consider using TypeScript for better type safety in larger codebases")
            if "eslint" not in code and code_lines > 10:
                suggestions.append("Use ESLint and Prettier for consistent code formatting")
        elif language == SupportedLanguage.JAVA:
            suggestions.extend([
                "Use meaningful variable and method names",
                "Implement proper exception handling",
                "Consider using design patterns for better code organization"
            ])
        
        # Add suggestions based on detected issues
        if any(issue.type == IssueType.SECURITY for issue in issues):
            suggestions.append("Review security best practices for your programming language")
        
        if any(issue.type == IssueType.PERFORMANCE for issue in issues):
            suggestions.append("Consider profiling your code to identify performance bottlenecks")
        
        # Smart general suggestions based on code complexity
        code_lines = len(code.split('\n'))
        
        if code_lines <= 10:
            # For simple code, focus on immediate improvements
            if "test" not in code.lower() and "function" in code:
                suggestions.append("Add a simple unit test to verify function behavior")
        else:
            # For complex code, suggest more comprehensive improvements
            suggestions.extend([
                "Add comprehensive unit tests to improve code reliability",
                "Use version control (Git) to track changes and collaborate effectively",
                "Consider code reviews with team members before merging changes"
            ])
        
        # Smart limiting: fewer suggestions for simple code
        max_suggestions = 3 if code_lines <= 10 else 5
        return suggestions[:max_suggestions]
    
    def _get_suggestion_for_issue(self, pattern: str, issue_type: IssueType) -> str:
        """Get specific suggestion for an issue pattern."""
        suggestions_map = {
            r"print\(": "Use the logging module instead: import logging; logging.info('message')",
            r"console\.log\(": "Use a proper logging library or remove before production",
            r"eval\(": "Use safer alternatives like JSON.parse() or specific parsing functions",
            r"==\s*[^=]": "Replace == with === for strict equality comparison",
            r"var\s+": "Use 'const' for constants or 'let' for variables that change"
        }
        
        for pat, suggestion in suggestions_map.items():
            if pat == pattern:
                return suggestion
        
        return "Review this code pattern and consider alternatives"
    
    def _get_explanation_for_issue(self, pattern: str, issue_type: IssueType) -> str:
        """Get detailed explanation for an issue pattern."""
        explanations_map = {
            r"print\(": "Print statements are not suitable for production applications. Use logging for better control over output levels and destinations.",
            r"eval\(": "The eval() function can execute arbitrary code, making it a significant security risk. It can lead to code injection attacks.",
            r"==\s*[^=]": "The == operator performs type coercion, which can lead to unexpected results. Use === for strict equality without type conversion."
        }
        
        for pat, explanation in explanations_map.items():
            if pat == pattern:
                return explanation
        
        return "This pattern may indicate a potential issue that should be reviewed."