from typing import Dict, Any, Optional, List
import os
import json
from pathlib import Path
import logging
import asyncio
import gc
import time
from concurrent.futures import ThreadPoolExecutor
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
CPU_THREADS = 2  # Reduced from 4 to lower CPU usage
CPU_THROTTLE_DELAY = 0.1  # Add small delay between operations


class AICodeAnalyzer:
    """Service for analyzing code using the DeepSeek Coder model."""
    
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.last_cleanup_time = 0
        self.cleanup_interval = 300  # 5 minutes
        # Shared thread pool to avoid creating new ones
        self.thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-model")
        # Model will be loaded lazily when needed
    
    async def load_model(self) -> None:
        """Load the DeepSeek Coder model asynchronously."""
        if self.model_loaded:
            return
            
        try:
            model_path = Path(MODEL_PATH).resolve()
            if not model_path.exists():
                logger.error(f"Model file not found at {model_path}")
                return
            
            logger.info(f"Loading DeepSeek Coder model from {model_path}")
            
            # Load model in shared thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                self.thread_pool,
                self._load_model_sync,
                str(model_path)
            )
            
            if self.model is not None:
                self.model_loaded = True
                logger.info("DeepSeek Coder model loaded successfully")
            else:
                logger.error("Failed to load model")
                self.model_loaded = False
                
        except Exception as e:
            logger.error(f"Failed to load DeepSeek Coder model: {str(e)}")
            self.model_loaded = False
    
    def _load_model_sync(self, model_path: str) -> Optional[Llama]:
        """Synchronous model loading for thread executor."""
        try:
            # Add CPU throttling during model loading
            time.sleep(CPU_THROTTLE_DELAY)
            return Llama(
                model_path=model_path,
                n_ctx=CONTEXT_SIZE,
                n_threads=CPU_THREADS,
                verbose=False
            )
        except Exception as e:
            logger.error(f"Error in sync model loading: {e}")
            return None
    
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
            await self.load_model()
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
            
            # Generate response from the model asynchronously with CPU throttling
            await asyncio.sleep(CPU_THROTTLE_DELAY)  # CPU throttling before inference
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.thread_pool,
                self._generate_completion_sync,
                prompt
            )
            
            # Memory cleanup after inference
            await self._cleanup_after_analysis()
            
            # Extract and parse the generated text
            generated_text = response["choices"][0]["text"]
            logger.info(f"Generated response length: {len(generated_text)}")
            
            # Parse the JSON response
            analysis_result = self._parse_ai_response(generated_text, language, analysis_type, code)
            
            logger.info(f"✅ AI analysis completed successfully")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Error during code analysis: {str(e)}")
            # Ensure cleanup even on error
            await self._cleanup_after_analysis()
            return self._generate_fallback_response(f"Analysis failed: {str(e)}", request.code)
    
    # Legacy method for backward compatibility (if needed)
    async def analyze_code_legacy(self, 
                                 code: str, 
                                 language: SupportedLanguage, 
                                 analysis_type: AnalysisType = AnalysisType.FULL) -> Dict[str, Any]:
        """Legacy method for backward compatibility - now properly async."""
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
        
        # Call the main async method
        return await self.analyze_code(request)
    
    def _create_analysis_prompt(self, code: str, language: str, analysis_type: str) -> str:
        """Create a comprehensive analysis prompt for the DeepSeek Coder model."""
        system_prompt = (
            "You are an expert code reviewer with deep knowledge of modern software development practices. "
            "Provide comprehensive, educational feedback that helps developers improve their skills. "
            "Focus on code quality, security, performance, maintainability, and best practices. "
            "Always provide constructive suggestions with explanations."
        )
        
        # Create language-specific analysis instructions
        language_specific_checks = self._get_language_specific_checks(language.lower())
        
        # Adjust the prompt based on analysis type
        focus_instruction = ""
        if analysis_type != "full":
            focus_map = {
                "bugs_only": "Focus primarily on bugs, logical errors, and potential runtime issues. Still provide brief insights on code quality.",
                "security_only": "Focus primarily on security vulnerabilities and potential attack vectors. Include security best practices.",
                "performance_only": "Focus primarily on performance optimizations, efficiency improvements, and scalability concerns.",
                "style_only": "Focus primarily on code style, formatting, naming conventions, and maintainability best practices."
            }
            focus_instruction = focus_map.get(analysis_type, "")
        
        user_prompt = (
            f"COMPREHENSIVE CODE REVIEW of this {language} code:\n```\n{code}\n```\n\n"
            f"{focus_instruction}\n\n"
            f"{language_specific_checks}\n\n"
            "ANALYSIS FRAMEWORK:\n"
            "1. SECURITY ASSESSMENT:\n"
            "   - Identify vulnerabilities (XSS, injection attacks, insecure data handling)\n"
            "   - Check for hardcoded secrets or sensitive data exposure\n"
            "   - Evaluate input validation and sanitization\n"
            "   - Assess authentication and authorization patterns\n\n"
            "2. CODE QUALITY EVALUATION:\n"
            "   - Function complexity and readability\n"
            "   - Naming conventions and code organization\n"
            "   - Error handling and edge case coverage\n"
            "   - Code reusability and modularity\n\n"
            "3. PERFORMANCE ANALYSIS:\n"
            "   - Algorithmic efficiency and optimization opportunities\n"
            "   - Memory usage and resource management\n"
            "   - Async/await patterns and Promise handling\n"
            "   - DOM manipulation efficiency\n\n"
            "4. BEST PRACTICES & MAINTAINABILITY:\n"
            "   - Modern language features usage\n"
            "   - Design patterns and architectural considerations\n"
            "   - Testing considerations and testability\n"
            "   - Documentation and code comments\n\n"
            "SCORING GUIDELINES:\n"
            "- Critical security vulnerabilities: Score 1-3\n"
            "- Major bugs or logic errors: Score 2-4\n"
            "- Poor practices or maintainability issues: Score 4-6\n"
            "- Good code with minor improvements: Score 6-8\n"
            "- Excellent code following best practices: Score 8-10\n\n"
            "CONSTRUCTIVE FEEDBACK FOR CLEAN CODE:\n"
            "Even when code is clean and functional, ALWAYS provide educational suggestions in these areas:\n"
            "1. DOCUMENTATION: JSDoc comments, inline documentation, README considerations\n"
            "2. ROBUSTNESS: Input validation, error handling, edge case coverage\n"
            "3. TYPE SAFETY: TypeScript migration, parameter typing, return type annotations\n"
            "4. MAINTAINABILITY: Code organization, modularity, naming improvements\n"
            "5. TESTING: Unit test suggestions, test coverage, testability improvements\n"
            "6. PERFORMANCE: Optimization opportunities, scalability considerations\n"
            "7. ACCESSIBILITY: UI/UX improvements for user-facing code\n"
            "8. SECURITY: Defense-in-depth practices, security best practices\n\n"
            "IMPORTANT: Always provide educational explanations for your findings. "
            "Even for perfect code, suggest enhancements that demonstrate professional development practices.\n\n"
            "Return ONLY valid JSON in this exact format:\n"
            "{\n"
            '  "bugs": ["Detailed bug descriptions with explanations"],\n'
            '  "security": ["Security issues with impact explanations"],\n'
            '  "performance": ["Performance improvements with rationale"],\n'
            '  "quality": ["Code quality insights and best practice suggestions"],\n'
            '  "score": 7,\n'
            '  "summary": "Comprehensive analysis summary with educational insights and actionable recommendations"\n'
            "}\n\n"
            "Ensure all arrays contain meaningful, educational content even if no critical issues are found."
        )
        
        # Format for DeepSeek Coder
        full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n"
        return full_prompt
    
    def _get_language_specific_checks(self, language: str) -> str:
        """Get language-specific analysis guidelines."""
        checks = {
            "javascript": """
JAVASCRIPT-SPECIFIC ANALYSIS POINTS:

🔐 SECURITY CONSIDERATIONS:
- DOM manipulation safety (innerHTML vs textContent)
- Event listener security and XSS prevention
- CORS configuration and same-origin policy
- Input validation and sanitization
- Client-side storage security (localStorage, sessionStorage)
- eval() usage and code injection risks
- Third-party script inclusion safety

⚡ PERFORMANCE OPTIMIZATION:
- Event delegation patterns
- DOM query optimization (querySelector vs getElementById)
- Memory leak prevention (event listener cleanup)
- Efficient array/object operations
- Bundle size and lazy loading opportunities
- Unnecessary re-renders in frameworks

📝 CODE QUALITY & BEST PRACTICES:
- Modern ES6+ features utilization (const/let, arrow functions, destructuring)
- Promise patterns vs async/await
- Error handling with try/catch blocks
- Function purity and side effects
- Consistent naming conventions (camelCase)
- Module import/export patterns

🏗️ ARCHITECTURAL PATTERNS:
- Separation of concerns
- Component composition patterns
- State management approaches
- API interaction patterns
- Error boundary implementations
- Testing strategy considerations

📚 EDUCATIONAL ENHANCEMENTS FOR CLEAN CODE:
- JSDoc documentation with @param, @returns, @example tags
- Input validation using libraries like Joi or custom validators
- Error handling with custom Error classes and proper error propagation
- TypeScript migration path and type annotations
- Unit testing with Jest/Mocha and test-driven development
- Code organization with modules, namespaces, and design patterns
- Accessibility considerations for DOM manipulation
- Performance monitoring and optimization techniques
- Security hardening practices and secure coding guidelines
- Modern JavaScript features and upcoming ECMAScript proposals""",
            
            "typescript": """
TYPESCRIPT-SPECIFIC ANALYSIS POINTS:

🔐 SECURITY CONSIDERATIONS:
- Type safety for security-critical operations
- Strict null checks and undefined handling
- Interface contracts for API boundaries
- Generic type constraints for input validation

⚡ PERFORMANCE OPTIMIZATION:
- Type-only imports for better tree-shaking
- Union type efficiency
- Conditional types for compile-time optimization
- Proper type guards for runtime checks

📝 CODE QUALITY & BEST PRACTICES:
- Type annotation completeness
- Interface vs type alias usage
- Generic type parameter naming
- Utility types utilization (Pick, Omit, etc.)
- Strict compiler options adherence
- Enum vs const assertions

🏗️ ARCHITECTURAL PATTERNS:
- Dependency injection patterns
- Abstract factory implementations
- Decorator patterns
- Advanced type system usage""",
            
            "python": """
PYTHON-SPECIFIC ANALYSIS POINTS:

🔐 SECURITY CONSIDERATIONS:
- SQL injection prevention
- Path traversal vulnerabilities
- Pickle/eval security risks
- Input validation and sanitization

⚡ PERFORMANCE OPTIMIZATION:
- List comprehensions vs loops
- Generator usage for memory efficiency
- Appropriate data structure selection
- Caching strategies

📝 CODE QUALITY & BEST PRACTICES:
- PEP 8 compliance
- Type hints usage
- Docstring completeness
- Exception handling patterns
- Context managers usage

🏗️ ARCHITECTURAL PATTERNS:
- Class design and inheritance
- Decorator patterns
- Context manager implementations
- Module organization""",
        }
        
        return checks.get(language, "General code analysis focusing on security, performance, and maintainability.")
    
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
        """Create intelligent fallback analysis based on code patterns with educational insights."""
        code_lower = code.lower()
        ai_text_lower = ai_text.lower()
        
        bugs = []
        security = []
        performance = []
        quality = []
        score = 7  # Default good score
        summary = "Code analysis completed with educational insights."
        
        # Detect programming language for specific checks
        is_javascript = any(keyword in code_lower for keyword in ['function', 'const ', 'let ', 'var ', '=>', 'document.', 'window.'])
        is_python = any(keyword in code_lower for keyword in ['def ', 'import ', 'from ', 'if __name__'])
        
        # CRITICAL SECURITY CHECKS
        if "select * from" in code_lower and ("+ " in code or "' + " in code):
            security.append("CRITICAL: SQL Injection vulnerability - user input concatenated directly into SQL query. Use parameterized queries instead.")
            score = 1
            summary = "Critical SQL injection vulnerability detected - immediate fix required"
        elif ".innerhtml" in code_lower and ("input" in code_lower or "value" in code_lower):
            security.append("CRITICAL: XSS vulnerability - user input directly inserted into DOM via innerHTML. Use textContent or properly sanitize input.")
            score = 2
            summary = "Critical XSS vulnerability detected - use safe DOM manipulation"
        elif "eval(" in code_lower:
            security.append("HIGH: Code injection risk - eval() executes arbitrary code. Consider safer alternatives like JSON.parse() for data.")
            score = 3
            summary = "High-risk eval() usage detected"
        elif ("password" in code_lower or "api_key" in code_lower or "secret" in code_lower) and ("=" in code and '"' in code):
            security.append("HIGH: Hardcoded credentials detected. Store sensitive data in environment variables or secure vaults.")
            score = 3
            summary = "Security issue: hardcoded credentials found"
        
        # JAVASCRIPT-SPECIFIC ANALYSIS
        if is_javascript:
            # Performance checks
            if "getelementbyid" in code_lower and "for" in code_lower:
                performance.append("Consider caching DOM queries outside loops to improve performance. Store element references in variables.")
                
            if "addeventlistener" in code_lower and "removeeventlistener" not in code_lower:
                quality.append("Remember to remove event listeners to prevent memory leaks, especially in single-page applications.")
                
            if "var " in code:
                quality.append("Consider using 'const' or 'let' instead of 'var' for better scope control and to avoid hoisting issues.")
                
            if "== " in code and "=== " not in code:
                quality.append("Use strict equality (===) instead of loose equality (==) to avoid type coercion issues.")
                
            if "promise" in code_lower and "catch" not in code_lower:
                bugs.append("Missing error handling for Promise. Add .catch() or use try/catch with async/await.")
                
            if "fetch(" in code_lower and "await" not in code_lower and ".then" not in code_lower:
                bugs.append("Fetch call should be awaited or use .then() to handle the Promise properly.")
                
            # Best practices
            if "function" in code and "=>" not in code:
                quality.append("Consider using arrow functions for shorter syntax and lexical 'this' binding when appropriate.")
                
            if code.count("console.log") > 2:
                quality.append("Multiple console.log statements found. Consider using a proper logging solution for production code.")
        
        # PYTHON-SPECIFIC ANALYSIS
        elif is_python:
            if "except:" in code_lower and "pass" in code_lower:
                bugs.append("Bare except clause with pass can hide errors. Specify exception types and handle appropriately.")
                
            if "open(" in code_lower and "with" not in code_lower:
                quality.append("Use context managers (with statement) for file operations to ensure proper resource cleanup.")
                
            if "range(len(" in code_lower:
                quality.append("Consider using enumerate() instead of range(len()) for cleaner, more Pythonic iteration.")
        
        # GENERAL CODE QUALITY CHECKS
        lines = code.strip().split('\n')
        if len(lines) < 3:
            quality.append("Code snippet is quite short. Consider adding documentation or comments for context.")
            
        if not any(comment in code for comment in ['//', '#', '/*', '"""', "'''"]):
            quality.append("Adding comments would improve code maintainability and help other developers understand the logic.")
            
        if any(name in code for name in ['temp', 'tmp', 'test', 'data', 'result']) and 'function' in code_lower:
            quality.append("Consider using more descriptive variable names to improve code readability and maintainability.")
            
        # Error handling assessment
        if "try" in code_lower and "catch" in code_lower:
            score += 1
            quality.append("Good use of error handling! Consider logging errors for debugging purposes.")
        elif "try" in code_lower and "except" in code_lower:
            score += 1
            quality.append("Good use of error handling! Consider being specific about exception types.")
            
        # Function complexity check
        if code.count('{') > 10 or code.count('if') > 5:
            quality.append("Function appears complex. Consider breaking it into smaller, more focused functions for better maintainability.")
            score -= 1
            
        # Enhanced educational feedback for clean code
        if is_javascript:
            # Always provide JavaScript-specific improvements, even for clean code
            if not any("JSDoc" in item for item in quality):
                quality.append("Add JSDoc documentation with @param, @returns, and @example tags to improve code maintainability and IDE support.")
            
            if "function" in code_lower and not any("validation" in item.lower() for item in bugs + quality):
                quality.append("Consider adding input validation to handle unexpected parameter types and improve function robustness.")
            
            if "function" in code_lower and "try" not in code_lower:
                quality.append("Add error handling with try-catch blocks to gracefully handle potential runtime errors and improve user experience.")
            
            if not any("TypeScript" in item for item in quality):
                quality.append("Consider migrating to TypeScript for better type safety, enhanced IDE support, and improved code documentation through type annotations.")
                
            if len(lines) <= 5 and "function" in code_lower:
                quality.append("For small functions like this, consider: 1) Adding unit tests, 2) Grouping related functions in modules, 3) Using modern ES6+ features.")
                
            # Performance suggestions for any JavaScript code
            if not performance:
                performance.append("Consider performance monitoring: add timing measurements, optimize for specific use cases, and consider memoization for pure functions.")
        
        elif is_python:
            # Enhanced Python-specific feedback
            if not any("docstring" in item.lower() for item in quality):
                quality.append("Add comprehensive docstrings following Google or NumPy style for better documentation and IDE support.")
            
            if "def " in code_lower and not any("type hint" in item.lower() for item in quality):
                quality.append("Add type hints for parameters and return values to improve code clarity and enable better static analysis.")
                
            if not any("test" in item.lower() for item in quality):
                quality.append("Consider adding unit tests using pytest or unittest to ensure code reliability and facilitate refactoring.")
        
        # Universal improvements for any clean code
        if not bugs and not security and not performance and not quality:
            quality.append("Excellent code foundation! Consider these professional enhancements:")
            quality.append("1. Documentation: Add comprehensive comments and API documentation")
            quality.append("2. Testing: Implement unit tests and integration tests for reliability")
            quality.append("3. Error Handling: Add robust error handling and logging mechanisms")
            quality.append("4. Modularity: Organize code into reusable, focused modules")
            
            summary = "Clean code with strong fundamentals. Ready for professional enhancement through documentation, testing, and architectural improvements."
        else:
            summary = "Code analysis shows good practices with targeted suggestions for professional development and best practices."
            
        # Adjust score based on findings
        if security:
            score = min(score, 4)
        if bugs:
            score = min(score, 5)
        if len(quality) > 3:
            score -= 1
            
        # Ensure score is within bounds
        score = max(1, min(10, score))
        
        # Ensure we always provide constructive educational feedback
        if not bugs:
            bugs = ["No critical bugs detected. Code follows good logical structure and practices."]
            
        if not security:
            if is_javascript:
                security = ["No immediate security vulnerabilities found. Consider implementing Content Security Policy (CSP) and input sanitization as defensive measures."]
            else:
                security = ["No immediate security vulnerabilities found. Continue following secure coding practices and principle of least privilege."]
        
        if not performance:
            if is_javascript:
                performance = ["No major performance issues detected. For production optimization, consider: code minification, lazy loading, and performance monitoring."]
            elif is_python:
                performance = ["No major performance issues detected. For production optimization, consider: caching strategies, async operations, and profiling tools."]
            else:
                performance = ["No major performance issues detected. Consider profiling for optimization opportunities and scalability planning."]
        
        if not quality:
            quality = ["Code structure is clean and readable. Ready for professional enhancement through documentation, testing, and modular organization."]
        
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
    
    def _generate_completion_sync(self, prompt: str) -> Dict[str, Any]:
        """Synchronous completion generation for thread executor."""
        try:
            # Add CPU throttling during inference
            time.sleep(CPU_THROTTLE_DELAY)
            result = self.model.create_completion(
                prompt=prompt,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                stop=["</s>", "<|im_end|"],
                echo=False
            )
            # Small delay after inference to prevent CPU spikes
            time.sleep(CPU_THROTTLE_DELAY)
            return result
        except Exception as e:
            logger.error(f"Error in sync completion generation: {e}")
            return {"choices": [{"text": f"Error: {str(e)}"}]}
    
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
                    
                issue = CodeIssue(
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
                )
                issues.append(issue.dict())  # Convert to dictionary

        # Process security issues
        for i, issue in enumerate(security_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                severity = IssueSeverity.HIGH
                if any(word in issue.lower() for word in ['injection', 'xss', 'auth', 'critical']):
                    severity = IssueSeverity.CRITICAL
                    
                issue_obj = CodeIssue(
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
                )
                issues.append(issue_obj.dict())  # Convert to dictionary
                
        # Process performance issues
        for i, issue in enumerate(performance_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                issue_obj = CodeIssue(
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
                )
                issues.append(issue_obj.dict())  # Convert to dictionary
        
        # Process quality issues
        for i, issue in enumerate(quality_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                issue_obj = CodeIssue(
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
                )
                issues.append(issue_obj.dict())  # Convert to dictionary
        
        logger.info(f"Created {len(issues)} total issues")
        
        # Create metrics
        lines_of_code = len([line.strip() for line in code.split('\n') if line.strip() and not line.strip().startswith('#')]) if code else 1
        
        # Use AI score directly but cap it if critical issues exist
        actual_score = max(1, min(10, score))
        critical_count = len([i for i in issues if i.get('severity') == IssueSeverity.CRITICAL])
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
            critical_issues=len([i for i in issues if i.get('severity') == IssueSeverity.CRITICAL]),
            high_issues=len([i for i in issues if i.get('severity') == IssueSeverity.HIGH]),
            medium_issues=len([i for i in issues if i.get('severity') == IssueSeverity.MEDIUM]),
            low_issues=len([i for i in issues if i.get('severity') == IssueSeverity.LOW]),
            overall_score=actual_score,
            recommendation=self._get_recommendation(actual_score, len(issues), ai_data)
        )
        
        # Generate meaningful suggestions from analysis data
        suggestions = []
        
        # Add suggestions from AI response data if available
        if quality_issues:
            suggestions.extend(quality_issues[:3])  # Top 3 quality suggestions
            
        # Add suggestions from other categories for a comprehensive view
        if performance_issues:
            suggestions.extend([f"Performance: {issue}" for issue in performance_issues[:2]])
            
        if security_issues:
            suggestions.extend([f"Security: {issue}" for issue in security_issues[:2]])
            
        # If no specific suggestions, generate based on analysis context
        if not suggestions:
            if actual_score >= 8:
                suggestions = [
                    "Excellent code! Consider adding comprehensive documentation and unit tests.",
                    "Implement automated testing and continuous integration for production readiness.",
                    "Consider performance profiling and optimization for scale."
                ]
            elif actual_score >= 6:
                suggestions = [
                    "Good code foundation! Focus on improving code documentation and error handling.",
                    "Add input validation and comprehensive testing for better reliability.",
                    "Consider refactoring for better maintainability and modularity."
                ]
            else:
                suggestions = [
                    "Address critical and high-severity issues first for stability.",
                    "Implement proper error handling and input validation.",
                    "Add comprehensive testing and code review processes."
                ]
        
        # Ensure we have meaningful suggestions, limit to 5 to avoid overwhelming
        suggestions = [s for s in suggestions if s and isinstance(s, str) and len(s.strip()) > 10][:5]
        
        return {
            "issues": issues,  # Already converted to dictionaries above
            "metrics": metrics.dict(),  # Convert to dictionary
            "summary": summary.dict(),  # Convert to dictionary
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
    
    async def _cleanup_after_analysis(self):
        """Perform memory cleanup after AI analysis completion"""
        current_time = time.time()
        
        # Only cleanup if enough time has passed to avoid excessive cleanup
        if current_time - self.last_cleanup_time < self.cleanup_interval:
            return
            
        try:
            logger.debug("🧹 Performing post-analysis memory cleanup")
            
            # Force garbage collection to free unused memory
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"Garbage collected {collected} objects after AI analysis")
            
            # Optional: Unload model if memory pressure is high
            try:
                import psutil
                memory_percent = psutil.virtual_memory().percent
                if memory_percent > 90:  # If system memory > 90%
                    logger.warning(f"High memory usage {memory_percent:.1f}%, considering model unload")
                    await self._unload_model_if_needed()
            except ImportError:
                pass  # psutil not available
                
            self.last_cleanup_time = current_time
            
        except Exception as e:
            logger.error(f"❌ Error during post-analysis cleanup: {e}")
    
    async def _unload_model_if_needed(self):
        """Unload model if memory pressure is too high"""
        if self.model_loaded and self.model is not None:
            try:
                logger.warning("🗑️ Unloading AI model due to high memory pressure")
                self.model = None
                self.model_loaded = False
                # Force garbage collection after model unload
                gc.collect()
                logger.info("✅ AI model unloaded successfully")
            except Exception as e:
                logger.error(f"❌ Error unloading model: {e}")
    
    def __del__(self):
        """Cleanup thread pool on destruction"""
        try:
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=False)
        except Exception:
            pass  # Ignore cleanup errors during destruction


# Singleton instance
ai_analyzer = AICodeAnalyzer()