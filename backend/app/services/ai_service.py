from typing import Dict, Any, Optional, List
import os
import json
from pathlib import Path
import logging
from llama_cpp import Llama

from app.models.requests import SupportedLanguage, AnalysisType
from app.models.responses import IssueSeverity, IssueType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configuration
# FIXED: Use absolute path resolution
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
                n_threads=CPU_THREADS
            )
            self.model_loaded = True
            logger.info("DeepSeek Coder model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load DeepSeek Coder model: {str(e)}")
            self.model_loaded = False
    
    def analyze_code(self, 
                     code: str, 
                     language: SupportedLanguage, 
                     analysis_type: AnalysisType = AnalysisType.FULL) -> Dict[str, Any]:
        """Analyze code using the DeepSeek Coder model."""
        if not self.model_loaded or self.model is None:
            logger.warning("Model not loaded, attempting to reload")
            self.load_model()
            if not self.model_loaded:
                return self._generate_fallback_response("Model could not be loaded", code)
        
        try:
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
            return self._parse_ai_response(generated_text, language, analysis_type, code)  # Add code parameter            
        except Exception as e:
            logger.error(f"Error during code analysis: {str(e)}")
            return self._generate_fallback_response(f"Analysis failed: {str(e)}", code)
    
    def _create_analysis_prompt(self, code: str, language: str, analysis_type: str) -> str:
        """Create a prompt for the DeepSeek Coder model."""
        system_prompt = (
            "You are an expert code reviewer. Analyze code for bugs, security issues, and improvements. "
            "Provide detailed feedback in a structured format."
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
            f"Review this {language} code: ```\n{code}\n```\n\n"
            f"{focus_instruction}\n"
            "Analyze and provide:\n"
            "- bugs: List any bugs or logical errors (mark severity as 'critical', 'high', 'medium', or 'low')\n"
            "- security: List security vulnerabilities or risks\n"
            "- performance: List performance improvement suggestions\n"
            "- quality: List code style and maintainability issues\n"
            "- score: Overall code quality score from 1-10\n"
            "- summary: Detailed summary with specific actionable recommendations\n\n"
            "Format as JSON with these exact keys: bugs, security, performance, quality, score, summary.\n"
            "For bugs and security issues, include severity indicators in descriptions."
)
        
        # Format for DeepSeek Coder
        full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n"
        return full_prompt
    
    def _parse_ai_response(self, response_text: str, language: SupportedLanguage, analysis_type: AnalysisType, code: str = "") -> Dict[str, Any]:
        """Parse the AI model's response into a structured format."""
        try:
            # Clean the response text first
            logger.info(f"Raw AI response: {response_text}")
            cleaned_text = response_text.strip()
            
            # Try to extract JSON from the response
            json_start = cleaned_text.find('{')
            json_end = cleaned_text.rfind('}')

            if json_start >= 0 and json_end >= 0:
                json_str = cleaned_text[json_start:json_end+1]
                
                logger.info(f"Extracted JSON: {json_str}")

                # Clean up any extra content after the JSON
                json_lines = json_str.split('\n')
                clean_json = []
                brace_count = 0
                for line in json_lines:
                    clean_json.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0 and '}' in line:
                        break
                
                final_json = '\n'.join(clean_json)
                analysis_data = json.loads(final_json)
                logger.info(f"Parsed AI data: {analysis_data}")

            else:
                # If no JSON found, try to parse the text response
                analysis_data = self._extract_structured_data(cleaned_text)
                logger.info(f"Extracted structured data: {analysis_data}")
            # Convert to expected format
            return self._convert_to_analyzer_format(analysis_data, language, code)  # Use code here

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Response text: {response_text[:500]}...")
            structured_data = self._extract_structured_data(response_text)
            return self._convert_to_analyzer_format(structured_data, language, code)  # Use code here
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return self._generate_fallback_response("Failed to parse AI response", code)  # Use code here
    
    def _extract_structured_data(self, text: str) -> Dict[str, Any]:
        """Extract structured data from text when JSON parsing fails."""
        # Default structure
        result = {
            "bugs": [],
            "security": [],
            "performance": [],
            "quality": [],
            "score": 5,  # Default middle score
            "summary": "Analysis completed with limited structure."
        }
        
        # Try to extract sections
        sections = {
            "bugs": ["bugs", "bug", "errors", "error"],
            "security": ["security", "vulnerabilities", "vulnerability"],
            "performance": ["performance", "optimization", "speed"],
            "quality": ["quality", "style", "best practices", "maintainability"],
            "summary": ["summary", "overview", "conclusion"]
        }
        
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this line starts a new section
            for section, keywords in sections.items():
                if any(line.lower().startswith(keyword) for keyword in keywords):
                    current_section = section
                    break
            
            # Extract score if present
            if "score" in line.lower() and ":/10" in line.replace(" ", ""):
                try:
                    score_text = line.split(":")[-1].strip()
                    score = int(score_text.split("/")[0].strip())
                    result["score"] = min(max(score, 1), 10)  # Ensure between 1-10
                except (ValueError, IndexError):
                    pass
            
            # Add content to current section
            if current_section and current_section in result:
                if isinstance(result[current_section], list):
                    # Skip section headers
                    if not any(keyword in line.lower() for keyword in sections[current_section]):
                        result[current_section].append(line)
                else:
                    # For summary (string field)
                    result[current_section] = line
        
        return result
    
    def _convert_to_analyzer_format(self, 
                                   ai_data: Dict[str, Any], 
                                   language: SupportedLanguage,
                                   code: str = "") -> Dict[str, Any]:
        """Convert AI response to the format expected by the analyzer service."""
        from app.models.responses import CodeIssue, CodeMetrics, AnalysisSummary
        import uuid
        
        # Extract data from AI response
        bugs = ai_data.get("bugs", [])
        security_issues = ai_data.get("security", [])
        performance_issues = ai_data.get("performance", [])
        quality_issues = ai_data.get("quality", [])
        score = ai_data.get("score", 5)
        summary_text = ai_data.get("summary", "Analysis completed.")
        
        # Convert to CodeIssue objects
        issues = []
        
        
        # Process bugs with intelligent severity detection
        for i, bug in enumerate(bugs):
            if isinstance(bug, str):
        # Determine severity based on keywords
                severity = IssueSeverity.MEDIUM  # Default
                bug_lower = bug.lower()
        
                if any(word in bug_lower for word in ['critical', 'crash', 'fatal', 'security', 'vulnerability']):
                    severity = IssueSeverity.CRITICAL
                elif any(word in bug_lower for word in ['error', 'exception', 'fail', 'break']):
                    severity = IssueSeverity.HIGH
                elif any(word in bug_lower for word in ['warning', 'potential', 'risk']):
                    severity = IssueSeverity.MEDIUM
                else:
                    severity = IssueSeverity.LOW
            
                issues.append(CodeIssue(
                    id=f"bug_{uuid.uuid4().hex[:8]}",
                    type=IssueType.BUG,
                    severity=severity,
                    title=f"Bug #{i+1}",
                    description=bug,
                    suggestion="Fix this bug to prevent unexpected behavior."
                ))

