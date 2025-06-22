import asyncio
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import aiofiles
import hashlib

from app.models.requests import SupportedLanguage
from app.models.responses import (
    CodeIssue,
    CodeMetrics,
    AnalysisSummary,
    IssueSeverity,
    IssueType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StaticAnalysisOrchestrator:
    """Orchestrates multiple static analysis tools and merges their results."""
    
    def __init__(self, cache_service=None):
        self.cache_service = cache_service
        self.analyzers = {
            SupportedLanguage.JAVASCRIPT: [ESLintAnalyzer()],
            SupportedLanguage.TYPESCRIPT: [ESLintAnalyzer()],
            SupportedLanguage.PYTHON: [PylintAnalyzer(), BanditAnalyzer()],
        }
        # Rate limiting for static analysis tools
        self.analysis_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent analyses
        self.subprocess_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent subprocesses
    
    async def analyze_code(self, code: str, language: str, rules_config: Optional[Dict] = None) -> Dict[str, Any]:
        """Run static analysis on code using appropriate tools for the language."""
        try:
            # Generate a cache key based on code content and rules
            cache_key = self._generate_cache_key(code, language, rules_config)
            
            # Try to get cached results
            if self.cache_service:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for analysis of {language} code")
                    return cached_result
            
            # Get appropriate analyzers for the language
            language_enum = SupportedLanguage(language)
            available_analyzers = self.analyzers.get(language_enum, [])
            
            if not available_analyzers:
                logger.warning(f"No static analyzers available for {language}")
                return self._generate_empty_result(language)
            
            # Run analyzers in parallel
            logger.info(f"Running {len(available_analyzers)} analyzers for {language} code")
            results = await self._run_parallel_analysis(available_analyzers, code, rules_config)
            
            # Merge results from all analyzers
            merged_result = self._merge_results(results)
            
            # Cache the results
            if self.cache_service:
                await self.cache_service.set(cache_key, merged_result)
            
            return merged_result
            
        except Exception as e:
            logger.error(f"Error during static analysis: {str(e)}")
            return self._generate_error_result(str(e), language)
    
    async def _run_parallel_analysis(self, analyzers: List, code: str, rules_config: Optional[Dict] = None) -> List[Dict]:
        """Run multiple analyzers in parallel using asyncio with rate limiting."""
        async with self.analysis_semaphore:
            tasks = []
            for analyzer in analyzers:
                config = rules_config.get(analyzer.tool_id, {}) if rules_config else {}
                # Wrap each analyzer task with subprocess rate limiting
                task = self._run_analyzer_with_rate_limit(analyzer, code, config)
                tasks.append(task)
            
            # Run all analysis tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        filtered_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Analyzer {analyzers[i].tool_id} failed: {str(result)}")
            else:
                filtered_results.append(result)
        
        return filtered_results
    
    async def _run_analyzer_with_rate_limit(self, analyzer, code: str, config: Dict) -> Dict[str, Any]:
        """Run a single analyzer with subprocess rate limiting."""
        async with self.subprocess_semaphore:
            try:
                return await asyncio.wait_for(
                    analyzer.analyze(code, config),
                    timeout=60.0  # 1 minute timeout for each analyzer
                )
            except asyncio.TimeoutError:
                logger.error(f"Analyzer {analyzer.tool_id} timed out after 60 seconds")
                return {"issues": [], "error": f"{analyzer.tool_id} analysis timed out"}
            except Exception as e:
                logger.error(f"Analyzer {analyzer.tool_id} failed: {str(e)}")
                return {"issues": [], "error": str(e)}
    
    def _merge_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Merge results from multiple analyzers into a single result."""
        if not results:
            return self._generate_empty_result("unknown")
        
        # Initialize merged structure
        merged = {
            "issues": [],
            "metrics": {
                "complexity_score": 0,
                "maintainability_index": 0,
                "issue_count": 0,
                "bug_count": 0,
                "security_count": 0,
                "performance_count": 0,
                "style_count": 0,
                "lines_of_code": 0
            },
            "summary": {
                "overall_score": 0,
                "quality_level": "",
                "summary": "",
                "top_issues": [],
                "language": "",
                "total_issues": 0,
                "critical_issues": 0,
                "high_issues": 0,
                "medium_issues": 0,
                "low_issues": 0,
                "recommendation": ""
            },
            "suggestions": []
        }
        
        # Combine issues from all analyzers
        all_issues = []
        for result in results:
            all_issues.extend(result.get("issues", []))
            
            # Update metrics
            result_metrics = result.get("metrics", {})
            merged["metrics"]["complexity_score"] += result_metrics.get("complexity_score", 0)
            merged["metrics"]["maintainability_index"] += result_metrics.get("maintainability_index", 0)
            merged["metrics"]["issue_count"] += result_metrics.get("issue_count", 0)
            merged["metrics"]["bug_count"] += result_metrics.get("bug_count", 0)
            merged["metrics"]["security_count"] += result_metrics.get("security_count", 0)
            merged["metrics"]["performance_count"] += result_metrics.get("performance_count", 0)
            merged["metrics"]["style_count"] += result_metrics.get("style_count", 0)
            
            # Take the max for lines of code
            merged["metrics"]["lines_of_code"] = max(
                merged["metrics"]["lines_of_code"],
                result_metrics.get("lines_of_code", 0)
            )
            
            # Collect suggestions with smart filtering
            suggestions = result.get("suggestions", [])
            merged["suggestions"].extend(suggestions)
        
        # Average the metrics that were summed
        if results:
            merged["metrics"]["complexity_score"] /= len(results)
            merged["metrics"]["maintainability_index"] /= len(results)
        
        # Sort issues by severity
        all_issues.sort(key=lambda x: {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3
        }.get(x.severity, 4))
        
        merged["issues"] = all_issues
        
        # Update summary
        merged["summary"]["total_issues"] = len(all_issues)
        merged["summary"]["critical_issues"] = sum(1 for i in all_issues if i.severity == IssueSeverity.CRITICAL)
        merged["summary"]["high_issues"] = sum(1 for i in all_issues if i.severity == IssueSeverity.HIGH)
        merged["summary"]["medium_issues"] = sum(1 for i in all_issues if i.severity == IssueSeverity.MEDIUM)
        merged["summary"]["low_issues"] = sum(1 for i in all_issues if i.severity == IssueSeverity.LOW)
        
        # Calculate overall score (1-10 scale, more reasonable weighting)
        issue_weights = {
            IssueSeverity.CRITICAL: 2.0,  # Reduced from 2.5
            IssueSeverity.HIGH: 1.0,      # Reduced from 1.5
            IssueSeverity.MEDIUM: 0.4,    # Reduced from 0.8
            IssueSeverity.LOW: 0.1        # Reduced from 0.3
        }
        
        weighted_issues = sum(issue_weights.get(i.severity, 0) for i in all_issues)
        base_score = 10
        
        # More gradual score reduction with better minimum scores
        if weighted_issues == 0:
            overall_score = 8  # Clean code gets 8/10 instead of 10/10
        elif weighted_issues <= 1:
            overall_score = 7  # Minor issues get 7/10
        else:
            score_reduction = min(weighted_issues * 0.8, 6)  # Cap reduction at 6 to ensure score >= 4
            overall_score = base_score - score_reduction
            
        merged["summary"]["overall_score"] = max(4, min(10, overall_score))  # Minimum score of 4 for working code
        
        # Set quality level based on score
        if merged["summary"]["overall_score"] >= 9:
            merged["summary"]["quality_level"] = "Excellent"
        elif merged["summary"]["overall_score"] >= 7:
            merged["summary"]["quality_level"] = "Good"
        elif merged["summary"]["overall_score"] >= 5:
            merged["summary"]["quality_level"] = "Average"
        elif merged["summary"]["overall_score"] >= 3:
            merged["summary"]["quality_level"] = "Poor"
        else:
            merged["summary"]["quality_level"] = "Critical"
        
        # Set top issues
        merged["summary"]["top_issues"] = [i.title for i in all_issues[:3]]
        
        # Generate summary text
        if not all_issues:
            merged["summary"]["summary"] = "No issues detected by static analysis tools."
        else:
            critical_high = merged["summary"]["critical_issues"] + merged["summary"]["high_issues"]
            if critical_high > 0:
                merged["summary"]["summary"] = f"Found {critical_high} critical/high issues that need immediate attention."
            else:
                merged["summary"]["summary"] = f"Found {len(all_issues)} issues of lower severity."
        
        # Generate recommendation
        if merged["summary"]["critical_issues"] > 0:
            merged["summary"]["recommendation"] = "Address critical security and bug issues immediately."
        elif merged["summary"]["high_issues"] > 0:
            merged["summary"]["recommendation"] = "Fix high-priority issues before deploying to production."
        elif merged["summary"]["medium_issues"] > 0:
            merged["summary"]["recommendation"] = "Consider addressing medium-severity issues to improve code quality."
        elif merged["summary"]["low_issues"] > 0:
            merged["summary"]["recommendation"] = "Minor issues found that could be improved for better code quality."
        else:
            merged["summary"]["recommendation"] = "Code looks good! No significant issues detected."
        
        # Apply smart filtering to suggestions based on code complexity
        code_lines = len(code.split('\n'))
        is_simple_code = code_lines <= 10
        
        if is_simple_code:
            # For simple code, prioritize actionable suggestions and limit to 3
            priority_keywords = ['JSDoc', 'documentation', 'input validation', 'error handling', 'parameter']
            actionable_suggestions = []
            generic_suggestions = []
            
            for suggestion in merged["suggestions"]:
                if any(keyword.lower() in suggestion.lower() for keyword in priority_keywords):
                    actionable_suggestions.append(suggestion)
                else:
                    generic_suggestions.append(suggestion)
            
            # Prioritize actionable over generic for simple code
            merged["suggestions"] = (actionable_suggestions[:3] + generic_suggestions[:0]) if actionable_suggestions else merged["suggestions"][:2]
        else:
            # For complex code, allow more suggestions but still limit them
            merged["suggestions"] = merged["suggestions"][:5]
        
        return merged
    
    def _generate_cache_key(self, code: str, language: str, rules_config: Optional[Dict] = None) -> str:
        """Generate a unique cache key based on code content and analysis parameters."""
        # Create a hash of the code content
        code_hash = hashlib.md5(code.encode()).hexdigest()
        
        # Add language to the key
        key_parts = [code_hash, language]
        
        # Add rules config hash if provided
        if rules_config:
            rules_str = json.dumps(rules_config, sort_keys=True)
            rules_hash = hashlib.md5(rules_str.encode()).hexdigest()
            key_parts.append(rules_hash)
        
        # Join all parts with a separator
        return "_".join(key_parts)
    
    def _generate_empty_result(self, language: str) -> Dict[str, Any]:
        """Generate an empty result when no analyzers are available."""
        return {
            "issues": [],
            "metrics": CodeMetrics(
                complexity_score=0,
                maintainability_index=0,
                issue_count=0,
                bug_count=0,
                security_count=0,
                performance_count=0,
                style_count=0,
                lines_of_code=0
            ).model_dump(),
            "summary": AnalysisSummary(
                overall_score=0,
                quality_level="Unknown",
                summary="No static analysis tools available for this language.",
                top_issues=[],
                language=language,
                total_issues=0,
                critical_issues=0,
                high_issues=0,
                medium_issues=0,
                low_issues=0,
                recommendation="Consider using a supported language for static analysis."
            ).model_dump(),
            "suggestions": []
        }
    
    def _generate_error_result(self, error_message: str, language: str) -> Dict[str, Any]:
        """Generate an error result when analysis fails."""
        return {
            "issues": [CodeIssue(
                id=f"error_{uuid.uuid4().hex[:8]}",
                type=IssueType.BUG,
                severity=IssueSeverity.LOW,
                title="Static Analysis Error",
                description=f"Error during static analysis: {error_message}",
                suggestion="Check the code format and try again."
            ).model_dump()],
            "metrics": CodeMetrics(
                complexity_score=0,
                maintainability_index=0,
                issue_count=1,
                bug_count=1,
                security_count=0,
                performance_count=0,
                style_count=0,
                lines_of_code=0
            ).model_dump(),
            "summary": AnalysisSummary(
                overall_score=0,
                quality_level="Unknown",
                summary=f"Static analysis failed: {error_message}",
                top_issues=["Static Analysis Error"],
                language=language,
                total_issues=1,
                critical_issues=0,
                high_issues=0,
                medium_issues=0,
                low_issues=1,
                recommendation="Check the code format and try again."
            ).model_dump(),
            "suggestions": ["Ensure the code is valid and properly formatted."]
        }


class BaseAnalyzer:
    """Base class for all static code analyzers."""
    
    def __init__(self):
        self.tool_id = "base_analyzer"
    
    async def analyze(self, code: str, config: Dict) -> Dict[str, Any]:
        """Analyze code and return results."""
        raise NotImplementedError("Subclasses must implement analyze()")
    
    async def _write_temp_file(self, code: str, extension: str) -> str:
        """Write code to a temporary file and return the file path."""
        try:
            # Create a temporary file with the appropriate extension
            fd, file_path = tempfile.mkstemp(suffix=extension)
            os.close(fd)  # Close the file descriptor
            
            # Write the code to the file asynchronously
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(code)
            
            return file_path
        except Exception as e:
            logger.error(f"Error writing temporary file: {str(e)}")
            raise


class ESLintAnalyzer(BaseAnalyzer):
    """Analyzer for JavaScript/TypeScript using ESLint."""
    
    def __init__(self):
        super().__init__()
        self.tool_id = "eslint"
    
    async def analyze(self, code: str, config: Dict) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript code using ESLint."""
        try:
            # Determine file extension based on config or default to .js
            is_typescript = config.get("typescript", False)
            extension = ".ts" if is_typescript else ".js"
            
            # Write code to temporary file
            file_path = await self._write_temp_file(code, extension)
            
            try:
                # Execute ESLint on the file
                eslint_result = await self._execute_eslint(file_path, config)
                
                # Convert ESLint results to our format
                return self._convert_results(eslint_result, code)
            finally:
                # Clean up temporary file
                if os.path.exists(file_path):
                    os.unlink(file_path)
        
        except Exception as e:
            logger.error(f"ESLint analysis error: {str(e)}")
            return self._generate_error_result(str(e))
    
    async def _execute_eslint(self, file_path: str, config: Dict) -> Dict:
        """Execute ESLint on the given file and return the results."""
        try:
            # Create a temporary ESLint config file if custom config provided
            config_path = None
            if config.get("rules"):
                config_path = await self._create_eslint_config(config)
            
            # Build the ESLint command
            cmd = ["npx", "eslint", "--format", "json", file_path]
            if config_path:
                cmd.extend(["--config", config_path])
            
            # Execute ESLint process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Get output with reduced timeout for better performance
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            
            # Clean up config file if created
            if config_path and os.path.exists(config_path):
                os.unlink(config_path)
            
            # Parse the JSON output
            if stdout:
                try:
                    return json.loads(stdout.decode())
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse ESLint output: {stdout.decode()}")
            
            # If no valid output, check for errors
            if stderr:
                logger.warning(f"ESLint stderr: {stderr.decode()}")
            
            # Return empty result if no output
            return []
            
        except asyncio.TimeoutError:
            logger.error("ESLint execution timed out")
            raise Exception("ESLint analysis timed out")
        except Exception as e:
            logger.error(f"Error executing ESLint: {str(e)}")
            raise
    
    async def _create_eslint_config(self, config: Dict) -> str:
        """Create a temporary ESLint config file from the provided config."""
        eslint_config = {
            "env": {
                "browser": True,
                "es2021": True,
                "node": True
            },
            "extends": config.get("extends", ["eslint:recommended"]),
            "rules": config.get("rules", {})
        }
        
        # Add parser options for TypeScript if needed
        if config.get("typescript", False):
            eslint_config["parser"] = "@typescript-eslint/parser"
            eslint_config["plugins"] = ["@typescript-eslint"]
            eslint_config["parserOptions"] = {
                "ecmaVersion": 12,
                "sourceType": "module"
            }
        
        # Write config to temporary file
        fd, config_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        
        async with aiofiles.open(config_path, 'w') as f:
            await f.write(json.dumps(eslint_config))
        
        return config_path
    
    def _convert_results(self, eslint_result: List, code: str) -> Dict[str, Any]:
        """Convert ESLint results to our standardized format."""
        # Count lines of code
        lines_of_code = len([line for line in code.split('\n') if line.strip()])
        
        # Initialize issues list
        issues = []
        
        # Smart severity mapping based on rule type and impact
        def get_eslint_severity(rule_id, eslint_severity):
            # CRITICAL: Code that can break functionality
            critical_rules = ['no-undef', 'no-redeclare', 'no-dupe-keys', 'no-func-assign']
            
            # HIGH: Logic errors and security issues  
            high_rules = ['no-eval', 'no-implied-eval', 'no-new-func', 'no-script-url',
                         'eqeqeq', 'no-unreachable', 'no-constant-condition']
            
            # MEDIUM: Potential issues and important best practices
            medium_rules = ['no-unused-vars', 'no-use-before-define', 'no-shadow',
                           'prefer-const', 'no-var']
            
            # LOW: Style and formatting (most ESLint rules)
            low_rules = ['no-console', 'quotes', 'semi', 'indent', 'comma-dangle',
                        'space-before-function-paren', 'max-len', 'camelcase']
            
            if rule_id in critical_rules:
                return IssueSeverity.CRITICAL
            elif rule_id in high_rules:
                return IssueSeverity.HIGH  
            elif rule_id in medium_rules:
                return IssueSeverity.MEDIUM
            elif rule_id in low_rules:
                return IssueSeverity.LOW
            else:
                # Default mapping for unknown rules
                severity_map = {
                    2: IssueSeverity.MEDIUM,  # ESLint error -> MEDIUM (was HIGH)
                    1: IssueSeverity.LOW,     # ESLint warning -> LOW (was MEDIUM)
                    0: IssueSeverity.LOW      # ESLint info -> LOW
                }
                return severity_map.get(eslint_severity, IssueSeverity.LOW)
        
        # Map ESLint rule categories to our issue types
        type_map = {
            "possible-errors": IssueType.BUG,
            "best-practices": IssueType.MAINTAINABILITY,
            "variables": IssueType.BUG,
            "stylistic-issues": IssueType.STYLE,
            "es6": IssueType.MAINTAINABILITY,
            "security": IssueType.SECURITY,
            "performance": IssueType.PERFORMANCE
        }
        
        # Process each ESLint result file
        for file_result in eslint_result:
            for message in file_result.get("messages", []):
                # Determine issue type based on rule id or category
                rule_id = message.get("ruleId", "")
                issue_type = IssueType.MAINTAINABILITY  # Default type
                
                # Try to map rule to a more specific type
                if "security" in rule_id.lower():
                    issue_type = IssueType.SECURITY
                elif "performance" in rule_id.lower():
                    issue_type = IssueType.PERFORMANCE
                elif rule_id.startswith("no-") or "error" in rule_id.lower():
                    issue_type = IssueType.BUG
                elif "style" in rule_id.lower() or "format" in rule_id.lower():
                    issue_type = IssueType.STYLE
                
                # Create the issue with proper severity classification
                issue = CodeIssue(
                    id=f"eslint_{uuid.uuid4().hex[:8]}",
                    type=issue_type,
                    severity=get_eslint_severity(rule_id, message.get("severity", 1)),
                    title=f"ESLint: {rule_id}" if rule_id else "ESLint Issue",
                    description=message.get("message", "Unknown ESLint issue"),
                    line_number=message.get("line"),
                    column_number=message.get("column"),
                    suggestion=f"Fix according to ESLint rule: {rule_id}" if rule_id else "Review code"
                )
                
                issues.append(issue.model_dump())
        
        # Count issues by type (issues are now dictionaries)
        bug_count = sum(1 for i in issues if i.get("type") == IssueType.BUG.value)
        security_count = sum(1 for i in issues if i.get("type") == IssueType.SECURITY.value)
        performance_count = sum(1 for i in issues if i.get("type") == IssueType.PERFORMANCE.value)
        style_count = sum(1 for i in issues if i.get("type") == IssueType.STYLE.value)
        
        # Calculate metrics
        # More issues = higher complexity score (1-10 scale)
        issue_count = len(issues)
        complexity_factor = min(issue_count / 5, 1.0)  # Cap at 1.0
        complexity_score = 5 + (complexity_factor * 5)  # Scale to 5-10
        
        # Maintainability decreases with more issues
        maintainability_index = max(0, 100 - (issue_count * 5))
        
        # Create metrics
        metrics = CodeMetrics(
            complexity_score=complexity_score,
            maintainability_index=maintainability_index,
            issue_count=issue_count,
            bug_count=bug_count,
            security_count=security_count,
            performance_count=performance_count,
            style_count=style_count,
            lines_of_code=lines_of_code
        )
        
        # Create suggestions from issues
        suggestions = [i.description for i in issues]
        
        # Calculate overall score (1-10 scale, lower with more severe issues)
        issue_weights = {
            IssueSeverity.HIGH: 1.5,
            IssueSeverity.MEDIUM: 0.8,
            IssueSeverity.LOW: 0.3
        }
        
        weighted_issues = sum(issue_weights.get(i.severity, 0) for i in issues)
        base_score = 10
        score_reduction = min(weighted_issues, 9)  # Cap reduction at 9 to ensure score >= 1
        overall_score = base_score - score_reduction
        
        # Create summary
        summary = AnalysisSummary(
            overall_score=max(1, min(10, overall_score)),  # Ensure between 1-10
            quality_level=self._get_quality_level(overall_score),
            summary=f"ESLint found {issue_count} issues in the code.",
            top_issues=[i.title for i in issues[:3]],
            language="javascript/typescript",
            total_issues=issue_count,
            critical_issues=0,  # ESLint doesn't have critical severity
            high_issues=sum(1 for i in issues if i.severity == IssueSeverity.HIGH),
            medium_issues=sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM),
            low_issues=sum(1 for i in issues if i.severity == IssueSeverity.LOW),
            recommendation=self._get_recommendation(overall_score, issue_count)
        )
        
        return {
            "issues": issues,
            "metrics": metrics.model_dump(),
            "summary": summary.model_dump(),
            "suggestions": suggestions
        }
    
    def _get_quality_level(self, score: float) -> str:
        """Convert numerical score to quality level string."""
        if score >= 9:
            return "Excellent"
        elif score >= 7:
            return "Good"
        elif score >= 5:
            return "Average"
        elif score >= 3:
            return "Poor"
        else:
            return "Critical"
    
    def _get_recommendation(self, score: float, issue_count: int) -> str:
        """Generate recommendation based on score and issues."""
        if score >= 9:
            return "Code quality is excellent. Minor improvements possible."
        elif score >= 7:
            return "Good code quality. Address the identified issues for better code."
        elif score >= 5:
            return "Average code quality. Consider addressing the issues."
        elif score >= 3:
            return "Poor code quality. Important issues need to be fixed."
        else:
            return "Critical code quality issues. Immediate attention required."
    
    def _generate_error_result(self, error_message: str) -> Dict[str, Any]:
        """Generate an error result when ESLint analysis fails."""
        return {
            "issues": [CodeIssue(
                id=f"eslint_error_{uuid.uuid4().hex[:8]}",
                type=IssueType.BUG,
                severity=IssueSeverity.LOW,
                title="ESLint Analysis Error",
                description=f"Error during ESLint analysis: {error_message}",
                suggestion="Check that ESLint is properly installed and configured."
            ).model_dump()],
            "metrics": CodeMetrics(
                complexity_score=0,
                maintainability_index=0,
                issue_count=1,
                bug_count=1,
                security_count=0,
                performance_count=0,
                style_count=0,
                lines_of_code=0
            ).model_dump(),
            "summary": AnalysisSummary(
                overall_score=0,
                quality_level="Unknown",
                summary=f"ESLint analysis failed: {error_message}",
                top_issues=["ESLint Analysis Error"],
                language="javascript/typescript",
                total_issues=1,
                critical_issues=0,
                high_issues=0,
                medium_issues=0,
                low_issues=1,
                recommendation="Ensure ESLint is properly installed and the code is valid."
            ).model_dump(),
            "suggestions": ["Check that ESLint is properly installed and configured."]
        }


