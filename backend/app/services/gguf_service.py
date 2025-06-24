# backend/app/services/gguf_service.py
"""
GGUF Model Service for DeepSeek Coder using llama-cpp-python
Optimized for your existing 1.3B quantized model
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from llama_cpp import Llama
import json

logger = logging.getLogger(__name__)

class GGUFCodeAnalyzer:
    """GGUF-based code analyzer using your existing model"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        logger.info(f"Initializing GGUF service with model: {model_path}")
    
    async def initialize(self):
        """Initialize the GGUF model"""
        start_time = time.time()
        
        try:
            logger.info(f"Loading GGUF model from {self.model_path}")
            
            # Load GGUF model with optimized settings for deployment
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=4096,           # Context window
                n_batch=256,          # Batch size
                n_threads=4,          # CPU threads (adjust based on Oracle Cloud)
                verbose=False,        # Reduce logs
                use_mlock=True,       # Keep model in memory
                n_gpu_layers=0        # CPU only (no GPU on Oracle Cloud free)
            )
            
            load_time = time.time() - start_time
            logger.info(f"GGUF model loaded successfully in {load_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Failed to load GGUF model: {e}")
            raise
    
    async def analyze_code(self, code: str, language: str, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """Analyze code using GGUF model"""
        if not self.model:
            raise RuntimeError("GGUF model not initialized")
        
        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(code, language, analysis_type)
            
            # Generate response with GGUF model
            response = self.model(
                prompt,
                max_tokens=1500,      # Reasonable limit for analysis
                temperature=0.1,      # Low temperature for consistent analysis
                top_p=0.9,
                repeat_penalty=1.1,
                stop=["</analysis>", "\n\nUser:", "\n\nHuman:"]
            )
            
            # Extract the generated text
            generated_text = response['choices'][0]['text']
            
            # Parse the response into structured format
            analysis_result = self._parse_gguf_response(generated_text, code, language)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"GGUF analysis failed: {e}")
            return self._create_fallback_analysis(code, language)
    
    def _build_analysis_prompt(self, code: str, language: str, analysis_type: str) -> str:
        """Build analysis prompt optimized for DeepSeek Coder"""
        
        prompt = f"""<|im_start|>system
You are an expert code reviewer specializing in {language}. Analyze the provided code for bugs, security issues, performance problems, and style violations.

Provide your analysis in this JSON format:
{{
    "summary": {{
        "overall_score": <0-100>,
        "total_issues": <number>,
        "critical_issues": <number>,
        "security_score": <0-100>
    }},
    "issues": [
        {{
            "id": "issue_1",
            "type": "bug|security|performance|style",
            "severity": "critical|high|medium|low",
            "line_number": <number_or_null>,
            "description": "Clear description",
            "suggestion": "Fix recommendation"
        }}
    ]
}}
<|im_end|>
<|im_start|>user
Analyze this {language} code:

```{language}
{code}
```

Focus on: {"critical and high-severity issues only" if analysis_type == "quick" else "comprehensive analysis including all severity levels"}
<|im_end|>
<|im_start|>assistant
I'll analyze this {language} code for issues:

"""
        return prompt
    
    def _parse_gguf_response(self, response: str, code: str, language: str) -> Dict[str, Any]:
        """Parse GGUF model response into structured format"""
        try:
            # Try to extract JSON from response
            import re
            
            # Look for JSON block
            json_match = re.search(r'\{.*?\}', response, re.DOTALL)
            if json_match:
                analysis_data = json.loads(json_match.group())
                
                # Validate and enhance
                return self._validate_analysis(analysis_data, code, language)
            else:
                # Create structured response from text
                return self._text_to_structured_analysis(response, code, language)
                
        except Exception as e:
            logger.warning(f"Failed to parse GGUF response: {e}")
            return self._text_to_structured_analysis(response, code, language)
    
    def _validate_analysis(self, analysis: Dict[str, Any], code: str, language: str) -> Dict[str, Any]:
        """Validate and enhance analysis data"""
        # Ensure required fields
        if 'summary' not in analysis:
            analysis['summary'] = {
                "overall_score": 75,
                "total_issues": len(analysis.get('issues', [])),
                "critical_issues": 0,
                "security_score": 80
            }
        
        # Add metadata
        analysis['metadata'] = {
            "analysis_id": f"gguf_{int(time.time())}",
            "language": language,
            "code_lines": len(code.split('\n')),
            "analysis_timestamp": time.time(),
            "model": "deepseek-coder-1.3b-gguf",
            "analysis_type": "gguf_optimized"
        }
        
        return analysis
    
    def _text_to_structured_analysis(self, response: str, code: str, language: str) -> Dict[str, Any]:
        """Convert text response to structured analysis"""
        # Simple text analysis when JSON parsing fails
        issues = []
        
        # Look for common issue indicators in the response
        issue_keywords = {
            'bug': ['error', 'wrong', 'incorrect', 'mistake', 'fault'],
            'security': ['security', 'vulnerable', 'exploit', 'attack', 'unsafe'],
            'performance': ['slow', 'inefficient', 'optimize', 'performance', 'memory'],
            'style': ['style', 'convention', 'format', 'naming', 'structure']
        }
        
        for issue_type, keywords in issue_keywords.items():
            for keyword in keywords:
                if keyword.lower() in response.lower():
                    issues.append({
                        "id": f"text_{issue_type}_{len(issues)+1}",
                        "type": issue_type,
                        "severity": "medium",
                        "line_number": None,
                        "description": f"Potential {issue_type} issue detected in analysis",
                        "suggestion": f"Review code for {issue_type} concerns mentioned in analysis"
                    })
                    break  # Only add one issue per type
        
        return {
            "summary": {
                "overall_score": 80 - len(issues) * 5,
                "total_issues": len(issues),
                "critical_issues": 0,
                "security_score": 85
            },
            "issues": issues,
            "suggestions": [
                {
                    "category": "general",
                    "description": "Review the detailed analysis for specific recommendations",
                    "priority": "medium"
                }
            ],
            "metadata": {
                "analysis_id": f"gguf_text_{int(time.time())}",
                "language": language,
                "code_lines": len(code.split('\n')),
                "analysis_timestamp": time.time(),
                "model": "deepseek-coder-1.3b-gguf",
                "analysis_type": "text_parsing",
                "raw_response": response[:500]  # First 500 chars
            }
        }
    
    def _create_fallback_analysis(self, code: str, language: str) -> Dict[str, Any]:
        """Create fallback analysis when GGUF fails"""
        return {
            "summary": {
                "overall_score": 70,
                "total_issues": 1,
                "critical_issues": 0,
                "security_score": 75
            },
            "issues": [
                {
                    "id": "gguf_fallback_1",
                    "type": "system",
                    "severity": "low",
                    "line_number": None,
                    "description": "GGUF model analysis temporarily unavailable",
                    "suggestion": "Try again or use static analysis tools"
                }
            ],
            "metadata": {
                "analysis_id": f"gguf_fallback_{int(time.time())}",
                "language": language,
                "code_lines": len(code.split('\n')),
                "analysis_timestamp": time.time(),
                "model": "gguf_fallback",
                "analysis_type": "fallback"
            }
        }

# Global service instance
gguf_analyzer = GGUFCodeAnalyzer(os.getenv("MODEL_PATH", "/app/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf"))