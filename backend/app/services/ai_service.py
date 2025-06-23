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
        # Shared thread pool with increased workers for better performance
        self.thread_pool = ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2), thread_name_prefix="ai-model")
        
        # Rate limiting semaphores for resource management
        self.model_loading_semaphore = asyncio.Semaphore(1)  # Only one model load at a time
        self.inference_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent AI inferences
        self.request_rate_limiter = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        # Enhanced cache with memory management
        self.analysis_cache = {}
        self.cache_max_size = 50  # Reduced to prevent memory issues
        self.cache_memory_limit = 100 * 1024 * 1024  # 100MB cache limit
        self.cache_size_bytes = 0
        
        # Circuit breaker for AI operations
        self.ai_failure_count = 0
        self.ai_failure_threshold = 5
        self.ai_recovery_time = 300  # 5 minutes
        self.ai_last_failure = 0
        
        # Model will be loaded lazily when needed
    
    async def load_model(self) -> None:
        """Load the DeepSeek Coder model asynchronously with rate limiting."""
        if self.model_loaded:
            return
            
        # Apply rate limiting for model loading
        async with self.model_loading_semaphore:
            # Double-check after acquiring semaphore
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
        Analyze code using the DeepSeek Coder model with rate limiting and circuit breaker.
        
        Args:
            request: CodeAnalysisRequest object containing all analysis parameters
            
        Returns:
            Dict containing analysis results in the expected format
        """
        # Apply rate limiting for concurrent requests
        async with self.request_rate_limiter:
            # Check circuit breaker state
            if self._is_circuit_breaker_open():
                logger.warning("AI service circuit breaker is open, using fallback")
                return await self._generate_fallback_response(request)
            
            # Check cache first for performance improvement
            import hashlib
            cache_key = hashlib.md5(f"{request.code}_{request.language}_{request.analysis_type}".encode()).hexdigest()
            
            if cache_key in self.analysis_cache:
                logger.info("Returning cached analysis result")
                return self.analysis_cache[cache_key]
        
        if not self.model_loaded or self.model is None:
            logger.warning("Model not loaded, attempting to reload")
            await self.load_model()
            if not self.model_loaded:
                return await self._generate_fallback_response(request)
        
        try:
            logger.info(f"Starting AI analysis for {request.language} code, analysis type: {request.analysis_type}")
            
            # Extract parameters from request
            code = request.code
            language = request.language
            analysis_type = request.analysis_type
            
            # Prepare the prompt for the model
            prompt = self._create_analysis_prompt(code, language.value, analysis_type.value)
            
            # Apply rate limiting for AI inference
            async with self.inference_semaphore:
                try:
                    # Generate response from the model asynchronously with CPU throttling
                    await asyncio.sleep(CPU_THROTTLE_DELAY)  # CPU throttling before inference
                    loop = asyncio.get_event_loop()
                    response = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.thread_pool,
                            self._generate_completion_sync,
                            prompt
                        ),
                        timeout=300.0  # INCREASED from 2 minutes to 5 minutes for complex AI inference
                    )
                    
                    # Reset failure count on success
                    self.ai_failure_count = 0
                    
                except asyncio.TimeoutError:
                    logger.error("AI inference timed out after 2 minutes")
                    self._record_ai_failure()
                    return await self._generate_fallback_response(request)
                except Exception as e:
                    logger.error(f"AI inference failed: {str(e)}")
                    self._record_ai_failure()
                    return await self._generate_fallback_response(request)
            
            # Memory cleanup after inference
            await self._cleanup_after_analysis()
            
            # Extract and parse the generated text
            generated_text = response["choices"][0]["text"]
            logger.info(f"Generated response length: {len(generated_text)}")
            
            # Parse the JSON response
            analysis_result = self._parse_ai_response(generated_text, language, analysis_type, code)
            
            # Cache the result for future use with memory management
            self._manage_cache_memory(cache_key, analysis_result)
            
            logger.info(f"AI analysis completed successfully")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error during code analysis: {str(e)}")
            self._record_ai_failure()
            # Ensure cleanup even on error
            await self._cleanup_after_analysis()
            return await self._generate_fallback_response(request)
    
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
            "SMART FEEDBACK STRATEGY:\n"
            "For simple functions (under 10 lines), provide 2-3 SPECIFIC, ACTIONABLE suggestions.\n"
            "For complex code (10+ lines), provide up to 5 suggestions.\n"
            "PRIORITIZE immediate, actionable improvements over generic advice:\n\n"
            "HIGH PRIORITY (simple functions):\n"
            "- Missing JSDoc/documentation for function parameters and return values\n"
            "- Missing input validation for function parameters\n"
            "- Missing error handling for operations that could fail\n"
            "- Specific naming improvements (vague variable names)\n\n"
            "LOWER PRIORITY (complex functions only):\n"
            "- Language migration suggestions (TypeScript, etc.)\n"
            "- Architecture patterns and code organization\n"
            "- Performance optimizations for non-performance-critical code\n"
            "- General testing suggestions without specific test cases\n\n"
            "IMPORTANT: Focus on what the developer can implement immediately. "
            "Avoid generic advice like 'consider using TypeScript' for simple working functions.\n\n"
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
# JAVASCRIPT-SPECIFIC ANALYSIS POINTS:

# SECURITY CONSIDERATIONS:
- DOM manipulation safety (innerHTML vs textContent)
- Event listener security and XSS prevention
- CORS configuration and same-origin policy
- Input validation and sanitization
- Client-side storage security (localStorage, sessionStorage)
- eval() usage and code injection risks
- Third-party script inclusion safety

# PERFORMANCE OPTIMIZATION:
- Event delegation patterns
- DOM query optimization (querySelector vs getElementById)
- Memory leak prevention (event listener cleanup)
- Efficient array/object operations
- Bundle size and lazy loading opportunities
- Unnecessary re-renders in frameworks

# CODE QUALITY & BEST PRACTICES:
- Modern ES6+ features utilization (const/let, arrow functions, destructuring)
- Promise patterns vs async/await
- Error handling with try/catch blocks
- Function purity and side effects
- Consistent naming conventions (camelCase)
- Module import/export patterns

# ARCHITECTURAL PATTERNS:
- Separation of concerns
- Component composition patterns
- State management approaches
- API interaction patterns
- Error boundary implementations
- Testing strategy considerations

# EDUCATIONAL ENHANCEMENTS FOR CLEAN CODE:
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
# TYPESCRIPT-SPECIFIC ANALYSIS POINTS:

# SECURITY CONSIDERATIONS:
- Type safety for security-critical operations
- Strict null checks and undefined handling
- Interface contracts for API boundaries
- Generic type constraints for input validation

# PERFORMANCE OPTIMIZATION:
- Type-only imports for better tree-shaking
- Union type efficiency
- Conditional types for compile-time optimization
- Proper type guards for runtime checks

# CODE QUALITY & BEST PRACTICES:
- Type annotation completeness
- Interface vs type alias usage
- Generic type parameter naming
- Utility types utilization (Pick, Omit, etc.)
- Strict compiler options adherence
- Enum vs const assertions

# ARCHITECTURAL PATTERNS:
- Dependency injection patterns
- Abstract factory implementations
- Decorator patterns
- Advanced type system usage""",
            
            "python": """
# PYTHON-SPECIFIC ANALYSIS POINTS:

# SECURITY CONSIDERATIONS:
- SQL injection prevention
- Path traversal vulnerabilities
- Pickle/eval security risks
- Input validation and sanitization

# PERFORMANCE OPTIMIZATION:
- List comprehensions vs loops
- Generator usage for memory efficiency
- Appropriate data structure selection
- Caching strategies

# CODE QUALITY & BEST PRACTICES:
- PEP 8 compliance
- Type hints usage
- Docstring completeness
- Exception handling patterns
- Context managers usage

# ARCHITECTURAL PATTERNS:
- Class design and inheritance
- Decorator patterns
- Context manager implementations
- Module organization""",

            "c": """
# C-SPECIFIC ANALYSIS POINTS:

# CRITICAL SECURITY VULNERABILITIES:
- Buffer overflow vulnerabilities: strcpy(), strcat(), gets(), sprintf() without bounds checking
- Format string vulnerabilities: printf() family with user-controlled format strings
- Memory corruption: use-after-free, double-free, dangling pointers
- Integer overflow/underflow leading to buffer overflows
- Null pointer dereference causing segmentation faults
- Stack-based buffer overflows from unsafe array access
- Heap corruption from incorrect malloc/free usage
- Command injection through system(), popen() with unsanitized input
- Race conditions in multi-threaded code accessing shared memory
- Uninitialized variable usage leading to unpredictable behavior

# MEMORY MANAGEMENT BEST PRACTICES:
- Every malloc()/calloc() must have corresponding free()
- Set pointers to NULL after freeing to prevent use-after-free
- Check return values of malloc/calloc for allocation failures
- Use valgrind or AddressSanitizer to detect memory leaks
- Prefer stack allocation over heap when lifetime is predictable
- Implement RAII-like patterns with cleanup functions
- Use static analysis tools like Clang Static Analyzer
- Initialize all variables before use
- Avoid memory leaks in error handling paths
- Consider using memory pools for frequent allocations

# PERFORMANCE OPTIMIZATION:
- Memory allocation efficiency (prefer stack over heap when possible)
- Cache-friendly data structures and sequential memory access
- Loop optimization and avoiding function calls in tight loops
- Bit manipulation for faster arithmetic operations
- Memory alignment for optimal processor performance
- Minimize system calls and I/O operations
- Use const correctness for compiler optimizations
- Profile code to identify actual bottlenecks

# CODE QUALITY & DEFENSIVE PROGRAMMING:
- Always check return values of functions that can fail
- Validate function parameters at entry points
- Use const keyword for immutable data
- Implement comprehensive error handling with meaningful error codes
- Use assert() for debugging invariants
- Follow consistent naming conventions
- Add comprehensive comments for complex pointer arithmetic
- Use static functions to limit scope and improve modularity
- Implement proper cleanup in all error paths
- Use safer alternatives: strncpy() instead of strcpy(), snprintf() instead of sprintf()

# ARCHITECTURAL PATTERNS & BEST PRACTICES:
- Design clear module interfaces with header files
- Use opaque pointers to hide implementation details
- Implement proper error propagation mechanisms
- Use function pointers for callbacks and plugin architectures
- Follow single responsibility principle for functions
- Minimize global variables and use static for file-local variables
- Implement consistent resource management patterns
- Use preprocessor macros judiciously with proper guarding
- Consider using C11 features like _Static_assert for compile-time checks""",

            "go": """
# GO-SPECIFIC ANALYSIS POINTS:

# CRITICAL SECURITY VULNERABILITIES:
- SQL injection: Use parameterized queries with database/sql, never string concatenation
- Cross-site scripting (XSS): Sanitize output with html/template, validate input
- Path traversal: Validate file paths with filepath.Clean() and check boundaries
- Command injection: Avoid os/exec with user input, use allowlists for commands
- CSRF attacks: Implement proper CSRF tokens in web applications
- JWT vulnerabilities: Validate signatures, check expiration, use secure algorithms
- TLS misconfiguration: Use strong cipher suites, validate certificates properly
- Race conditions: Protect shared resources with mutexes or channels

# GOROUTINE LEAK PREVENTION:
- Always ensure goroutines have a way to terminate (context cancellation)
- Use context.WithTimeout() or context.WithCancel() for long-running operations
- Avoid infinite loops without exit conditions in goroutines
- Close channels properly to signal goroutine completion
- Use sync.WaitGroup to coordinate goroutine completion
- Monitor goroutine count in production (runtime.NumGoroutine())
- Implement graceful shutdown with signal handling
- Use worker pools instead of spawning unlimited goroutines
- Set timeouts for network operations to prevent hanging goroutines
- Test for goroutine leaks using goleak package

# PERFORMANCE OPTIMIZATION:
- Channel buffering strategies to reduce blocking
- Use sync.Pool for expensive object reuse
- Prefer strings.Builder over string concatenation in loops
- Minimize interface{} usage and type assertions
- Use slice make() with capacity when size is known
- Optimize memory allocations to reduce GC pressure
- Profile with go tool pprof to identify bottlenecks
- Use benchmark tests to validate performance improvements

# CODE QUALITY & IDIOMATIC GO:
- Proper error handling: check every error, wrap with fmt.Errorf() or errors.Wrap()
- Use panic/recover only for truly exceptional situations
- Design minimal interfaces (accept interfaces, return structs)
- Follow effective Go naming conventions (camelCase, no underscores)
- Use context.Context for cancellation and deadlines in long operations
- Always use defer for cleanup (close files, unlock mutexes)
- Initialize with zero values when possible, use constructors for complex setup
- Prefer struct embedding over inheritance-like patterns
- Use go fmt and go vet as part of development workflow

# CONCURRENT PROGRAMMING PATTERNS:
- Worker pool pattern for controlled concurrency
- Producer-consumer with buffered channels
- Fan-in/fan-out patterns for parallel processing
- Pipeline patterns with channel composition
- Use select statement for non-blocking channel operations
- Implement circuit breaker patterns for fault tolerance
- Use atomic operations for simple shared counters
- Prefer channels over shared memory for communication
- Implement proper backpressure mechanisms""",

            "rust": """
# RUST-SPECIFIC ANALYSIS POINTS:

# MEMORY SAFETY & SECURITY:
- Unsafe block usage: Every unsafe block must have a comment explaining why it's safe
- FFI boundary safety: Validate C interface contracts, handle null pointers
- Data race prevention: Use Arc<Mutex<T>> or Arc<RwLock<T>> for shared mutable state
- Serialization security: Validate deserialized data, use serde_derive carefully
- Input validation: Use strong typing and validation libraries like validator
- Cryptographic safety: Use audited crates like ring, sodiumoxide, or rustcrypto
- SQL injection prevention: Use sqlx compile-time checked queries or diesel ORM

# OWNERSHIP & BORROWING MASTERY:
- Understand when to use owned values (String, Vec<T>) vs references (&str, &[T])
- Avoid unnecessary cloning - prefer borrowing when possible
- Use Cow<str> for functions that might need to modify strings
- Implement proper lifetime annotations for structs with references
- Use lifetime elision rules effectively to reduce annotation noise
- Understand interior mutability patterns: Cell<T>, RefCell<T>, Mutex<T>
- Use Rc<T> for single-threaded shared ownership, Arc<T> for multi-threaded
- Master the borrow checker: understand when borrows end and how to restructure code
- Use RAII patterns with Drop trait for automatic resource cleanup
- Prefer move semantics for expensive operations

# PERFORMANCE OPTIMIZATION:
- Iterator chains are zero-cost abstractions - prefer them over manual loops
- Use Vec::with_capacity() when final size is known
- Prefer &str over String for read-only string operations
- Use appropriate collection types: Vec, VecDeque, LinkedList, HashMap, BTreeMap
- Minimize allocations in hot paths
- Use const generics and const fn for compile-time optimizations
- Profile with cargo flamegraph and criterion for benchmarking
- Consider using SIMD with portable_simd or explicit intrinsics
- Use #[inline] judiciously for performance-critical small functions

# IDIOMATIC RUST PATTERNS:
- Comprehensive error handling with Result<T, E> and custom error types
- Use ? operator for error propagation
- Implement Display and Debug traits appropriately
- Use pattern matching exhaustively with match statements
- Design traits for common behavior, implement for your types
- Use associated types vs generic parameters appropriately
- Follow Rust naming conventions (snake_case, CamelCase)
- Write comprehensive unit tests with #[cfg(test)]
- Use cargo clippy for additional linting and suggestions
- Document public APIs with /// comments and examples

# ADVANCED PATTERNS & ARCHITECTURE:
- Builder pattern with typestate for compile-time validation
- State machines using enums and pattern matching
- Plugin systems using trait objects (dyn Trait)
- Async programming: understand Send + Sync bounds for async fn
- Error handling strategies: use thiserror for library errors, anyhow for applications
- Generic programming: use where clauses for complex bounds
- Macro programming: declarative macros (macro_rules!) vs procedural macros
- Module system: use pub(crate), pub(super) for controlled visibility
- Dependency injection using traits and generics""",

            "php": """
# PHP-SPECIFIC ANALYSIS POINTS:

# CRITICAL INJECTION VULNERABILITIES:
- SQL injection: ALWAYS use prepared statements with PDO or mysqli
- Cross-site scripting (XSS): Use htmlspecialchars() with ENT_QUOTES | ENT_HTML5
- Command injection: Avoid exec(), shell_exec(), system() with user input
- File inclusion (LFI/RFI): Validate file paths, use allowlists, avoid include with user input
- LDAP injection: Use ldap_escape() for LDAP queries
- XML injection: Use DOMDocument with proper validation
- Header injection: Validate headers before using header() function
- Session fixation: Use session_regenerate_id() after authentication
- Directory traversal: Use realpath() and validate paths against basedir

# SECURITY BEST PRACTICES:
- Password security: Use password_hash() with PASSWORD_DEFAULT, password_verify()
- CSRF protection: Implement token-based CSRF protection
- Session security: Set secure, httponly, samesite cookie flags
- Input validation: Use filter_var() with appropriate filters
- Output encoding: Context-aware output encoding (HTML, JS, CSS, URL)
- File upload security: Validate file types, scan for malware, store outside web root
- Authentication: Implement proper session management and timeout
- Authorization: Use role-based access control (RBAC)
- Error handling: Don't expose sensitive information in error messages
- Cryptography: Use random_bytes() for cryptographically secure random data

# PERFORMANCE & SCALABILITY:
- Database optimization: Avoid N+1 queries, use eager loading, proper indexing
- Caching strategies: Implement Redis/Memcached, use APCu for opcode caching
- Memory management: Unset large variables, avoid memory leaks in loops
- String operations: Use implode() instead of concatenation in loops
- Array performance: Use array functions (array_map, array_filter) over loops
- File I/O: Use appropriate stream contexts, batch operations
- HTTP requests: Use cURL with connection pooling
- Database connections: Use connection pooling, persistent connections wisely
- Profile with Xdebug or Blackfire to identify bottlenecks

# MODERN PHP PRACTICES:
- Type declarations: Use strict types (declare(strict_types=1))
- Return type declarations: Specify return types for all functions
- Nullable types: Use ?Type for optional parameters
- Union types (PHP 8+): Use Type1|Type2 for multiple accepted types
- Named arguments (PHP 8+): Use for better code readability
- Attributes (PHP 8+): Use instead of docblock annotations
- Match expressions (PHP 8+): Use instead of switch for value matching
- Constructor property promotion (PHP 8+): Simplify constructor declarations
- Error handling: Use typed exceptions, implement proper exception hierarchy
- PSR compliance: Follow PSR-1, PSR-2, PSR-4 standards

# ARCHITECTURAL PATTERNS:
- Dependency injection: Use PSR-11 compatible containers
- Repository pattern: Separate data access logic from business logic
- Factory pattern: Create objects without specifying exact classes
- Observer pattern: Implement event-driven architecture
- Middleware pattern: Chain request/response processing
- Service layer pattern: Encapsulate business logic
- Value objects: Use for domain modeling and validation
- Command pattern: Implement for complex operations and undo functionality
- Strategy pattern: Implement different algorithms interchangeably""",

            "ruby": """
# RUBY-SPECIFIC ANALYSIS POINTS:

# CRITICAL SECURITY VULNERABILITIES:
- SQL injection: Use ActiveRecord's parameterized queries, avoid raw SQL with interpolation
- Mass assignment: Use strong parameters with permit() method in Rails
- Cross-site scripting (XSS): Use rails_html_sanitizer, avoid raw() and html_safe()
- Command injection: Avoid system(), exec(), and backticks with user input
- YAML deserialization: Use safe_load() instead of load() for untrusted YAML
- Session hijacking: Use secure session configuration, regenerate session IDs
- CSRF attacks: Enable protect_from_forgery in Rails controllers
- Regular expression DoS (ReDoS): Avoid complex regex with user input
- File upload vulnerabilities: Validate file types, use carrierwave or shrine securely

# METAPROGRAMMING SAFETY:
- eval() usage: Avoid eval() with user input - extreme code injection risk
- class_eval/instance_eval: Use only with trusted code, prefer define_method
- const_set/const_get: Validate constant names to prevent constant pollution
- send/public_send: Use public_send to respect method visibility
- method_missing: Always implement respond_to_missing? alongside method_missing
- define_method vs def: Use define_method for dynamic method creation
- Module inclusion: Be careful with prepend vs include vs extend semantics
- Monkey patching: Use refinements instead of global monkey patches when possible
- Dynamic class creation: Use Class.new carefully, prefer explicit class definitions
- Hook methods: Understand inherited, included, extended hook execution order

# PERFORMANCE OPTIMIZATION:
- N+1 query elimination: Use includes(), preload(), eager_load() appropriately
- Database query optimization: Use select() to limit columns, use exists? vs present?
- Memory efficiency: Use Symbol over String for hash keys, avoid String duplication
- Enumerable performance: Use lazy enumerators for large datasets
- String operations: Use String#<< for concatenation in loops, prefer interpolation
- Block vs Proc vs Lambda: Understand performance implications and use appropriately
- Caching strategies: Use Rails.cache, implement fragment caching, use counter_cache
- Background processing: Use Sidekiq, Resque, or delayed_job for heavy operations
- Garbage collection tuning: Configure RUBY_GC_HEAP_GROWTH_FACTOR appropriately

# IDIOMATIC RUBY PRACTICES:
- Ruby style guide: Follow community style guide (RuboCop configuration)
- Method naming: Use snake_case, predicate methods end with ?, mutating methods with !
- Class design: Prefer composition over inheritance, use modules for shared behavior
- Exception handling: Use specific exception classes, avoid rescuing StandardError broadly
- Block usage: Prefer block_given? over checking block presence
- Truthiness: Understand nil and false are falsy, everything else is truthy
- Constants: Use SCREAMING_SNAKE_CASE, understand constant lookup rules
- Method visibility: Use private, protected, public appropriately
- Duck typing: Design for interfaces, not implementation
- Functional patterns: Use map, select, reject over manual iterations

# ARCHITECTURAL PATTERNS:
- Service objects: Extract complex business logic into service classes
- Form objects: Use for complex form handling and validation
- Policy objects: Implement authorization logic with pundit or cancancan
- Decorator pattern: Use draper for view-layer logic
- Observer pattern: Use ActiveSupport::Notifications for event handling
- Repository pattern: Abstract data access behind repository interfaces
- Command pattern: Implement for complex operations with rollback capability
- Factory pattern: Use for object creation with complex setup
- Concern pattern: Use ActiveSupport::Concern for shared module functionality""",
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
        is_c = any(keyword in code_lower for keyword in ['#include', 'int main', 'malloc', 'free', 'printf', 'scanf'])
        is_go = any(keyword in code_lower for keyword in ['package main', 'func ', 'go ', 'goroutine', 'channel', 'import ('])
        is_rust = any(keyword in code_lower for keyword in ['fn ', 'let mut', 'match ', 'impl ', 'trait ', 'use std::'])
        is_php = any(keyword in code_lower for keyword in ['<?php', '$_', 'function ', 'class ', 'namespace', 'mysqli_'])
        is_ruby = any(keyword in code_lower for keyword in ['def ', 'class ', 'module ', 'require ', '@', 'do |', 'end'])
        
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
        
        # C-SPECIFIC ANALYSIS
        elif is_c:
            if "malloc(" in code_lower and "free(" not in code_lower:
                bugs.append("CRITICAL: Memory leak detected - malloc() without corresponding free(). Always free allocated memory.")
                score -= 3
                
            if "strcpy(" in code_lower or "strcat(" in code_lower:
                security.append("HIGH: Buffer overflow risk - strcpy/strcat are unsafe. Use strncpy/strncat with size limits.")
                score -= 2
                
            if "scanf(" in code_lower and "%s" in code:
                security.append("CRITICAL: Buffer overflow vulnerability - scanf with %s can overflow buffer. Use fgets() instead.")
                score -= 3
                
            if "printf(" in code_lower and "%" in code and ("user" in code_lower or "input" in code_lower):
                security.append("HIGH: Format string vulnerability - user input in printf format string. Use puts() or validate input.")
                score -= 2
                
            if "for" in code_lower and "<=" in code and ("malloc" in code_lower or "array" in code_lower):
                bugs.append("Potential off-by-one error - check array bounds carefully to avoid buffer overflow.")
                
        # GO-SPECIFIC ANALYSIS
        elif is_go:
            if "go func(" in code_lower and "wg.done" not in code_lower and "channel" not in code_lower:
                bugs.append("Goroutine leak risk - ensure goroutines have proper termination mechanism (WaitGroup or channels).")
                
            if "fmt.sprintf" in code_lower and ("input" in code_lower or "request" in code_lower):
                security.append("XSS risk in web handlers - sanitize user input before rendering in HTML responses.")
                
            if "err != nil" not in code_lower and ("file" in code_lower or "http" in code_lower or "sql" in code_lower):
                bugs.append("Missing error handling - Go functions return errors that should be checked.")
                
            if "for range" in code_lower and "go " in code_lower:
                performance.append("Consider using worker pools instead of spawning unlimited goroutines in loops.")
                
        # RUST-SPECIFIC ANALYSIS
        elif is_rust:
            if "unsafe" in code_lower:
                security.append("CRITICAL: Unsafe block detected - justify necessity and ensure memory safety invariants are maintained.")
                score -= 2
                
            if "unwrap()" in code_lower:
                bugs.append("Panic risk - avoid unwrap() in production code. Use match, if let, or expect() with descriptive messages.")
                
            if "clone()" in code_lower and ("vec" in code_lower or "string" in code_lower):
                performance.append("Unnecessary cloning detected - consider borrowing (&) instead of cloning for better performance.")
                
            if "vec![" in code_lower and "with_capacity" not in code_lower:
                performance.append("Consider using Vec::with_capacity() when you know the size to avoid reallocations.")
                
        # PHP-SPECIFIC ANALYSIS
        elif is_php:
            if ("$_get" in code_lower or "$_post" in code_lower) and "filter_" not in code_lower and "htmlspecialchars" not in code_lower:
                security.append("CRITICAL: XSS vulnerability - sanitize user input from $_GET/$_POST before output.")
                score -= 3
                
            if ("select * from" in code_lower or "insert into" in code_lower) and "prepare" not in code_lower:
                security.append("CRITICAL: SQL injection vulnerability - use prepared statements instead of string concatenation.")
                score -= 3
                
            if ("password" in code_lower and "==" in code) or ("password_verify" not in code_lower and "password" in code_lower):
                security.append("HIGH: Insecure password handling - use password_hash() and password_verify() functions.")
                score -= 2
                
            if "foreach" in code_lower and "sql" in code_lower and "where" in code_lower:
                performance.append("N+1 query problem detected - consider using JOINs or batch queries to reduce database calls.")
                
        # RUBY-SPECIFIC ANALYSIS
        elif is_ruby:
            if ".new(params)" in code_lower and "permit" not in code_lower:
                security.append("CRITICAL: Mass assignment vulnerability - use strong parameters with permit() method.")
                score -= 3
                
            if "user.all." in code_lower and "includes" not in code_lower and "joins" not in code_lower:
                performance.append("N+1 query problem - use includes() or joins() to avoid multiple database queries.")
                
            if "/" in code and "users.length" in code_lower and "zero?" not in code_lower:
                bugs.append("Division by zero risk - check for empty collections before division operations.")
                
            if "system(" in code_lower or "exec(" in code_lower:
                security.append("HIGH: Command injection risk - sanitize input before system calls or use safer alternatives.")
                score -= 2
                
            if "@users.each" in code and "return" in code_lower:
                bugs.append("Method may not return expected value - each block doesn't affect method return value.")
        
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
            
            # Only suggest TypeScript for complex functions or existing projects
            if len(lines) > 15 and is_javascript and not any("TypeScript" in item for item in quality):
                quality.append("For larger codebases like this, consider migrating to TypeScript for better type safety and IDE support.")
                
            # Focus on immediate improvements for small functions
            if len(lines) <= 10 and "function" in code_lower:
                if "/**" not in code and "@param" not in code:
                    quality.append("Add JSDoc comments to document function parameters, return value, and purpose for better code maintainability.")
                if "(" in code and ")" in code and "if" not in code_lower:
                    quality.append("Consider adding input validation to ensure function parameters meet expected criteria.")
            elif len(lines) > 10:
                quality.append("For larger functions, consider: 1) Adding comprehensive unit tests, 2) Breaking into smaller, focused functions, 3) Using modern ES6+ features.")
                
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
            
        # Adjust score based on actual issues found (not positive feedback)
        # Count real issues vs positive feedback messages
        real_security_issues = [s for s in security if not any(phrase in s.lower() for phrase in ['complete', 'appears', 'no significant', 'continue following'])]
        real_bugs = [b for b in bugs if not any(phrase in b.lower() for phrase in ['appears sound', 'no significant', 'structure appears'])]
        real_quality_issues = [q for q in quality if not any(phrase in q.lower() for phrase in ['clean and readable', 'ready for', 'structure is'])]
        
        # Only penalize for actual issues, not suggestions or positive feedback
        if real_security_issues:
            # Critical security issues get harsh penalty
            critical_security = any(word in ' '.join(real_security_issues).lower() for word in ['injection', 'xss', 'eval', 'credentials'])
            if critical_security:
                score = min(score, 3)
            else:
                score = min(score, 6)  # Less harsh for minor security issues
        
        if real_bugs:
            # Critical bugs get penalty
            critical_bugs = any(word in ' '.join(real_bugs).lower() for word in ['crash', 'fatal', 'division by zero'])
            if critical_bugs:
                score = min(score, 4)
            else:
                score = min(score, 7)  # Less harsh for minor bugs
        
        # Quality suggestions shouldn't heavily penalize clean code
        if len(real_quality_issues) > 5:  # Only penalize if many real quality issues
            score -= 1
            
        # Ensure score is within bounds
        score = max(1, min(10, score))
        
        # Ensure we always provide constructive educational feedback
        if not bugs:
            bugs = ["Code structure appears sound with no significant logical issues identified."]
            
        if not security:
            if is_javascript:
                security = ["Security analysis complete - no significant issues found. Consider implementing Content Security Policy (CSP) and input sanitization as defensive measures."]
            else:
                security = ["Security analysis complete - no significant issues found. Continue following secure coding practices and principle of least privilege."]
        
        if not performance:
            if is_javascript:
                performance = ["Performance analysis complete - no significant issues found. For production optimization, consider: code minification, lazy loading, and performance monitoring."]
            elif is_python:
                performance = ["Performance analysis complete - no significant issues found. For production optimization, consider: caching strategies, async operations, and profiling tools."]
            else:
                performance = ["Performance analysis complete - no significant issues found. Consider profiling for optimization opportunities and scalability planning."]
        
        if not quality:
            quality = ["Code structure is clean and readable. Ready for professional enhancement through documentation, testing, and modular organization."]
        
        # Smart filtering based on code complexity
        lines = code.strip().split('\n')
        is_simple_function = len(lines) <= 10
        
        if is_simple_function:
            # For simple functions, prioritize actionable feedback and limit to 2-3 suggestions
            priority_keywords = ['JSDoc', 'input validation', 'error handling', 'parameter', 'documentation']
            
            # Filter quality suggestions to prioritize actionable ones
            actionable_quality = []
            generic_quality = []
            
            for suggestion in quality:
                if any(keyword.lower() in suggestion.lower() for keyword in priority_keywords):
                    actionable_quality.append(suggestion)
                else:
                    generic_quality.append(suggestion)
            
            # For simple functions: max 2-3 actionable suggestions, avoid generic ones
            quality = (actionable_quality[:3] + generic_quality[:0]) if actionable_quality else quality[:2]
            
            # Simplify performance suggestions for simple functions
            if performance and len(performance) > 1:
                performance = [p for p in performance if 'monitoring' not in p.lower() or 'minification' not in p.lower()][:1]
        else:
            # For complex functions, allow more suggestions but still limit them
            quality = quality[:5]
            performance = performance[:3]
        
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
        
        # Extract data from AI response with proper initialization
        bugs = ai_data.get("bugs", [])
        security_issues = ai_data.get("security", [])
        performance_issues = ai_data.get("performance", [])
        quality_issues = ai_data.get("quality", [])
        score = ai_data.get("score", 5)
        summary_text = ai_data.get("summary", "Analysis completed.")
        
        logger.info(f"Processing bugs: {bugs}, security: {security_issues}, performance: {performance_issues}, quality: {quality_issues}")
        
        # Initialize variables before processing
        issues = []
        i = 0
        bug = ""
        severity = IssueSeverity.LOW
        issue = None
        
        # Process bugs with proper impact-based severity detection in try-catch
        try:
            for i, bug in enumerate(bugs):
                if isinstance(bug, str) and len(bug.strip()) > 1:  # Avoid single characters
                    severity = self._classify_bug_severity(bug)  # Use proper classification
                        
                    issue = CodeIssue(
                        id=f"bug_{uuid.uuid4().hex[:8]}",
                        type=IssueType.BUG,
                        severity=severity,
                        title=f"Critical Division by Zero" if 'division' in bug.lower() else f"Bug #{i+1}",
                        description=bug,
                        suggestion="Fix this bug to prevent unexpected behavior.",
                        line_number=None,
                        column_number=None,
                        code_snippet=None,
                        explanation=None,
                        confidence=0.8
                    )
                    issues.append(issue.model_dump())  # Convert to dictionary
        except NameError as e:
            logger.error(f"NameError in bug processing loop: {str(e)}. Variables - i: {i}, bug: {bug}, severity: {severity}")
            # Add a fallback issue to indicate the error
            fallback_issue = CodeIssue(
                id=f"bug_error_{uuid.uuid4().hex[:8]}",
                type=IssueType.BUG,
                severity=IssueSeverity.LOW,
                title="Bug Processing Error",
                description=f"Error processing bug analysis: {str(e)}",
                suggestion="Review the bug detection logic for variable initialization issues.",
                line_number=None,
                column_number=None,
                code_snippet=None,
                explanation=None,
                confidence=0.5
            )
            issues.append(fallback_issue.model_dump())
        except Exception as e:
            logger.error(f"Unexpected error in bug processing loop: {str(e)}")
            # Add a fallback issue to indicate the error
            fallback_issue = CodeIssue(
                id=f"bug_error_{uuid.uuid4().hex[:8]}",
                type=IssueType.BUG,
                severity=IssueSeverity.LOW,
                title="Bug Processing Error",
                description=f"Unexpected error processing bug analysis: {str(e)}",
                suggestion="Review the bug detection logic for potential issues.",
                line_number=None,
                column_number=None,
                code_snippet=None,
                explanation=None,
                confidence=0.5
            )
            issues.append(fallback_issue.model_dump())

        # Process security issues with proper impact-based classification
        for i, issue in enumerate(security_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                severity = self._classify_security_severity(issue)  # Use proper classification
                    
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
                issues.append(issue_obj.model_dump())  # Convert to dictionary
                
        # Process performance issues with proper impact-based classification
        for i, issue in enumerate(performance_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                severity = self._classify_performance_severity(issue)  # Use proper classification
                issue_obj = CodeIssue(
                    id=f"perf_{uuid.uuid4().hex[:8]}",
                    type=IssueType.PERFORMANCE,
                    severity=severity,
                    title=f"Performance Improvement #{i+1}",
                    description=issue,
                    suggestion="Consider this optimization for better performance.",
                    line_number=None,
                    column_number=None,
                    code_snippet=None,
                    explanation=None,
                    confidence=0.7
                )
                issues.append(issue_obj.model_dump())  # Convert to dictionary
        
        # Process quality issues with proper classification
        for i, issue in enumerate(quality_issues):
            if isinstance(issue, str) and len(issue.strip()) > 1:
                severity = self._classify_quality_severity(issue)  # Use proper classification
                issue_obj = CodeIssue(
                    id=f"quality_{uuid.uuid4().hex[:8]}",
                    type=IssueType.STYLE,
                    severity=severity,
                    title=f"Code Quality Suggestion #{i+1}",
                    description=issue,
                    suggestion="Improve code quality and maintainability.",
                    line_number=None,
                    column_number=None,
                    code_snippet=None,
                    explanation=None,
                    confidence=0.7
                )
                issues.append(issue_obj.model_dump())  # Convert to dictionary
        
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
            "metrics": metrics.model_dump(),  # Convert to dictionary
            "summary": summary.model_dump(),  # Convert to dictionary
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
            "issues": [fallback_issue.model_dump()],
            "metrics": metrics.model_dump(),
            "summary": summary.model_dump(),
            "suggestions": ["Try again with a smaller code sample."]
        }
    
    async def _cleanup_after_analysis(self):
        """Perform memory cleanup after AI analysis completion"""
        current_time = time.time()
        
        # Only cleanup if enough time has passed to avoid excessive cleanup
        if current_time - self.last_cleanup_time < self.cleanup_interval:
            return
            
        try:
            logger.debug("Performing post-analysis memory cleanup")
            
            # Reduce aggressive garbage collection - only run occasionally
            current_time = time.time()
            if not hasattr(self, '_last_gc_time'):
                self._last_gc_time = 0
                
            # Only run GC every 30 seconds to reduce overhead
            if current_time - self._last_gc_time > 30:
                collected = gc.collect()
                self._last_gc_time = current_time
                if collected > 0:
                    logger.debug(f"Garbage collected {collected} objects after AI analysis")
            
            # Reduce memory pressure checks - only check every 60 seconds
            if not hasattr(self, '_last_memory_check'):
                self._last_memory_check = 0
                
            if current_time - self._last_memory_check > 60:
                try:
                    import psutil
                    memory_percent = psutil.virtual_memory().percent
                    self._last_memory_check = current_time
                    if memory_percent > 95:  # Only unload at 95% instead of 90%
                        logger.warning(f"High memory usage {memory_percent:.1f}%, considering model unload")
                        await self._unload_model_if_needed()
                except ImportError:
                    pass  # psutil not available
                
            self.last_cleanup_time = current_time
            
        except Exception as e:
            logger.error(f"Error during post-analysis cleanup: {e}")
    
    async def _unload_model_if_needed(self):
        """Unload model if memory pressure is too high"""
        if self.model_loaded and self.model is not None:
            try:
                logger.warning("Unloading AI model due to high memory pressure")
                self.model = None
                self.model_loaded = False
                # Force garbage collection after model unload
                gc.collect()
                logger.info("AI model unloaded successfully")
            except Exception as e:
                logger.error(f"Error unloading model: {e}")
    
    def _classify_bug_severity(self, bug_description: str) -> IssueSeverity:
        """
        Classify bug severity based on actual functionality impact.
        CRITICAL = breaks functionality, crashes, data loss
        HIGH = significant logic errors, incorrect behavior
        MEDIUM = edge cases, minor logic issues
        LOW = style suggestions, minor improvements
        """
        bug_lower = bug_description.lower()
        
        # CRITICAL: Functionality-breaking bugs
        critical_indicators = [
            'crash', 'fatal', 'segfault', 'core dump', 'infinite loop', 'deadlock',
            'division by zero', '/0', 'null pointer', 'memory leak', 'buffer overflow',
            'stack overflow', 'data corruption', 'undefined behavior', 'breaks functionality'
        ]
        
        if any(indicator in bug_lower for indicator in critical_indicators):
            return IssueSeverity.CRITICAL
            
        # HIGH: Significant logic errors
        high_indicators = [
            'logic error', 'incorrect result', 'wrong calculation', 'fails to execute',
            'exception not handled', 'resource leak', 'race condition', 'thread safety'
        ]
        
        if any(indicator in bug_lower for indicator in high_indicators):
            return IssueSeverity.HIGH
            
        # MEDIUM: Minor issues that could cause problems
        medium_indicators = [
            'edge case', 'potential issue', 'may fail', 'could cause', 'might result'
        ]
        
        if any(indicator in bug_lower for indicator in medium_indicators):
            return IssueSeverity.MEDIUM
            
        # LOW: Everything else (suggestions, improvements)
        return IssueSeverity.LOW
    
    def _classify_security_severity(self, security_description: str) -> IssueSeverity:
        """
        Classify security severity based on actual vulnerability impact.
        CRITICAL = Remote code execution, privilege escalation
        HIGH = Data exposure, authentication bypass
        MEDIUM = Information disclosure, DoS potential
        LOW = Security best practices, hardening suggestions
        """
        security_lower = security_description.lower()
        
        # CRITICAL: Arbitrary code execution, system compromise
        critical_indicators = [
            'remote code execution', 'arbitrary code', 'code injection', 'eval(',
            'exec(', 'privilege escalation', 'root access', 'admin access',
            'sql injection', 'command injection', 'deserialization'
        ]
        
        if any(indicator in security_lower for indicator in critical_indicators):
            return IssueSeverity.CRITICAL
            
        # HIGH: Data exposure, authentication issues
        high_indicators = [
            'xss', 'cross-site scripting', 'csrf', 'authentication bypass',
            'authorization bypass', 'data exposure', 'sensitive data',
            'password', 'credentials', 'api key', 'token exposure',
            'path traversal', 'directory traversal'
        ]
        
        if any(indicator in security_lower for indicator in high_indicators):
            return IssueSeverity.HIGH
            
        # MEDIUM: Information disclosure, DoS
        medium_indicators = [
            'information disclosure', 'denial of service', 'dos', 'timing attack',
            'weak encryption', 'insecure hash', 'session fixation'
        ]
        
        if any(indicator in security_lower for indicator in medium_indicators):
            return IssueSeverity.MEDIUM
            
        # LOW: Best practices, suggestions
        return IssueSeverity.LOW
    
    def _classify_performance_severity(self, performance_description: str) -> IssueSeverity:
        """
        Classify performance severity based on actual impact.
        CRITICAL = System failure, DoS potential
        HIGH = Severe performance degradation
        MEDIUM = Noticeable performance impact
        LOW = Minor optimizations, best practices
        """
        perf_lower = performance_description.lower()
        
        # CRITICAL: System-breaking performance issues
        critical_indicators = [
            'infinite loop', 'exponential complexity', 'memory exhaustion',
            'cpu exhaustion', 'system overload', 'denial of service'
        ]
        
        if any(indicator in perf_lower for indicator in critical_indicators):
            return IssueSeverity.CRITICAL
            
        # HIGH: Severe performance degradation
        high_indicators = [
            'o(n²)', 'quadratic', 'o(n³)', 'cubic', 'blocking operation',
            'synchronous i/o', 'large memory usage', 'significant slowdown'
        ]
        
        if any(indicator in perf_lower for indicator in high_indicators):
            return IssueSeverity.HIGH
            
        # MEDIUM: Noticeable impact
        medium_indicators = [
            'inefficient', 'repeated computation', 'unnecessary loops',
            'database query in loop', 'n+1 query', 'missing index'
        ]
        
        if any(indicator in perf_lower for indicator in medium_indicators):
            return IssueSeverity.MEDIUM
            
        # LOW: Minor optimizations
        return IssueSeverity.LOW
    
    def _classify_quality_severity(self, quality_description: str) -> IssueSeverity:
        """
        Classify code quality severity - these should mostly be LOW.
        CRITICAL = Never for quality issues
        HIGH = Code that makes maintenance dangerous
        MEDIUM = Code that significantly hurts maintainability  
        LOW = Style, documentation, best practices
        """
        quality_lower = quality_description.lower()
        
        # HIGH: Dangerous maintenance issues (rare for quality)
        high_indicators = [
            'complex nested', 'unreadable code', 'magic numbers in critical',
            'no error handling in critical', 'dangerous pattern'
        ]
        
        if any(indicator in quality_lower for indicator in high_indicators):
            return IssueSeverity.HIGH
            
        # MEDIUM: Significant maintainability issues
        medium_indicators = [
            'very long function', 'deeply nested', 'complex logic',
            'difficult to understand', 'hard to maintain'
        ]
        
        if any(indicator in quality_lower for indicator in medium_indicators):
            return IssueSeverity.MEDIUM
            
        # LOW: Style, documentation, best practices (default for quality)
        return IssueSeverity.LOW

    def _is_circuit_breaker_open(self) -> bool:
        """Check if the AI service circuit breaker is open."""
        if self.ai_failure_count < self.ai_failure_threshold:
            return False
        
        # Check if recovery time has passed
        if time.time() - self.ai_last_failure > self.ai_recovery_time:
            logger.info("Circuit breaker recovery time passed, resetting failure count")
            self.ai_failure_count = 0
            return False
        
        return True
    
    def _record_ai_failure(self):
        """Record an AI service failure for circuit breaker tracking."""
        self.ai_failure_count += 1
        self.ai_last_failure = time.time()
        logger.warning(f"AI service failure recorded. Count: {self.ai_failure_count}/{self.ai_failure_threshold}")
        
        if self.ai_failure_count >= self.ai_failure_threshold:
            logger.error(f"AI service circuit breaker opened after {self.ai_failure_count} failures")
    
    async def _generate_fallback_response(self, request: CodeAnalysisRequest) -> Dict[str, Any]:
        """Generate a fallback response when AI service is unavailable."""
        logger.info("Generating fallback response due to AI service unavailability")
        
        # Use the existing fallback method but adapt for the new interface
        fallback_result = self._generate_fallback_response_sync("AI service temporarily unavailable", request.code)
        
        return fallback_result
    
    def _manage_cache_memory(self, cache_key: str, result: Dict[str, Any]):
        """Manage cache memory usage to prevent memory leaks."""
        import sys
        
        # Estimate memory size of the result
        result_size = sys.getsizeof(str(result))
        
        # Remove old entries if cache is too large
        while (self.cache_size_bytes + result_size > self.cache_memory_limit and 
               len(self.analysis_cache) > 0):
            # Remove oldest entry
            oldest_key = next(iter(self.analysis_cache))
            old_result = self.analysis_cache.pop(oldest_key)
            old_size = sys.getsizeof(str(old_result))
            self.cache_size_bytes -= old_size
            logger.debug(f"Removed cache entry {oldest_key} to free memory")
        
        # Add new entry if within limits
        if len(self.analysis_cache) < self.cache_max_size:
            self.analysis_cache[cache_key] = result
            self.cache_size_bytes += result_size
        else:
            logger.debug("Cache at maximum size, not adding new entry")

    def __del__(self):
        """Cleanup thread pool on destruction"""
        try:
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=False)
        except Exception:
            pass  # Ignore cleanup errors during destruction


# Singleton instance
ai_analyzer = AICodeAnalyzer()