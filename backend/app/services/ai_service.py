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
MODEL_PATH = "./models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf"
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
                return self._generate_fallback_response("Model could not be loaded")
        
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
            return self._parse_ai_response(generated_text, language, analysis_type)
            
        except Exception as e:
            logger.error(f"Error during code analysis: {str(e)}")
            return self._generate_fallback_response(f"Analysis failed: {str(e)}")
    
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
            "Provide: \n"
            "- Bugs found (if any)\n"
            "- Security issues (if any)\n"
            "- Performance improvements\n"
            "- Code quality suggestions\n"
            "- Overall score (1-10)\n"
            "Format as JSON with these keys: bugs, security, performance, quality, score, summary."
        )
        
        # Format for DeepSeek Coder
        full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n"
        return full_prompt
    
    def _parse_ai_response(self, 
                          response_text: str, 
                          language: SupportedLanguage,
                          analysis_type: AnalysisType) -> Dict[str, Any]:
        """Parse the AI model's response into a structured format."""
        try:
            # Try to extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start >= 0 and json_end >= 0:
                json_str = response_text[json_start:json_end+1]
                analysis_data = json.loads(json_str)
            else:
                # If no JSON found, try to parse the text response
                analysis_data = self._extract_structured_data(response_text)
            
            # Convert to expected format
            return self._convert_to_analyzer_format(analysis_data, language)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Response text: {response_text}")
            return self._extract_structured_data(response_text)
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return self._generate_fallback_response("Failed to parse AI response")
    
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
                                   language: SupportedLanguage) -> Dict[str, Any]:
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
        
        # Process bugs
        for i, bug in enumerate(bugs):
            if isinstance(bug, str):
                issues.append(CodeIssue(
                    id=f"bug_{uuid.uuid4().hex[:8]}",
                    type=IssueType.BUG,
                    severity=IssueSeverity.MEDIUM,  # Default severity
                    title=f"Bug #{i+1}",
                    description=bug,
                    suggestion="Fix this bug to prevent unexpected behavior."
                ))
        
        # Process security issues
        for i, issue in enumerate(security_issues):
            if isinstance(issue, str):
                issues.append(CodeIssue(
                    id=f"security_{uuid.uuid4().hex[:8]}",
                    type=IssueType.SECURITY,
                    severity=IssueSeverity.HIGH,  # Security issues are high severity by default
                    title=f"Security Issue #{i+1}",
                    description=issue,
                    suggestion="Address this security vulnerability."
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
        metrics = CodeMetrics(
            complexity_score=min(10, max(1, score)),  # Ensure between 1-10
            maintainability_index=min(100, max(0, score * 10)),  # Scale to 0-100
            issue_count=len(issues),
            bug_count=len([i for i in issues if i.type == IssueType.BUG]),
            security_count=len([i for i in issues if i.type == IssueType.SECURITY]),
            performance_count=len([i for i in issues if i.type == IssueType.PERFORMANCE]),
            style_count=len([i for i in issues if i.type == IssueType.STYLE])
        )
        
        # Create summary
        summary = AnalysisSummary(
            overall_score=score,
            quality_level=self._get_quality_level(score),
            summary=summary_text,
            top_issues=[i.title for i in issues[:3]],
            language=language.value
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
    
    def _generate_fallback_response(self, error_message: str) -> Dict[str, Any]:
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
            style_count=0
        )
        
        summary = AnalysisSummary(
            overall_score=5,  # Neutral score
            quality_level="Unknown",
            summary=f"Analysis limited: {error_message}",
            top_issues=["AI Analysis Limited"],
            language="unknown"
        )
        
        return {
            "issues": [fallback_issue],
            "metrics": metrics,
            "summary": summary,
            "suggestions": ["Try again with a smaller code sample or wait for system improvements."]
        }


# Singleton instance
ai_analyzer = AICodeAnalyzer()