import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Dict, Any, Optional, List, Tuple, Union

import redis.asyncio as redis
from celery import Celery
from celery.result import AsyncResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalysisOptimizer:
    """Service for optimizing code analysis performance through caching and background processing."""
    
    def __init__(self, redis_url: Optional[str] = None, celery_app: Optional[Celery] = None):
        """Initialize the optimizer with Redis connection and Celery app.
        
        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379/0)
            celery_app: Celery application instance
        """
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.redis_client = None
        self.celery_app = celery_app
        self.cache_ttl = 60 * 60 * 24  # 24 hours default TTL
        self.progress_ttl = 60 * 60  # 1 hour TTL for progress tracking
        self.chunk_size = 1000  # Default chunk size in lines
        self.cache_enabled = True
        # Remove _initialize_redis() call
    
    async def _ensure_redis_connection(self):
        if self.redis_client is None and self.cache_enabled:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=0, decode_responses=True
                )
                await asyncio.get_event_loop().run_in_executor(None, self.redis_client.ping)
            except Exception as e:
                self.cache_enabled = False
    
    async def cache_analysis_result(self, code_hash: str, result: dict):
        await self._ensure_redis_connection()
        if not self.cache_enabled:
            return
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.setex, f"analysis:{code_hash}", 3600, json.dumps(result)
            )
        except Exception:
            pass
    
    async def get_cached_result_new(self, code_hash: str):
        await self._ensure_redis_connection()
        if not self.cache_enabled:
            return None
        try:
            cached = await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.get, f"analysis:{code_hash}"
            )
            return json.loads(cached) if cached else None
        except Exception:
            return None
    
    async def get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result.
        
        Args:
            cache_key: Unique key for the cached result
            
        Returns:
            Cached result if found, None otherwise
        """
        if not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(f"analysis:{cache_key}")
            if cached_data:
                logger.info(f"Cache hit for key: {cache_key}")
                return json.loads(cached_data)
            
            logger.info(f"Cache miss for key: {cache_key}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving from cache: {str(e)}")
            return None
    
    async def cache_result(self, cache_key: str, result: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache analysis result.
        
        Args:
            cache_key: Unique key for the cached result
            result: Analysis result to cache
            ttl: Time-to-live in seconds (default: 24 hours)
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            ttl = ttl or self.cache_ttl
            serialized_result = json.dumps(result)
            await self.redis_client.setex(f"analysis:{cache_key}", ttl, serialized_result)
            logger.info(f"Cached result for key: {cache_key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching result: {str(e)}")
            return False
    
    def generate_cache_key(self, code: str, language: str, analysis_type: str, config: Optional[Dict] = None) -> str:
        """Generate a unique cache key based on code content and analysis parameters.
        
        Args:
            code: Source code to analyze
            language: Programming language
            analysis_type: Type of analysis
            config: Analysis configuration
            
        Returns:
            Unique cache key
        """
        # Create a hash of the code content
        code_hash = hashlib.md5(code.encode()).hexdigest()
        
        # Add language and analysis type to the key
        key_parts = [code_hash, language, analysis_type]
        
        # Add config hash if provided
        if config:
            config_str = json.dumps(config, sort_keys=True)
            config_hash = hashlib.md5(config_str.encode()).hexdigest()
            key_parts.append(config_hash)
        
        # Join all parts with a separator
        return "_".join(key_parts)
    
    def chunk_code(self, code: str, chunk_size: Optional[int] = None) -> List[Tuple[int, str]]:
        """Split code into manageable chunks for parallel processing.
        
        Args:
            code: Source code to chunk
            chunk_size: Number of lines per chunk (default: 1000)
            
        Returns:
            List of (start_line, chunk) tuples
        """
        chunk_size = chunk_size or self.chunk_size
        lines = code.split('\n')
        chunks = []
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            chunks.append((i, '\n'.join(chunk_lines)))
        
        return chunks
    
    async def submit_background_job(self, task_name: str, args: List, kwargs: Dict) -> str:
        """Submit a background job to Celery.
        
        Args:
            task_name: Name of the Celery task
            args: Positional arguments for the task
            kwargs: Keyword arguments for the task
            
        Returns:
            Job ID
        """
        if not self.celery_app:
            raise ValueError("Celery app not initialized")
        
        try:
            # Submit task to Celery
            task = self.celery_app.send_task(task_name, args=args, kwargs=kwargs)
            job_id = task.id
            
            # Initialize progress tracking
            await self.set_job_progress(job_id, 0, "Job submitted")
            
            logger.info(f"Submitted background job: {job_id} ({task_name})")
            return job_id
        except Exception as e:
            logger.error(f"Error submitting background job: {str(e)}")
            raise
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a background job.
        
        Args:
            job_id: ID of the background job
            
        Returns:
            Job status information
        """
        if not self.celery_app:
            raise ValueError("Celery app not initialized")
        
        try:
            # Get task result from Celery
            result = AsyncResult(job_id, app=self.celery_app)
            status = result.status
            
            # Get progress from Redis
            progress_data = await self.get_job_progress(job_id)
            
            # Combine status information
            status_info = {
                "job_id": job_id,
                "status": status,
                "progress": progress_data.get("progress", 0),
                "message": progress_data.get("message", ""),
                "result": None,
                "error": None
            }
            
            # Add result or error if available
            if status == "SUCCESS":
                status_info["result"] = result.get()
            elif status == "FAILURE":
                status_info["error"] = str(result.result)
            
            return status_info
        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            return {
                "job_id": job_id,
                "status": "ERROR",
                "progress": 0,
                "message": f"Error retrieving job status: {str(e)}",
                "result": None,
                "error": str(e)
            }
    
    async def set_job_progress(self, job_id: str, progress: float, message: str) -> bool:
        """Set progress for a background job.
        
        Args:
            job_id: ID of the background job
            progress: Progress percentage (0-100)
            message: Progress message
            
        Returns:
            True if progress was set successfully, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            progress_data = {
                "progress": progress,
                "message": message,
                "timestamp": time.time()
            }
            
            serialized_data = json.dumps(progress_data)
            await self.redis_client.setex(f"progress:{job_id}", self.progress_ttl, serialized_data)
            
            logger.debug(f"Updated progress for job {job_id}: {progress}% - {message}")
            return True
        except Exception as e:
            logger.error(f"Error setting job progress: {str(e)}")
            return False
    
    async def get_job_progress(self, job_id: str) -> Dict[str, Any]:
        """Get progress for a background job.
        
        Args:
            job_id: ID of the background job
            
        Returns:
            Progress information
        """
        if not self.redis_client:
            return {"progress": 0, "message": "Redis not available", "timestamp": time.time()}
        
        try:
            progress_data = await self.redis_client.get(f"progress:{job_id}")
            if progress_data:
                return json.loads(progress_data)
            
            return {"progress": 0, "message": "No progress data available", "timestamp": time.time()}
        except Exception as e:
            logger.error(f"Error getting job progress: {str(e)}")
            return {"progress": 0, "message": f"Error: {str(e)}", "timestamp": time.time()}
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a background job.
        
        Args:
            job_id: ID of the background job
            
        Returns:
            True if job was cancelled successfully, False otherwise
        """
        if not self.celery_app:
            raise ValueError("Celery app not initialized")
        
        try:
            # Revoke the task in Celery
            self.celery_app.control.revoke(job_id, terminate=True)
            
            # Update progress to indicate cancellation
            await self.set_job_progress(job_id, 100, "Job cancelled")
            
            logger.info(f"Cancelled job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling job: {str(e)}")
            return False
    
    async def clear_cache(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries matching a pattern.
        
        Args:
            pattern: Redis key pattern to match (default: all analysis cache)
            
        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0
        
        try:
            pattern = pattern or "analysis:*"
            keys = await self.redis_client.keys(pattern)
            
            if not keys:
                return 0
            
            deleted = await self.redis_client.delete(*keys)
            logger.info(f"Cleared {deleted} cache entries matching pattern: {pattern}")
            
            return deleted
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        if not self.redis_client:
            return {"error": "Redis not available"}
        
        try:
            # Get Redis info
            info = await self.redis_client.info()
            
            # Count analysis cache entries
            analysis_keys = await self.redis_client.keys("analysis:*")
            analysis_count = len(analysis_keys)
            
            # Count progress entries
            progress_keys = await self.redis_client.keys("progress:*")
            progress_count = len(progress_keys)
            
            # Calculate total memory usage (approximate)
            memory_used = info.get("used_memory_human", "unknown")
            
            return {
                "total_keys": info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0) / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1)) * 100,
                "analysis_entries": analysis_count,
                "progress_entries": progress_count,
                "memory_used": memory_used
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"error": str(e)}