class PylintAnalyzer(BaseAnalyzer):
    """Analyzer for Python code using Pylint."""
    
    def __init__(self):
        super().__init__()
        self.tool_id = "pylint"
    
    async def analyze(self, code: str, config: Dict) -> Dict[str, Any]:
        """Analyze Python code using Pylint."""
        try:
            # Write code to temporary file
            file_path = await self._write_temp_file(code, ".py")
            
            try:
                # Execute Pylint on the file
                pylint_result = await self._execute_pylint(file_path, config)
                
                # Convert Pylint results to our format
                return self._convert_results(pylint_result, code)
            finally:
                # Clean up temporary file
                if os.path.exists(file_path):
                    os.unlink(file_path)
        
        except Exception as e:
            logger.error(f"Pylint analysis error: {str(e)}")
            return self._generate_error_result(str(e))
    
    async def _execute_pylint(self, file_path: str, config: Dict) -> Dict:
        """Execute Pylint on the given file and return the results."""
        try:
            # Create a temporary Pylint config file if custom config provided
            rcfile = None
            if config:
                rcfile = await self._create_pylint_config(config)
            
            # Build the Pylint command
            cmd = ["pylint", "--output-format=json", file_path]
            if rcfile:
                cmd.extend(["--rcfile", rcfile])
            
            # Execute Pylint process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Get output with reduced timeout for better performance
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            
            # Clean up config file if created
            if rcfile and os.path.exists(rcfile):
                os.unlink(rcfile)
            
            # Parse the JSON output
            if stdout:
                try:
                    return json.loads(stdout.decode())
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Pylint output: {stdout.decode()}")
            
            # If no valid output, check for errors
            if stderr:
                logger.warning(f"Pylint stderr: {stderr.decode()}")
            
            # Return empty result if no output
            return []
            
        except asyncio.TimeoutError:
            logger.error("Pylint execution timed out")
            raise Exception("Pylint analysis timed out")
        except Exception as e:
            logger.error(f"Error executing Pylint: {str(e)}")
            raise
    
    async def _create_pylint_config(self, config: Dict) -> str:
        """Create a temporary Pylint config file from the provided config."""
        # Convert config dict to Pylint format
        pylint_config = "[MASTER]\n"
        
        # Add disabled checks
        if "disabled" in config:
            pylint_config += f"disable={','.join(config['disabled'])}\n"
        
        # Add enabled checks
        if "enabled" in config:
            pylint_config += f"enable={','.join(config['enabled'])}\n"
        
        # Add other sections as needed
        if "options" in config:
            for section, options in config["options"].items():
                pylint_config += f"\n[{section.upper()}]\n"
                for key, value in options.items():
                    pylint_config += f"{key}={value}\n"
        
        # Write config to temporary file
        fd, config_path = tempfile.mkstemp(suffix=".pylintrc")
        os.close(fd)
        
        async with aiofiles.open(config_path, 'w') as f:
            await f.write(pylint_config)
        
        return config_path
    
    def _convert_results(self, pylint_result: List, code: str) -> Dict[str, Any]:
        """Convert Pylint results to our standardized format."""
        # Count lines of code
        lines_of_code = len([line for line in code.split('\n') if line.strip()])
        
        # Initialize issues list
        issues = []
        
        # Smart Pylint severity mapping based on actual impact
        def get_pylint_severity(message_id, pylint_type):
            # CRITICAL: Code that breaks functionality
            critical_messages = ['undefined-variable', 'used-before-assignment', 'no-member', 
                               'not-callable', 'invalid-name']
            
            # HIGH: Logic errors and serious issues
            high_messages = ['unused-variable', 'redefined-builtin', 'dangerous-default-value',
                           'unreachable', 'pointless-except', 'broad-except']
            
            # MEDIUM: Important maintainability issues
            medium_messages = ['too-many-arguments', 'too-many-locals', 'too-many-branches',
                             'cyclomatic-complexity', 'duplicate-code']
            
            # LOW: Style and conventions (most Pylint messages)
            low_messages = ['missing-docstring', 'line-too-long', 'trailing-whitespace',
                          'bad-indentation', 'wrong-import-order', 'invalid-name']
            
            if message_id in critical_messages:
                return IssueSeverity.CRITICAL
            elif message_id in high_messages:
                return IssueSeverity.HIGH
            elif message_id in medium_messages:
                return IssueSeverity.MEDIUM  
            elif message_id in low_messages:
                return IssueSeverity.LOW
            else:
                # Default mapping for unknown messages - more conservative
                severity_map = {
                    "error": IssueSeverity.MEDIUM,      # Was HIGH, now MEDIUM
                    "warning": IssueSeverity.LOW,       # Was MEDIUM, now LOW  
                    "convention": IssueSeverity.LOW,
                    "refactor": IssueSeverity.LOW,
                    "info": IssueSeverity.LOW
                }
                return severity_map.get(pylint_type, IssueSeverity.LOW)
        
        # Map Pylint message types to our issue types
        type_map = {
            "error": IssueType.BUG,
            "warning": IssueType.MAINTAINABILITY,
            "convention": IssueType.STYLE,
            "refactor": IssueType.MAINTAINABILITY,
            "info": IssueType.MAINTAINABILITY
        }
        
        # Process each Pylint message
        for message in pylint_result:
            msg_type = message.get("type", "warning")
            
            # Create the issue with proper severity classification
            issue = CodeIssue(
                id=f"pylint_{uuid.uuid4().hex[:8]}",
                type=type_map.get(msg_type, IssueType.MAINTAINABILITY),
                severity=get_pylint_severity(message.get('symbol', ''), msg_type),
                title=f"Pylint: {message.get('symbol', 'issue')}",
                description=message.get("message", "Unknown Pylint issue"),
                line_number=message.get("line"),
                column_number=message.get("column"),
                suggestion=f"Fix according to Pylint rule: {message.get('symbol', 'unknown')}"
            )
            
            issues.append(issue.model_dump())
        
        # Count issues by type (issues are now dictionaries)
        bug_count = sum(1 for i in issues if i.get("type") == IssueType.BUG.value)
        security_count = sum(1 for i in issues if i.get("type") == IssueType.SECURITY.value)
        performance_count = sum(1 for i in issues if i.get("type") == IssueType.PERFORMANCE.value)
        style_count = sum(1 for i in issues if i.get("type") == IssueType.STYLE.value)
        
        # Calculate metrics
        issue_count = len(issues)
        
        # Extract Pylint score if available (0-10 scale)
        pylint_score = None
        for message in pylint_result:
            if message.get("type") == "info" and "Your code has been rated at" in message.get("message", ""):
                score_text = message.get("message", "")
                try:
                    score_match = re.search(r"rated at (\d+\.\d+)/10", score_text)
                    if score_match:
                        pylint_score = float(score_match.group(1))
                except (ValueError, IndexError):
                    pass
        
        # Use Pylint score if available, otherwise calculate based on issues
        if pylint_score is not None:
            complexity_score = pylint_score
            maintainability_index = pylint_score * 10  # Scale to 0-100
        else:
            # More issues = higher complexity score (1-10 scale)
            complexity_factor = min(issue_count / 5, 1.0)  # Cap at 1.0
            complexity_score = 5 + (complexity_factor * 5)  # Scale to 5-10
            
            # Maintainability decreases with more issues
            maintainability_index = max(0, 100 - (issue_count * 5))
        
        # Create metrics
        metrics = CodeMetrics(
            complexity_score=complexity_score,
            maintainability_index=maintainability_index,
            issue_count=issue_count,
            bug_count=bug_count,
            security_count=security_count,
            performance_count=performance_count,
            style_count=style_count,
            lines_of_code=lines_of_code
        )
        
        # Create suggestions from issues
        suggestions = [i.description for i in issues]
        
        # Calculate overall score (1-10 scale)
        overall_score = pylint_score if pylint_score is not None else max(1, 10 - (issue_count / 2))
        
        # Create summary
        summary = AnalysisSummary(
            overall_score=max(1, min(10, overall_score)),  # Ensure between 1-10
            quality_level=self._get_quality_level(overall_score),
            summary=f"Pylint found {issue_count} issues in the code.",
            top_issues=[i.title for i in issues[:3]],
            language="python",
            total_issues=issue_count,
            critical_issues=0,  # Pylint doesn't have critical severity
            high_issues=sum(1 for i in issues if i.severity == IssueSeverity.HIGH),
            medium_issues=sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM),
            low_issues=sum(1 for i in issues if i.severity == IssueSeverity.LOW),
            recommendation=self._get_recommendation(overall_score, issue_count)
        )
        
        return {
            "issues": issues,
            "metrics": metrics.model_dump(),
            "summary": summary.model_dump(),
            "suggestions": suggestions
        }
    
    def _get_quality_level(self, score: float) -> str:
        """Convert numerical score to quality level string."""
        if score >= 9:
            return "Excellent"
        elif score >= 7:
            return "Good"
        elif score >= 5:
            return "Average"
        elif score >= 3:
            return "Poor"
        else:
            return "Critical"
    
    def _get_recommendation(self, score: float, issue_count: int) -> str:
        """Generate recommendation based on score and issues."""
        if score >= 9:
            return "Code quality is excellent. Minor improvements possible."
        elif score >= 7:
            return "Good code quality. Address the identified issues for better code."
        elif score >= 5:
            return "Average code quality. Consider addressing the issues."
        elif score >= 3:
            return "Poor code quality. Important issues need to be fixed."
        else:
            return "Critical code quality issues. Immediate attention required."
    
    def _generate_error_result(self, error_message: str) -> Dict[str, Any]:
        """Generate an error result when Pylint analysis fails."""
        return {
            "issues": [CodeIssue(
                id=f"pylint_error_{uuid.uuid4().hex[:8]}",
                type=IssueType.BUG,
                severity=IssueSeverity.LOW,
                title="Pylint Analysis Error",
                description=f"Error during Pylint analysis: {error_message}",
                suggestion="Check that Pylint is properly installed and configured."
            ).model_dump()],
            "metrics": CodeMetrics(
                complexity_score=0,
                maintainability_index=0,
                issue_count=1,
                bug_count=1,
                security_count=0,
                performance_count=0,
                style_count=0,
                lines_of_code=0
            ).model_dump(),
            "summary": AnalysisSummary(
                overall_score=0,
                quality_level="Unknown",
                summary=f"Pylint analysis failed: {error_message}",
                top_issues=["Pylint Analysis Error"],
                language="python",
                total_issues=1,
                critical_issues=0,
                high_issues=0,
                medium_issues=0,
                low_issues=1,
                recommendation="Ensure Pylint is properly installed and the code is valid."
            ).model_dump(),
            "suggestions": ["Check that Pylint is properly installed and configured."]
        }


