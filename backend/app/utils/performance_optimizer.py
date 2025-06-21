# backend/app/utils/performance_optimizer.py
import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from collections import defaultdict, deque
import weakref
import gc

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """Performance optimization utilities for the backend"""
    
    def __init__(self):
        # Resource limits
        self.max_concurrent_analyses = 5
        self.max_concurrent_ai_operations = 2
        self.max_memory_usage_mb = 2048  # 2GB limit
        self.max_cpu_usage_percent = 90.0
        
        # Semaphores for limiting concurrent operations
        self.analysis_semaphore = asyncio.Semaphore(self.max_concurrent_analyses)
        self.ai_semaphore = asyncio.Semaphore(self.max_concurrent_ai_operations)
        
        # Memory management
        self.memory_cleanup_threshold = 1536  # 1.5GB - trigger cleanup
        self.last_cleanup_time = 0
        self.cleanup_interval = 300  # 5 minutes
        
        # Performance tracking
        self.operation_times = defaultdict(lambda: deque(maxlen=100))
        self.resource_snapshots = deque(maxlen=60)  # 30 minutes at 30s intervals
        
        # Cache for expensive operations
        self.operation_cache = weakref.WeakValueDictionary()
        self.cache_hit_stats = defaultdict(int)
        
        # Circuit breaker state
        self.circuit_breakers = {}
        
    async def limit_concurrent_analyses(self, func: Callable):
        """Decorator to limit concurrent analysis operations"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self.analysis_semaphore:
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    end_time = time.time()
                    self.operation_times['analysis'].append(end_time - start_time)
                    return result
                except Exception as e:
                    logger.error(f"❌ Analysis operation failed: {e}")
                    raise
        return wrapper
        
    async def limit_ai_operations(self, func: Callable):
        """Decorator to limit concurrent AI operations"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self.ai_semaphore:
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    end_time = time.time()
                    self.operation_times['ai_operation'].append(end_time - start_time)
                    return result
                except Exception as e:
                    logger.error(f"❌ AI operation failed: {e}")
                    raise
        return wrapper
        
    async def check_resource_limits(self) -> bool:
        """Check if current resource usage is within limits"""
        try:
            import psutil
            process = psutil.Process()
            
            # Check memory usage
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            if memory_mb > self.max_memory_usage_mb:
                logger.warning(f"⚠️ Memory usage {memory_mb:.1f}MB exceeds limit {self.max_memory_usage_mb}MB")
                await self.emergency_cleanup()
                return False
                
            # Check CPU usage
            cpu_percent = process.cpu_percent(interval=0.1)
            if cpu_percent > self.max_cpu_usage_percent:
                logger.warning(f"⚠️ CPU usage {cpu_percent:.1f}% exceeds limit {self.max_cpu_usage_percent}%")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking resource limits: {e}")
            return True  # Allow operation if we can't check
            
    async def emergency_cleanup(self):
        """Perform emergency memory cleanup"""
        logger.warning("🧹 Performing emergency memory cleanup")
        
        try:
            # Force garbage collection
            collected = gc.collect()
            logger.info(f"Garbage collected {collected} objects")
            
            # Clear operation caches
            self.operation_cache.clear()
            
            # Truncate deques to save memory
            for key in self.operation_times:
                if len(self.operation_times[key]) > 20:
                    # Keep only last 20 entries
                    new_deque = deque(list(self.operation_times[key])[-20:], maxlen=100)
                    self.operation_times[key] = new_deque
                    
            if len(self.resource_snapshots) > 30:
                # Keep only last 30 snapshots
                new_deque = deque(list(self.resource_snapshots)[-30:], maxlen=60)
                self.resource_snapshots = new_deque
                
            self.last_cleanup_time = time.time()
            logger.info("✅ Emergency cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error during emergency cleanup: {e}")
            
    async def periodic_cleanup(self):
        """Perform regular periodic cleanup"""
        current_time = time.time()
        
        if current_time - self.last_cleanup_time < self.cleanup_interval:
            return
            
        logger.debug("🧹 Performing periodic cleanup")
        
        try:
            # Check if cleanup is needed
            should_cleanup = await self._should_perform_cleanup()
            
            if should_cleanup:
                # Gentle garbage collection
                collected = gc.collect(generation=0)  # Only generation 0
                if collected > 0:
                    logger.debug(f"Collected {collected} objects in periodic cleanup")
                    
                # Clean old cache entries
                cache_size_before = len(self.operation_cache)
                # WeakValueDictionary auto-cleans, but we can force it
                list(self.operation_cache.keys())  # Access to trigger cleanup
                cache_size_after = len(self.operation_cache)
                
                if cache_size_before != cache_size_after:
                    logger.debug(f"Cache cleaned: {cache_size_before} -> {cache_size_after} entries")
                    
            self.last_cleanup_time = current_time
            
        except Exception as e:
            logger.error(f"❌ Error during periodic cleanup: {e}")
            
    async def _should_perform_cleanup(self) -> bool:
        """Determine if cleanup should be performed"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            return memory_mb > self.memory_cleanup_threshold
            
        except Exception:
            return False
            
    def get_circuit_breaker(self, operation_name: str, failure_threshold: int = 5, 
                           recovery_timeout: int = 60):
        """Get or create a circuit breaker for an operation"""
        if operation_name not in self.circuit_breakers:
            self.circuit_breakers[operation_name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        return self.circuit_breakers[operation_name]
        
    def cache_operation_result(self, cache_key: str, result: Any, ttl: int = 300):
        """Cache the result of an expensive operation"""
        try:
            # Simple cache with TTL (stored as tuple with expiry time)
            expiry_time = time.time() + ttl
            self.operation_cache[cache_key] = (result, expiry_time)
            self.cache_hit_stats['cache_sets'] += 1
        except Exception as e:
            logger.debug(f"Cache set failed for {cache_key}: {e}")
            
    def get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached result if available and not expired"""
        try:
            if cache_key in self.operation_cache:
                result, expiry_time = self.operation_cache[cache_key]
                if time.time() < expiry_time:
                    self.cache_hit_stats['cache_hits'] += 1
                    return result
                else:
                    # Expired, remove from cache
                    del self.operation_cache[cache_key]
                    self.cache_hit_stats['cache_expired'] += 1
            
            self.cache_hit_stats['cache_misses'] += 1
            return None
            
        except Exception as e:
            logger.debug(f"Cache get failed for {cache_key}: {e}")
            return None
            
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        stats = {
            'timestamp': time.time(),
            'resource_limits': {
                'max_concurrent_analyses': self.max_concurrent_analyses,
                'max_concurrent_ai_operations': self.max_concurrent_ai_operations,
                'max_memory_usage_mb': self.max_memory_usage_mb,
                'max_cpu_usage_percent': self.max_cpu_usage_percent
            },
            'current_usage': {
                'active_analyses': self.max_concurrent_analyses - self.analysis_semaphore._value,
                'active_ai_operations': self.max_concurrent_ai_operations - self.ai_semaphore._value,
                'cache_size': len(self.operation_cache)
            },
            'operation_times': {},
            'cache_stats': dict(self.cache_hit_stats),
            'circuit_breakers': {}
        }
        
        # Calculate operation time statistics
        for operation, times in self.operation_times.items():
            if times:
                times_list = list(times)
                stats['operation_times'][operation] = {
                    'count': len(times_list),
                    'avg_time': sum(times_list) / len(times_list),
                    'min_time': min(times_list),
                    'max_time': max(times_list),
                    'recent_avg': sum(times_list[-10:]) / min(10, len(times_list))
                }
                
        # Circuit breaker states
        for name, breaker in self.circuit_breakers.items():
            stats['circuit_breakers'][name] = {
                'state': breaker.state,
                'failure_count': breaker.failure_count,
                'last_failure_time': breaker.last_failure_time
            }
            
        return stats

class CircuitBreaker:
    """Circuit breaker implementation for failing operations"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = 'closed'  # closed, open, half_open
        
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half_open'
                logger.info(f"Circuit breaker half-open, attempting recovery")
            else:
                raise Exception(f"Circuit breaker is open, operation blocked")
                
        try:
            result = await func(*args, **kwargs)
            
            # Success - reset failure count and close circuit
            if self.state == 'half_open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info(f"Circuit breaker closed, operation recovered")
                
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
                
            raise e

# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()