"""
Analysis persistence service for storing and retrieving analysis results.
Handles temporary storage of analysis results to support client reconnection.
"""

from typing import Dict, Any, Optional, List
import json
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
import pickle

logger = logging.getLogger(__name__)

@dataclass
class AnalysisResult:
    """Analysis result with metadata for persistence."""
    analysis_id: str
    client_session_id: str
    client_ip: str
    code_hash: str  # For deduplication
    result_data: Dict[str, Any]
    status: str  # 'pending', 'running', 'completed', 'failed'
    created_at: float
    completed_at: Optional[float] = None
    ttl_seconds: int = 3600  # 1 hour default TTL
    retrieval_count: int = 0
    max_retrievals: int = 10
    
    @property
    def is_expired(self) -> bool:
        """Check if the result has expired."""
        return time.time() > (self.created_at + self.ttl_seconds)
    
    @property
    def is_retrievable(self) -> bool:
        """Check if the result can still be retrieved."""
        return not self.is_expired and self.retrieval_count < self.max_retrievals
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisResult':
        """Create from dictionary."""
        return cls(**data)


class AnalysisPersistenceService:
    """Service for persisting analysis results across client disconnections."""
    
    def __init__(self, storage_dir: str = "analysis_storage", max_storage_size_mb: int = 500):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.max_storage_size_bytes = max_storage_size_mb * 1024 * 1024
        
        # In-memory cache for fast access
        self.results_cache: Dict[str, AnalysisResult] = {}
        self.client_sessions: Dict[str, List[str]] = {}  # session_id -> analysis_ids
        self.client_ip_mapping: Dict[str, str] = {}  # client_id -> ip
        
        # Cleanup management
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
        
        # Thread pool for disk operations
        self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis-persistence")
        
        # Load existing results on startup
        asyncio.create_task(self.load_existing_results())
        
        logger.info(f"🗄️ Analysis persistence service initialized - Storage: {self.storage_dir}")
    
    async def load_existing_results(self):
        """Load existing analysis results from disk on startup."""
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(self.thread_pool, self._load_results_from_disk)
            
            loaded_count = 0
            for result in results:
                if result.is_retrievable:
                    self.results_cache[result.analysis_id] = result
                    self._add_to_client_session(result.client_session_id, result.analysis_id)
                    loaded_count += 1
            
            logger.info(f"📂 Loaded {loaded_count} persistent analysis results")
            
        except Exception as e:
            logger.error(f"❌ Failed to load existing results: {e}")
    
    def _load_results_from_disk(self) -> List[AnalysisResult]:
        """Load results from disk (runs in thread pool)."""
        results = []
        
        for result_file in self.storage_dir.glob("*.json"):
            try:
                with open(result_file, 'r') as f:
                    data = json.load(f)
                    result = AnalysisResult.from_dict(data)
                    results.append(result)
            except Exception as e:
                logger.warning(f"⚠️ Failed to load result file {result_file}: {e}")
                # Clean up corrupted file
                try:
                    result_file.unlink()
                except:
                    pass
        
        return results
    
    def _add_to_client_session(self, session_id: str, analysis_id: str):
        """Add analysis ID to client session tracking."""
        if session_id not in self.client_sessions:
            self.client_sessions[session_id] = []
        if analysis_id not in self.client_sessions[session_id]:
            self.client_sessions[session_id].append(analysis_id)
    
    async def store_analysis_result(
        self, 
        analysis_id: str, 
        client_session_id: str,
        client_ip: str,
        code_hash: str,
        result_data: Dict[str, Any],
        status: str = 'completed',
        ttl_seconds: int = 3600
    ) -> bool:
        """Store analysis result for later retrieval."""
        try:
            # Check if we need cleanup
            await self._cleanup_if_needed()
            
            result = AnalysisResult(
                analysis_id=analysis_id,
                client_session_id=client_session_id,
                client_ip=client_ip,
                code_hash=code_hash,
                result_data=result_data,
                status=status,
                created_at=time.time(),
                completed_at=time.time() if status == 'completed' else None,
                ttl_seconds=ttl_seconds
            )
            
            # Store in memory cache
            self.results_cache[analysis_id] = result
            self._add_to_client_session(client_session_id, analysis_id)
            self.client_ip_mapping[client_session_id] = client_ip
            
            # Store to disk asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.thread_pool, 
                self._save_result_to_disk, 
                result
            )
            
            logger.info(f"💾 Stored analysis result: {analysis_id} for session {client_session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store analysis result {analysis_id}: {e}")
            return False
    
    def _save_result_to_disk(self, result: AnalysisResult):
        """Save result to disk (runs in thread pool)."""
        try:
            result_file = self.storage_dir / f"{result.analysis_id}.json"
            with open(result_file, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save result to disk: {e}")
    
    async def retrieve_analysis_result(
        self, 
        analysis_id: str, 
        client_session_id: Optional[str] = None,
        client_ip: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve analysis result if available and authorized."""
        try:
            result = self.results_cache.get(analysis_id)
            
            if not result:
                logger.debug(f"🔍 Analysis result not found in cache: {analysis_id}")
                return None
            
            # Check if result is still retrievable
            if not result.is_retrievable:
                logger.debug(f"⏰ Analysis result expired or max retrievals exceeded: {analysis_id}")
                await self._remove_result(analysis_id)
                return None
            
            # Verify client authorization
            if client_session_id and result.client_session_id != client_session_id:
                # Check if same IP can access (for session recovery)
                if client_ip and result.client_ip != client_ip:
                    logger.warning(f"🚫 Unauthorized access attempt to analysis {analysis_id}")
                    return None
            
            # Increment retrieval count
            result.retrieval_count += 1
            
            # Update disk storage
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.thread_pool, 
                self._save_result_to_disk, 
                result
            )
            
            logger.info(f"📤 Retrieved analysis result: {analysis_id} (retrieval #{result.retrieval_count})")
            return result.result_data
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve analysis result {analysis_id}: {e}")
            return None
    
    async def get_client_analyses(
        self, 
        client_session_id: str, 
        client_ip: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get all available analysis results for a client session."""
        try:
            analysis_ids = self.client_sessions.get(client_session_id, [])
            
            # Also check for results from same IP if session is different
            if client_ip:
                for session_id, ip in self.client_ip_mapping.items():
                    if ip == client_ip and session_id != client_session_id:
                        analysis_ids.extend(self.client_sessions.get(session_id, []))
            
            # Remove duplicates and limit results
            analysis_ids = list(set(analysis_ids))[-limit:]
            
            results = []
            for analysis_id in analysis_ids:
                result = self.results_cache.get(analysis_id)
                if result and result.is_retrievable:
                    results.append({
                        'analysis_id': analysis_id,
                        'status': result.status,
                        'created_at': result.created_at,
                        'completed_at': result.completed_at,
                        'has_result': result.status == 'completed',
                        'retrieval_count': result.retrieval_count
                    })
            
            # Sort by creation time (newest first)
            results.sort(key=lambda x: x['created_at'], reverse=True)
            
            logger.info(f"📋 Found {len(results)} analysis results for session {client_session_id}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to get client analyses for {client_session_id}: {e}")
            return []
    
    async def update_analysis_status(
        self, 
        analysis_id: str, 
        status: str,
        result_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update analysis status and optionally store result data."""
        try:
            result = self.results_cache.get(analysis_id)
            if not result:
                logger.debug(f"🔍 Analysis not found for status update: {analysis_id}")
                return False
            
            result.status = status
            if status == 'completed' and result_data:
                result.result_data = result_data
                result.completed_at = time.time()
            
            # Update disk storage
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.thread_pool, 
                self._save_result_to_disk, 
                result
            )
            
            logger.info(f"📝 Updated analysis status: {analysis_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update analysis status {analysis_id}: {e}")
            return False
    
    async def _remove_result(self, analysis_id: str):
        """Remove analysis result from cache and disk."""
        try:
            # Remove from cache
            result = self.results_cache.pop(analysis_id, None)
            
            if result:
                # Remove from client session tracking
                if result.client_session_id in self.client_sessions:
                    if analysis_id in self.client_sessions[result.client_session_id]:
                        self.client_sessions[result.client_session_id].remove(analysis_id)
                
                # Remove from disk
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self.thread_pool, 
                    self._remove_result_from_disk, 
                    analysis_id
                )
                
                logger.debug(f"🗑️ Removed analysis result: {analysis_id}")
        
        except Exception as e:
            logger.error(f"❌ Failed to remove analysis result {analysis_id}: {e}")
    
    def _remove_result_from_disk(self, analysis_id: str):
        """Remove result file from disk (runs in thread pool)."""
        try:
            result_file = self.storage_dir / f"{analysis_id}.json"
            if result_file.exists():
                result_file.unlink()
        except Exception as e:
            logger.error(f"❌ Failed to remove result file: {e}")
    
    async def _cleanup_if_needed(self):
        """Perform cleanup if needed based on time and storage limits."""
        current_time = time.time()
        
        # Check if cleanup interval has passed
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        try:
            await self._cleanup_expired_results()
            await self._cleanup_storage_limit()
            self.last_cleanup = current_time
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
    
    async def _cleanup_expired_results(self):
        """Remove expired results."""
        expired_ids = []
        
        for analysis_id, result in self.results_cache.items():
            if result.is_expired:
                expired_ids.append(analysis_id)
        
        for analysis_id in expired_ids:
            await self._remove_result(analysis_id)
        
        if expired_ids:
            logger.info(f"🧹 Cleaned up {len(expired_ids)} expired analysis results")
    
    async def _cleanup_storage_limit(self):
        """Cleanup old results if storage limit is exceeded."""
        try:
            # Calculate current storage size
            total_size = sum(f.stat().st_size for f in self.storage_dir.glob("*.json"))
            
            if total_size <= self.max_storage_size_bytes:
                return
            
            # Sort results by creation time (oldest first)
            sorted_results = sorted(
                self.results_cache.items(), 
                key=lambda x: x[1].created_at
            )
            
            # Remove oldest results until under limit
            removed_count = 0
            for analysis_id, result in sorted_results:
                await self._remove_result(analysis_id)
                removed_count += 1
                
                # Recalculate size
                total_size = sum(f.stat().st_size for f in self.storage_dir.glob("*.json"))
                if total_size <= self.max_storage_size_bytes * 0.8:  # Leave 20% headroom
                    break
            
            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} old analysis results due to storage limit")
        
        except Exception as e:
            logger.error(f"❌ Storage limit cleanup failed: {e}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            total_results = len(self.results_cache)
            total_sessions = len(self.client_sessions)
            
            # Calculate storage size
            total_size = sum(f.stat().st_size for f in self.storage_dir.glob("*.json"))
            
            # Status breakdown
            status_counts = {}
            for result in self.results_cache.values():
                status_counts[result.status] = status_counts.get(result.status, 0) + 1
            
            return {
                'total_results': total_results,
                'total_sessions': total_sessions,
                'storage_size_bytes': total_size,
                'storage_size_mb': round(total_size / 1024 / 1024, 2),
                'storage_limit_mb': self.max_storage_size_bytes / 1024 / 1024,
                'status_counts': status_counts,
                'last_cleanup': self.last_cleanup
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to get storage stats: {e}")
            return {}


# Global instance
analysis_persistence = AnalysisPersistenceService()