class BanditAnalyzer(BaseAnalyzer):
    """Analyzer for Python security issues using Bandit."""
    
    def __init__(self):
        super().__init__()
        self.tool_id = "bandit"
    
    async def analyze(self, code: str, config: Dict) -> Dict[str, Any]:
        """Analyze Python code for security issues using Bandit."""
        try:
            # Write code to temporary file
            file_path = await self._write_temp_file(code, ".py")
            
            try:
                # Execute Bandit on the file
                bandit_result = await self._execute_bandit(file_path, config)
                
                # Convert Bandit results to our format
                return self._convert_results(bandit_result, code)
            finally:
                # Clean up temporary file
                if os.path.exists(file_path):
                    os.unlink(file_path)
        
        except Exception as e:
            logger.error(f"Bandit analysis error: {str(e)}")
            return self._generate_error_result(str(e))
    
    async def _execute_bandit(self, file_path: str, config: Dict) -> Dict:
        """Execute Bandit on the given file and return the results."""
        try:
            # Build the Bandit command
            cmd = ["bandit", "-f", "json", file_path]
            
            # Add config options if provided
            if config.get("severity"):
                cmd.extend(["-l", config["severity"]])
            if config.get("confidence"):
                cmd.extend(["-c", config["confidence"]])
            if config.get("tests"):
                cmd.extend(["-t", ",".join(config["tests"])])
            if config.get("skips"):
                cmd.extend(["-s", ",".join(config["skips"])])
            
            # Execute Bandit process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Get output with reduced timeout for better performance
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            
            # Parse the JSON output
            if stdout:
                try:
                    return json.loads(stdout.decode())
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Bandit output: {stdout.decode()}")
            
            # If no valid output, check for errors
            if stderr:
                logger.warning(f"Bandit stderr: {stderr.decode()}")
            
            # Return empty result if no output
            return {"results": []}
            
        except asyncio.TimeoutError:
            logger.error("Bandit execution timed out")
            raise Exception("Bandit analysis timed out")
        except Exception as e:
            logger.error(f"Error executing Bandit: {str(e)}")
            raise
    
    def _convert_results(self, bandit_result: Dict, code: str) -> Dict[str, Any]:
        """Convert Bandit results to our standardized format."""
        # Count lines of code
        lines_of_code = len([line for line in code.split('\n') if line.strip()])
        
        # Initialize issues list
        issues = []
        
        # Map Bandit severities to our severities
        severity_map = {
            "HIGH": IssueSeverity.HIGH,
            "MEDIUM": IssueSeverity.MEDIUM,
            "LOW": IssueSeverity.LOW
        }
        
        # Process each Bandit result
        for result in bandit_result.get("results", []):
            # Determine severity based on Bandit's severity and confidence
            bandit_severity = result.get("issue_severity", "LOW").upper()
            bandit_confidence = result.get("issue_confidence", "LOW").upper()
            
            # Adjust severity based on confidence
            if bandit_severity == "HIGH" and bandit_confidence == "HIGH":
                severity = IssueSeverity.CRITICAL
            else:
                severity = severity_map.get(bandit_severity, IssueSeverity.MEDIUM)
            
            # Create the issue
            issue = CodeIssue(
                id=f"bandit_{uuid.uuid4().hex[:8]}",
                type=IssueType.SECURITY,  # Bandit is focused on security
                severity=severity,
                title=f"Security: {result.get('test_id', 'issue')}",
                description=result.get("issue_text", "Unknown security issue"),
                line_number=result.get("line_number"),
                code_snippet=result.get("code"),
                suggestion="Fix this security vulnerability."
            )
            
            issues.append(issue.model_dump())
        
        # Calculate metrics
        issue_count = len(issues)
        security_count = issue_count  # All Bandit issues are security issues
        
        # Create metrics
        metrics = CodeMetrics(
            complexity_score=5,  # Neutral score for security-only analysis
            maintainability_index=50,  # Neutral index for security-only analysis
            issue_count=issue_count,
            bug_count=0,
            security_count=security_count,
            performance_count=0,
            style_count=0,
            lines_of_code=lines_of_code
        )
        
        # Create suggestions from issues
        suggestions = [i.description for i in issues]
        
        # Calculate overall score (1-10 scale, security issues have higher impact)
        issue_weights = {
            IssueSeverity.CRITICAL: 3.0,
            IssueSeverity.HIGH: 2.0,
            IssueSeverity.MEDIUM: 1.0,
            IssueSeverity.LOW: 0.5
        }
        
        weighted_issues = sum(issue_weights.get(i.severity, 0) for i in issues)
        base_score = 10
        score_reduction = min(weighted_issues, 9)  # Cap reduction at 9 to ensure score >= 1
        overall_score = base_score - score_reduction
        
        # Create summary
        summary = AnalysisSummary(
            overall_score=max(1, min(10, overall_score)),  # Ensure between 1-10
            quality_level=self._get_quality_level(overall_score),
            summary=f"Bandit found {issue_count} security issues in the code.",
            top_issues=[i.title for i in issues[:3]],
            language="python",
            total_issues=issue_count,
            critical_issues=sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL),
            high_issues=sum(1 for i in issues if i.severity == IssueSeverity.HIGH),
            medium_issues=sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM),
            low_issues=sum(1 for i in issues if i.severity == IssueSeverity.LOW),
            recommendation=self._get_recommendation(overall_score, issue_count)
        )
        
        return {
            "issues": issues,
            "metrics": metrics.model_dump(),
            "summary": summary.model_dump(),
            "suggestions": suggestions
        }
    
    def _get_quality_level(self, score: float) -> str:
        """Convert numerical score to quality level string."""
        if score >= 9:
            return "Excellent"
        elif score >= 7:
            return "Good"
        elif score >= 5:
            return "Average"
        elif score >= 3:
            return "Poor"
        else:
            return "Critical"
    
    def _get_recommendation(self, score: float, issue_count: int) -> str:
        """Generate recommendation based on score and issues."""
        if issue_count == 0:
            return "No security issues detected. Continue following secure coding practices."
        elif score >= 8:
            return "Minor security concerns. Review and address the identified issues."
        elif score >= 6:
            return "Several security issues found. Address these vulnerabilities before deployment."
        elif score >= 4:
            return "Significant security vulnerabilities detected. Immediate attention required."
        else:
            return "Critical security issues found. Fix these vulnerabilities immediately."
    
    def _generate_error_result(self, error_message: str) -> Dict[str, Any]:
        """Generate an error result when Bandit analysis fails."""
        return {
            "issues": [CodeIssue(
                id=f"bandit_error_{uuid.uuid4().hex[:8]}",
                type=IssueType.SECURITY,
                severity=IssueSeverity.LOW,
                title="Bandit Analysis Error",
                description=f"Error during Bandit security analysis: {error_message}",
                suggestion="Check that Bandit is properly installed and configured."
            ).model_dump()],
            "metrics": CodeMetrics(
                complexity_score=0,
                maintainability_index=0,
                issue_count=1,
                bug_count=0,
                security_count=1,
                performance_count=0,
                style_count=0,
                lines_of_code=0
            ).model_dump(),
            "summary": AnalysisSummary(
                overall_score=0,
                quality_level="Unknown",
                summary=f"Bandit security analysis failed: {error_message}",
                top_issues=["Bandit Analysis Error"],
                language="python",
                total_issues=1,
                critical_issues=0,
                high_issues=0,
                medium_issues=0,
                low_issues=1,
                recommendation="Ensure Bandit is properly installed and the code is valid."
            ).model_dump(),
            "suggestions": ["Check that Bandit is properly installed and configured."]
        }


# Singleton instance
static_analyzer = StaticAnalysisOrchestrator()

async def analyze_code_task(code: str, language: str, tools: list, config: dict):
    """Background task function for Celery worker"""
    try:
        orchestrator = StaticAnalysisOrchestrator()
        result = await orchestrator.analyze_code(code, language, config, tools)
        return {"status": "completed", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}