class AnalysisProgressTracker:
    """Tracks progress of long-running analysis operations."""
    
    def __init__(self, optimizer: AnalysisOptimizer):
        """Initialize the progress tracker.
        
        Args:
            optimizer: AnalysisOptimizer instance for Redis access
        """
        self.optimizer = optimizer
        self.active_jobs = {}
    
    async def create_job(self, job_type: str, metadata: Optional[Dict] = None) -> str:
        """Create a new progress tracking job.
        
        Args:
            job_type: Type of analysis job
            metadata: Additional job metadata
            
        Returns:
            Job ID
        """
        # Generate a unique job ID
        job_id = f"{job_type}_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        
        # Initialize job data
        job_data = {
            "job_id": job_id,
            "job_type": job_type,
            "metadata": metadata or {},
            "start_time": time.time(),
            "end_time": None,
            "status": "created",
            "progress": 0,
            "message": "Job created"
        }
        
        # Store in Redis
        await self.optimizer.redis_client.setex(
            f"job:{job_id}", 
            self.optimizer.progress_ttl, 
            json.dumps(job_data)
        )
        
        # Store in memory for quick access
        self.active_jobs[job_id] = job_data
        
        logger.info(f"Created job: {job_id} ({job_type})")
        return job_id
    
    async def update_progress(self, job_id: str, progress: float, message: str, status: Optional[str] = None) -> bool:
        """Update job progress.
        
        Args:
            job_id: Job ID
            progress: Progress percentage (0-100)
            message: Progress message
            status: Job status (optional)
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Get current job data
            job_data = await self.get_job(job_id)
            if not job_data:
                logger.warning(f"Cannot update progress for unknown job: {job_id}")
                return False
            
            # Update progress
            job_data["progress"] = progress
            job_data["message"] = message
            
            # Update status if provided
            if status:
                job_data["status"] = status
                
                # Set end time if job is complete
                if status in ["completed", "failed", "cancelled"]:
                    job_data["end_time"] = time.time()
            
            # Store updated data in Redis
            await self.optimizer.redis_client.setex(
                f"job:{job_id}", 
                self.optimizer.progress_ttl, 
                json.dumps(job_data)
            )
            
            # Update in-memory cache
            self.active_jobs[job_id] = job_data
            
            # Also update in the progress tracker format for compatibility
            await self.optimizer.set_job_progress(job_id, progress, message)
            
            logger.debug(f"Updated job {job_id}: {progress}% - {message}")
            return True
        except Exception as e:
            logger.error(f"Error updating job progress: {str(e)}")
            return False
    
    async def complete_job(self, job_id: str, result: Optional[Dict] = None, error: Optional[str] = None) -> bool:
        """Mark a job as completed or failed.
        
        Args:
            job_id: Job ID
            result: Job result (for successful jobs)
            error: Error message (for failed jobs)
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Get current job data
            job_data = await self.get_job(job_id)
            if not job_data:
                logger.warning(f"Cannot complete unknown job: {job_id}")
                return False
            
            # Update job status
            if error:
                job_data["status"] = "failed"
                job_data["error"] = error
                job_data["message"] = f"Failed: {error}"
                job_data["progress"] = 100  # Mark as complete even if failed
            else:
                job_data["status"] = "completed"
                job_data["result"] = result
                job_data["message"] = "Job completed successfully"
                job_data["progress"] = 100
            
            job_data["end_time"] = time.time()
            
            # Store updated data in Redis with extended TTL for completed jobs
            await self.optimizer.redis_client.setex(
                f"job:{job_id}", 
                self.optimizer.progress_ttl * 2,  # Keep completed jobs longer
                json.dumps(job_data)
            )
            
            # Update in-memory cache
            self.active_jobs[job_id] = job_data
            
            # Also update in the progress tracker format for compatibility
            await self.optimizer.set_job_progress(
                job_id, 
                100, 
                "Job completed successfully" if not error else f"Failed: {error}"
            )
            
            logger.info(f"Completed job {job_id}: {'Success' if not error else 'Failed'}")
            return True
        except Exception as e:
            logger.error(f"Error completing job: {str(e)}")
            return False
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job information.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job data if found, None otherwise
        """
        # Try in-memory cache first
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        
        try:
            # Get from Redis
            job_data = await self.optimizer.redis_client.get(f"job:{job_id}")
            if job_data:
                job_data = json.loads(job_data)
                # Update in-memory cache
                self.active_jobs[job_id] = job_data
                return job_data
            
            return None
        except Exception as e:
            logger.error(f"Error getting job data: {str(e)}")
            return None
    
    async def list_active_jobs(self, job_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active jobs.
        
        Args:
            job_type: Filter by job type (optional)
            
        Returns:
            List of active jobs
        """
        try:
            # Get all job keys from Redis
            job_keys = await self.optimizer.redis_client.keys("job:*")
            
            jobs = []
            for key in job_keys:
                job_data = await self.optimizer.redis_client.get(key)
                if job_data:
                    job = json.loads(job_data)
                    
                    # Filter by job type if specified
                    if job_type and job.get("job_type") != job_type:
                        continue
                    
                    # Filter out completed jobs older than 1 hour
                    if job.get("status") in ["completed", "failed", "cancelled"]:
                        end_time = job.get("end_time", 0)
                        if time.time() - end_time > 3600:  # 1 hour
                            continue
                    
                    jobs.append(job)
            
            return jobs
        except Exception as e:
            logger.error(f"Error listing active jobs: {str(e)}")
            return []
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            # Get current job data
            job_data = await self.get_job(job_id)
            if not job_data:
                logger.warning(f"Cannot cancel unknown job: {job_id}")
                return False
            
            # Update job status
            job_data["status"] = "cancelled"
            job_data["message"] = "Job cancelled by user"
            job_data["progress"] = 100  # Mark as complete
            job_data["end_time"] = time.time()
            
            # Store updated data in Redis
            await self.optimizer.redis_client.setex(
                f"job:{job_id}", 
                self.optimizer.progress_ttl, 
                json.dumps(job_data)
            )
            
            # Update in-memory cache
            self.active_jobs[job_id] = job_data
            
            # Also update in the progress tracker format for compatibility
            await self.optimizer.set_job_progress(job_id, 100, "Job cancelled by user")
            
            # Try to cancel in Celery if available
            if self.optimizer.celery_app:
                self.optimizer.celery_app.control.revoke(job_id, terminate=True)
            
            logger.info(f"Cancelled job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling job: {str(e)}")
            return False


# Singleton instance
analysis_optimizer = AnalysisOptimizer()
analysis_progress_tracker = AnalysisProgressTracker(analysis_optimizer)