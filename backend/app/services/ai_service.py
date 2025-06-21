from typing import Dict, Any, Optional, List
import os
import json
from pathlib import Path
import logging
from llama_cpp import Llama

from app.models.requests import SupportedLanguage, AnalysisType, CodeAnalysisRequest
from app.models.responses import IssueSeverity, IssueType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configuration
def get_model_path():
    """Get the absolute path to the model file"""
    current_dir = Path(__file__).parent
    backend_dir = current_dir.parent.parent
    model_path = backend_dir / "models" / "deepseek-coder-1.3b-instruct.Q4_K_M.gguf"
    logger.info(f"Resolved model path: {model_path}")
    return str(model_path)

MODEL_PATH = get_model_path()
CONTEXT_SIZE = 4096
MAX_TOKENS = 512
TEMPERATURE = 0.1
CPU_THREADS = 4


class AICodeAnalyzer:
    """Service for analyzing code using the DeepSeek Coder model."""
    
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.load_model()
    
    def load_model(self) -> None:
        """Load the DeepSeek Coder model."""
        try:
            model_path = Path(MODEL_PATH).resolve()
            if not model_path.exists():
                logger.error(f"Model file not found at {model_path}")
                return
            
            logger.info(f"Loading DeepSeek Coder model from {model_path}")
            self.model = Llama(
                model_path=str(model_path),
                n_ctx=CONTEXT_SIZE,
                n_threads=CPU_THREADS,
                verbose=False
            )
            self.model_loaded = True
            logger.info("DeepSeek Coder model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load DeepSeek Coder model: {str(e)}")
            self.model_loaded = False
    
    async def analyze_code(self, request: CodeAnalysisRequest) -> Dict[str, Any]:
        """
        Analyze code using the DeepSeek Coder model.
        
        Args:
            request: CodeAnalysisRequest object containing all analysis parameters
            
        Returns:
            Dict containing analysis results in the expected format
        """
        if not self.model_loaded or self.model is None:
            logger.warning("Model not loaded, attempting to reload")
            self.load_model()
            if not self.model_loaded:
                return self._generate_fallback_response("Model could not be loaded", request.code)
        
        try:
            logger.info(f"🤖 Starting AI analysis for {request.language} code, analysis type: {request.analysis_type}")
            
            # Extract parameters from request
            code = request.code
            language = request.language
            analysis_type = request.analysis_type
            
            # Prepare the prompt for the model
            prompt = self._create_analysis_prompt(code, language.value, analysis_type.value)
            
            # Generate response from the model
            response = self.model.create_completion(
                prompt=prompt,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                stop=["</s>", "<|im_end|>"],
                echo=False
            )
            
            # Extract and parse the generated text
            generated_text = response["choices"][0]["text"]
            logger.info(f"Generated response length: {len(generated_text)}")
            
            # Parse the JSON response
            analysis_result = self._parse_ai_response(generated_text, language, analysis_type, code)
            
            logger.info(f"✅ AI analysis completed successfully")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Error during code analysis: {str(e)}")
            return self._generate_fallback_response(f"Analysis failed: {str(e)}", request.code)
    
    # Legacy method for backward compatibility (if needed)
    def analyze_code_legacy(self, 
                           code: str, 
                           language: SupportedLanguage, 
                           analysis_type: AnalysisType = AnalysisType.FULL) -> Dict[str, Any]:
        """Legacy method for backward compatibility."""
        from app.models.requests import CodeAnalysisRequest
        
        # Create a request object
        request = CodeAnalysisRequest(
            code=code,
            language=language,
            analysis_type=analysis_type,
            include_suggestions=True,
            include_explanations=True,
            severity_threshold="low"
        )
        
        # Call the main async method (note: this is not truly async in legacy mode)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.analyze_code(request))
        except RuntimeError:
            # If no event loop is running, create a new one
            return asyncio.run(self.analyze_code(request))
    
    def _create_analysis_prompt(self, code: str, language: str, analysis_type: str) -> str:
        """Create a prompt for the DeepSeek Coder model."""
        system_prompt = (
            "You are an expert security-focused code reviewer. You MUST identify security vulnerabilities. "
            "Provide detailed feedback in a structured JSON format."
        )
        
        # Adjust the prompt based on analysis type
        focus_instruction = ""
        if analysis_type != "full":
            focus_map = {
                "bugs_only": "Focus only on bugs and logical errors.",
                "security_only": "Focus only on security vulnerabilities.",
                "performance_only": "Focus only on performance improvements.",
                "style_only": "Focus only on code style and best practices."
            }
            focus_instruction = focus_map.get(analysis_type, "")
        
        user_prompt = (
            f"CRITICAL SECURITY REVIEW of this {language} code:\n```\n{code}\n```\n\n"
            f"{focus_instruction}\n"
            "CHECK FOR THESE CRITICAL SECURITY ISSUES:\n"
            "- SQL Injection (string concatenation in queries like 'SELECT * FROM table WHERE id = \"' + user_input + '\"')\n"
            "- XSS vulnerabilities (innerHTML with user input)\n"
            "- Command injection (os.system with user input)\n"
            "- Path traversal (file operations with user input)\n"
            "- Hardcoded secrets/passwords\n"
            "- Weak authentication\n"
            "- Division by zero errors\n"
            "- Buffer overflows\n"
            "- Logic errors\n\n"
            "SCORING RULES:\n"
            "- SQL injection = Score 1-2 (CRITICAL)\n"
            "- XSS vulnerabilities = Score 1-3 (CRITICAL)\n"
            "- Command injection = Score 1-2 (CRITICAL)\n"
            "- Division by zero = Score 1-3 (CRITICAL)\n"
            "- Good security practices = Score 8-10\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "bugs": ["specific bugs found"],\n'
            '  "security": ["specific security vulnerabilities"],\n'
            '  "performance": ["performance issues"],\n'
            '  "quality": ["code quality issues"],\n'
            '  "score": 1,\n'
            '  "summary": "detailed security analysis"\n'
            "}\n\n"
            "If you find SQL injection, XSS, or command injection, score MUST be 1-2."
        )
        
        # Format for DeepSeek Coder
        full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n"
        return full_prompt
    
    def _parse_ai_response(self, response_text: str, language: SupportedLanguage, analysis_type: AnalysisType, code: str = "") -> Dict[str, Any]:
        """Parse the AI model's response into a structured format."""
        try:
            logger.info(f"Raw AI response: {response_text[:200]}...")
            cleaned_text = response_text.strip()
            
            # Try to extract JSON from the response
            json_start = cleaned_text.find('{')
            json_end = cleaned_text.rfind('}')

            if json_start >= 0 and json_end >= 0:
                json_str = cleaned_text[json_start:json_end+1]
                logger.info(f"Extracted JSON: {json_str[:200]}...")

                try:
                    # Try parsing the JSON directly
                    analysis_data = json.loads(json_str)
                    logger.info(f"Successfully parsed JSON: {analysis_data}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Direct JSON parse failed: {e}")
                    # Try cleaning up the JSON
                    try:
                        # Remove any trailing text after the JSON
                        lines = json_str.split('\n')
                        cleaned_lines = []
                        brace_count = 0
                        
                        for line in lines:
                            cleaned_lines.append(line)
                            brace_count += line.count('{') - line.count('}')
                            if brace_count == 0 and '}' in line:
                                break
                        
                        clean_json = '\n'.join(cleaned_lines)
                        analysis_data = json.loads(clean_json)
                        logger.info(f"Parsed cleaned JSON: {analysis_data}")
                    except json.JSONDecodeError:
                        logger.error("Failed to parse cleaned JSON, using fallback")
                        analysis_data = self._create_smart_fallback(code, cleaned_text)
            else:
                logger.warning("No JSON brackets found, using smart fallback")
                analysis_data = self._create_smart_fallback(code, cleaned_text)

            # Validate and fix the data
            analysis_data = self._validate_analysis_data(analysis_data)
            
            # Convert to expected format
            return self._convert_to_analyzer_format(analysis_data, language, code)

        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            analysis_data = self._create_smart_fallback(code, response_text)
            return self._convert_to_analyzer_format(analysis_data, language, code)
    
    def _create_smart_fallback(self, code: str, ai_text: str) -> Dict[str, Any]:
        """Create intelligent fallback analysis based on code patterns."""
        code_lower = code.lower()
        ai_text_lower = ai_text.lower()
        
        bugs = []
        security = []
        performance = []
        quality = []
        score = 7  # Default good score
        summary = "Code analysis completed."
        
        # CRITICAL SECURITY CHECKS
        if "select * from" in code_lower and ("+ " in code or "' + " in code):
            security.append("CRITICAL: SQL Injection vulnerability - user input concatenated directly into SQL query")
            score = 1
            summary = "Critical SQL injection vulnerability detected"
        elif ".innerhtml" in code_lower and ("message" in code_lower or "input" in code_lower):
            security.append("CRITICAL: XSS vulnerability - user input directly inserted into DOM")
            score = 1
            summary = "Critical XSS vulnerability detected"
        elif "os.system" in code_lower and "+" in code:
            security.append("CRITICAL: Command injection vulnerability")
            score = 1
            summary = "Critical command injection vulnerability detected"
        elif "open(" in code_lower and "+" in code and ("filename" in code_lower or "path" in code_lower):
            security.append("HIGH: Path traversal vulnerability - user input in file path")
            score = 2
            summary = "Path traversal vulnerability detected"
        elif ("password" in code_lower or "api_key" in code_lower) and ("=" in code and '"' in code):
            security.append("HIGH: Hardcoded credentials detected")
            score = 3
            summary = "Hardcoded credentials found in code"
        elif "return x / 0" in code or "/ 0" in code:
            bugs.append("Critical: Division by zero will cause runtime error")
            score = 1
            summary = "Critical bug: Division by zero detected"
        elif "if" in code_lower and "== 0" in code and "error" in code_lower:
            # Good error handling
            score = 9
            summary = "Excellent error handling for edge cases"
        
        # Common code quality checks
        if len(code.strip().split('\n')) < 3:
            quality.append("Function could benefit from documentation")
        
        return {
            "bugs": bugs,
            "security": security, 
            "performance": performance,
            "quality": quality,
            "score": score,
            "summary": summary
        }
    
    def _validate_analysis_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix analysis data structure."""
        # Ensure all required keys exist
        validated = {
            "bugs": data.get("bugs", []),
            "security": data.get("security", []),
            "performance": data.get("performance", []),
            "quality": data.get("quality", []),
            "score": data.get("score", 5),
            "summary": data.get("summary", "Analysis completed.")
        }
        
        # Ensure arrays are actually arrays and not strings
        for key in ["bugs", "security", "performance", "quality"]:
            if isinstance(validated[key], str):
                # If it's a string, convert to array
                if validated[key].strip():
                    validated[key] = [validated[key]]
                else:
                    validated[key] = []
            elif not isinstance(validated[key], list):
                validated[key] = []
        
        # Ensure score is reasonable
        try:
            validated["score"] = max(1, min(10, int(validated["score"])))
        except (ValueError, TypeError):
            validated["score"] = 5
            
        return validated
    
    def _convert_to_analyzer_format(self, 
                                   ai_data: Dict[str, Any], 
                                   language: SupportedLanguage,
                                   code: str = "") -> Dict[str, Any]:
        """Convert AI response to the format expected by the analyzer service."""
        from app.models.responses import CodeIssue, CodeMetrics, AnalysisSummary
        import uuid
        
        logger.info(f"Converting AI data: {ai_data}")
        
        # Extract data from AI response
        bugs = ai_data.get("bugs", [])
        security_issues = ai_data.get("security", [])
        performance_issues = ai_data.get("performance", [])
        quality_issues = ai_data.get("quality", [])
        score = ai_data.get("score", 5)
        summary_text = ai_data.get("summary", "Analysis completed.")
        
        logger.info(f"Processing bugs: {bugs}, security: {security_issues}, performance: {performance_issues}, quality: {quality_issues}")
        
        # Convert to CodeIssue objects
        issues = []
        
        # Process bugs with intelligent severity detection
        for i, bug in enumerate(bugs):
            if isinstance(bug, str) and len(bug.strip()) > 1:  # Avoid single characters
                severity = IssueSeverity.LOW
                bug_lower = bug.lower()
                
                # Critical bugs
                if any(word in bug_lower for word in ['critical', 'division by zero', '/0', 'crash', 'fatal']):
                    severity = IssueSeverity.CRITICAL
                elif any(word in bug_lower for word in ['error', 'exception', 'runtime', 'undefined']):
                    severity = IssueSeverity.HIGH
                elif any(word in bug_lower for word in ['warning', 'potential', 'risk']):
                    severity = IssueSeverity.MEDIUM
                    
                issues.append(CodeIssue(
                    id=f"bug_{uuid.uuid4().hex[:8]}",
                    type=IssueType.BUG,
                    severity=severity,
                    title=f"Critical Division by Zero" if 'division' in bug_lower else f"Bug #{i+1}",
                    description=bug,
                    suggestion="Fix this bug to prevent unexpected behavior.",
                    line_number=None,
                    column_number=None,
                    code_snippet=None,
                    explanation=None,
                    confidence=0.8
                ))

        # Process security issues
        for i, issue in enumerate(security_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                severity = IssueSeverity.HIGH
                if any(word in issue.lower() for word in ['injection', 'xss', 'auth', 'critical']):
                    severity = IssueSeverity.CRITICAL
                    
                issues.append(CodeIssue(
                    id=f"security_{uuid.uuid4().hex[:8]}",
                    type=IssueType.SECURITY,
                    severity=severity,
                    title=f"Security Issue #{i+1}",
                    description=issue,
                    suggestion="Address this security vulnerability immediately.",
                    line_number=None,
                    column_number=None,
                    code_snippet=None,
                    explanation=None,
                    confidence=0.8
                ))
                
        # Process performance issues
        for i, issue in enumerate(performance_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                issues.append(CodeIssue(
                    id=f"perf_{uuid.uuid4().hex[:8]}",
                    type=IssueType.PERFORMANCE,
                    severity=IssueSeverity.LOW,
                    title=f"Performance Improvement #{i+1}",
                    description=issue,
                    suggestion="Consider this optimization for better performance.",
                    line_number=None,
                    column_number=None,
                    code_snippet=None,
                    explanation=None,
                    confidence=0.7
                ))
        
        # Process quality issues
        for i, issue in enumerate(quality_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                issues.append(CodeIssue(
                    id=f"quality_{uuid.uuid4().hex[:8]}",
                    type=IssueType.STYLE,
                    severity=IssueSeverity.LOW,
                    title=f"Code Quality Suggestion #{i+1}",
                    description=issue,
                    suggestion="Improve code quality and maintainability.",
                    line_number=None,
                    column_number=None,
                    code_snippet=None,
                    explanation=None,
                    confidence=0.7
                ))
        
        logger.info(f"Created {len(issues)} total issues")
        
        # Create metrics
        lines_of_code = len([line.strip() for line in code.split('\n') if line.strip() and not line.strip().startswith('#')]) if code else 1
        
        # Use AI score directly but cap it if critical issues exist
        actual_score = max(1, min(10, score))
        critical_count = len([i for i in issues if i.severity == IssueSeverity.CRITICAL])
        if critical_count > 0:
            actual_score = min(actual_score, 3)

        metrics = CodeMetrics(
            lines_of_code=lines_of_code,
            complexity_score=actual_score,
            maintainability_index=max(10, min(100, actual_score * 10)),
            test_coverage=None,
            duplication_percentage=0
        )
        
        # Create summary
        summary = AnalysisSummary(
            total_issues=len(issues),
            critical_issues=len([i for i in issues if i.severity == IssueSeverity.CRITICAL]),
            high_issues=len([i for i in issues if i.severity == IssueSeverity.HIGH]),
            medium_issues=len([i for i in issues if i.severity == IssueSeverity.MEDIUM]),
            low_issues=len([i for i in issues if i.severity == IssueSeverity.LOW]),
            overall_score=actual_score,
            recommendation=self._get_recommendation(actual_score, len(issues), ai_data)
        )
        
        # Generate suggestions
        suggestions = [i.description for i in issues if i.description]
        
        return {
            "issues": issues,
            "metrics": metrics,
            "summary": summary,
            "suggestions": suggestions
        }
    
    def _get_recommendation(self, score: int, issue_count: int, ai_data: Dict[str, Any] = None) -> str:
        """Generate intelligent recommendation."""
        if ai_data and 'summary' in ai_data and ai_data['summary']:
            ai_summary = ai_data['summary']
            
            if score >= 8:
                return f"{ai_summary} Continue following best practices."
            elif score >= 6:
                return f"{ai_summary} Address identified issues for better reliability."
            elif score >= 4:
                return f"{ai_summary} Focus on fixing critical and high-severity issues first."
            else:
                return f"{ai_summary} Significant improvements needed before production use."
        
        # Fallback recommendations
        if issue_count == 0:
            return "Excellent! No issues detected."
        elif issue_count <= 2:
            return "Good code quality with minor improvements needed."
        else:
            return "Multiple issues detected. Address critical issues first."

    def _generate_fallback_response(self, error_message: str, code: str = "") -> Dict[str, Any]:
        """Generate a fallback response when AI analysis fails."""
        from app.models.responses import CodeIssue, CodeMetrics, AnalysisSummary
        import uuid
        
        fallback_issue = CodeIssue(
            id=f"fallback_{uuid.uuid4().hex[:8]}",
            type=IssueType.MAINTAINABILITY,
            severity=IssueSeverity.LOW,
            title="AI Analysis Limited",
            description=f"AI analysis was limited: {error_message}",
            suggestion="Please try again or use manual review.",
            line_number=None,
            column_number=None,
            code_snippet=None,
            explanation=None,
            confidence=0.5
        )
        
        lines_of_code = len([line.strip() for line in code.split('\n') if line.strip()]) if code else 1
        
        metrics = CodeMetrics(
            lines_of_code=lines_of_code,
            complexity_score=5,
            maintainability_index=50,
            test_coverage=None,
            duplication_percentage=0
        )
        
        summary = AnalysisSummary(
            total_issues=1,
            critical_issues=0,
            high_issues=0,
            medium_issues=0,
            low_issues=1,
            overall_score=5,
            recommendation="Please try again for detailed analysis."
        )
        
        return {
            "issues": [fallback_issue],
            "metrics": metrics,
            "summary": summary,
            "suggestions": ["Try again with a smaller code sample."]
        }


# Singleton instance
ai_analyzer = AICodeAnalyzer()