# Process security issues (always high/critical severity)
        for i, issue in enumerate(security_issues):
            if isinstance(issue, str):
                severity = IssueSeverity.CRITICAL if any(word in issue.lower() for word in ['injection', 'xss', 'auth']) else IssueSeverity.HIGH
                issues.append(CodeIssue(
                    id=f"security_{uuid.uuid4().hex[:8]}",
                    type=IssueType.SECURITY,
                    severity=severity,
                    title=f"Security Issue #{i+1}",
                    description=issue,
                    suggestion="Address this security vulnerability immediately."
        ))
        # Process performance issues
        for i, issue in enumerate(performance_issues):
            if isinstance(issue, str):
                issues.append(CodeIssue(
                    id=f"perf_{uuid.uuid4().hex[:8]}",
                    type=IssueType.PERFORMANCE,
                    severity=IssueSeverity.LOW,  # Performance issues are low severity by default
                    title=f"Performance Improvement #{i+1}",
                    description=issue,
                    suggestion="Consider this optimization for better performance."
                ))
        
        # Process quality issues
        for i, issue in enumerate(quality_issues):
            if isinstance(issue, str):
                issues.append(CodeIssue(
                    id=f"quality_{uuid.uuid4().hex[:8]}",
                    type=IssueType.STYLE,
                    severity=IssueSeverity.LOW,  # Quality issues are low severity by default
                    title=f"Code Quality Suggestion #{i+1}",
                    description=issue,
                    suggestion="Improve code quality and maintainability."
                ))
        
        # Create metrics based on the score and issues
        # Count lines of code
        lines_of_code = len([line.strip() for line in code.split('\n') if line.strip() and not line.strip().startswith('#')]) if code else 1
        
        metrics = CodeMetrics(
            complexity_score=min(10, max(1, score)),
            maintainability_index=min(100, max(0, score * 10)),
            issue_count=len(issues),
            bug_count=len([i for i in issues if i.type == IssueType.BUG]),
            security_count=len([i for i in issues if i.type == IssueType.SECURITY]),
            performance_count=len([i for i in issues if i.type == IssueType.PERFORMANCE]),
            style_count=len([i for i in issues if i.type == IssueType.STYLE]),
            lines_of_code=lines_of_code
        )
        
        # Create summary
        # Create summary with AI intelligence
        summary = AnalysisSummary(
            overall_score=score,
            quality_level=self._get_quality_level(score),
            summary=summary_text,
            top_issues=[i.title for i in issues[:3]],
            language=language.value,
            total_issues=len(issues),
            critical_issues=len([i for i in issues if i.severity == IssueSeverity.CRITICAL]),
            high_issues=len([i for i in issues if i.severity == IssueSeverity.HIGH]),
            medium_issues=len([i for i in issues if i.severity == IssueSeverity.MEDIUM]),
            low_issues=len([i for i in issues if i.severity == IssueSeverity.LOW]),
            recommendation=self._get_recommendation(score, len(issues), ai_data)  # Pass AI data here
)
          
        
        # Generate suggestions based on issues
        suggestions = [i.description for i in issues]
        
        return {
            "issues": issues,
            "metrics": metrics,
            "summary": summary,
            "suggestions": suggestions
        }
    
    def _get_quality_level(self, score: int) -> str:
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
            
    def _get_recommendation(self, score: int, issue_count: int, ai_data: Dict[str, Any] = None) -> str:
        """Generate intelligent recommendation using AI analysis."""
        
        # Use AI summary if available
        if ai_data and 'summary' in ai_data and ai_data['summary']:
            ai_summary = ai_data['summary']
            
            # Enhance the AI summary with actionable advice
            if score >= 8:
                return f"{ai_summary} Continue following best practices and consider code reviews for quality assurance."
            elif score >= 6:
                return f"{ai_summary} Focus on addressing the identified issues to improve code reliability and maintainability."
            elif score >= 4:
                return f"{ai_summary} Prioritize fixing critical and high-severity issues before proceeding with new features."
            else:
                return f"{ai_summary} Consider significant refactoring and implementing comprehensive testing before production use."
        
        # Fallback to intelligent generic recommendations
        if issue_count == 0:
            return "Excellent! No major issues detected. Consider adding comprehensive tests and documentation."
        elif issue_count <= 2:
            return "Good code quality. Address the minor issues identified for optimal performance."
        elif issue_count <= 5:
            return "Moderate issues detected. Focus on fixing bugs and security vulnerabilities first."
        else:
            return "Multiple issues require attention. Prioritize critical and high-severity problems immediately."

    def _generate_fallback_response(self, error_message: str, code: str = "") -> Dict[str, Any]:
        """Generate a fallback response when AI analysis fails."""
        from app.models.responses import CodeIssue, CodeMetrics, AnalysisSummary
        import uuid
        
        fallback_issue = CodeIssue(
            id=f"fallback_{uuid.uuid4().hex[:8]}",
            type=IssueType.MAINTAINABILITY,
            severity=IssueSeverity.LOW,
            title="AI Analysis Limited",
            description=f"The AI code analysis was limited: {error_message}",
            suggestion="Please try again or use manual code review."
        )
        
        metrics = CodeMetrics(
            complexity_score=5,  # Neutral score
            maintainability_index=50,  # Neutral index
            issue_count=1,
            bug_count=0,
            security_count=0,
            performance_count=0,
            style_count=0,
            lines_of_code=1  # Default value
        )
        
        summary = AnalysisSummary(
            overall_score=5,
            quality_level="Unknown",
            summary=f"Analysis limited: {error_message}",
            top_issues=["AI Analysis Limited"],
            language="unknown",
            total_issues=1,
            critical_issues=0,
            high_issues=0,
            medium_issues=0,
            low_issues=1,
            recommendation="Please try again for detailed analysis"
        )
        
        return {
            "issues": [fallback_issue],
            "metrics": metrics,
            "summary": summary,
            "suggestions": ["Try again with a smaller code sample or wait for system improvements."]
        }


# Singleton instance
ai_analyzer = AICodeAnalyzer()