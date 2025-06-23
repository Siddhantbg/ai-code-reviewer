"""
API endpoints for analysis result persistence and retrieval.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.services.analysis_persistence import analysis_persistence
from app.models.responses import CodeAnalysisResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["persistence"])


@router.get("/health")
async def persistence_health_check() -> Dict[str, Any]:
    """Health check endpoint for persistence service."""
    try:
        # Test basic functionality
        stats = analysis_persistence.get_storage_stats()
        service_available = True
        message = "Persistence service is operational"
        
        if not stats:
            service_available = False
            message = "Persistence service is degraded but operational"
            
    except Exception as e:
        logger.warning(f"⚠️ Persistence health check failed: {e}")
        service_available = False
        message = f"Persistence service is degraded: {str(e)}"
    
    return {
        "success": True,
        "service": "persistence",
        "status": "healthy" if service_available else "degraded", 
        "available": service_available,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }



@router.post("/analysis/{analysis_id}/check")
async def check_analysis_status(
    analysis_id: str,
    request: Request,
    client_session_id: Optional[str] = Query(None, description="Client session ID for authorization")
) -> Dict[str, Any]:
    """Check if an analysis result is available without retrieving it."""
    try:
        client_ip = request.client.host if request.client else None
        
        # Try to get the result info without incrementing retrieval count
        result = analysis_persistence.results_cache.get(analysis_id)
        
        if not result:
            return {
                "success": True,
                "analysis_id": analysis_id,
                "available": False,
                "status": "not_found",
                "message": "Analysis result not found"
            }
        
        # Check authorization
        if client_session_id and result.client_session_id != client_session_id:
            if client_ip and result.client_ip != client_ip:
                return {
                    "success": True,
                    "analysis_id": analysis_id,
                    "available": False,
                    "status": "unauthorized",
                    "message": "Access denied"
                }
        
        # Check if retrievable
        if not result.is_retrievable:
            return {
                "success": True,
                "analysis_id": analysis_id,
                "available": False,
                "status": "expired",
                "message": "Analysis result expired or max retrievals exceeded"
            }
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "available": True,
            "status": result.status,
            "created_at": result.created_at,
            "completed_at": result.completed_at,
            "retrieval_count": result.retrieval_count,
            "max_retrievals": result.max_retrievals,
            "message": "Analysis result available"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to check analysis status {analysis_id}: {e}")
        # Return safe response instead of 500 error to prevent frontend crashes
        return {
            "success": False,
            "analysis_id": analysis_id,
            "available": False,
            "status": "error",
            "message": f"Failed to check analysis status: {str(e)}",
            "error": str(e)
        }


@router.get("/client/{client_id}/analyses")
async def get_client_analyses(
    client_id: str,
    request: Request,
    limit: Optional[int] = Query(10, ge=1, le=100, description="Maximum number of analyses to return"),
    offset: Optional[int] = Query(0, ge=0, description="Number of analyses to skip")
) -> Dict[str, Any]:
    """Retrieve analysis history for a specific client."""
    try:
        client_ip = request.client.host if request.client else None
        
        # Get all analyses for this client
        analyses = await analysis_persistence.get_client_analyses(
            client_session_id=client_id,
            client_ip=client_ip,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "client_id": client_id,
            "analyses": analyses,
            "count": len(analyses),
            "limit": limit,
            "offset": offset,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get client analyses for {client_id}: {e}")
        # Return empty analyses instead of 500 error to prevent frontend crashes
        return {
            "success": False,
            "error": "Failed to retrieve client analyses",
            "client_id": client_id,
            "analyses": [],
            "count": 0,
            "limit": limit,
            "offset": offset,
            "retrieved_at": datetime.utcnow().isoformat()
        }


@router.get("/analyses/{client_id}")
async def get_analyses_by_id(
    client_id: str,
    request: Request,
    limit: Optional[int] = Query(10, ge=1, le=100, description="Maximum number of analyses to return"),
    offset: Optional[int] = Query(0, ge=0, description="Number of analyses to skip"),
    client_session_id: Optional[str] = Query(None, description="Client session ID for authorization")
) -> Dict[str, Any]:
    """
    Retrieve analyses by ID - handles both client_id and analysis_id for backward compatibility.
    If it looks like an analysis_id (contains dashes), try to get specific analysis.
    Otherwise, treat as client_id and get client analysis history.
    """
    try:
        client_ip = request.client.host if request.client else None
        
        # If the ID looks like an analysis ID (contains timestamp and dashes), try specific analysis first
        if "-" in client_id and len(client_id) > 20:
            # Try to get specific analysis result
            result_data = await analysis_persistence.retrieve_analysis_result(
                analysis_id=client_id,
                client_session_id=client_session_id,
                client_ip=client_ip
            )
            
            if result_data:
                return {
                    "success": True,
                    "analysis_id": client_id,
                    "result": result_data,
                    "retrieved_at": datetime.utcnow().isoformat()
                }
        
        # Treat as client_id and get client analysis history
        analyses = await analysis_persistence.get_client_analyses(
            client_session_id=client_id,
            client_ip=client_ip,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "client_id": client_id,
            "analyses": analyses,
            "count": len(analyses),
            "limit": limit,
            "offset": offset,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get analyses for ID {client_id}: {e}")
        # Return safe response to prevent frontend crashes
        return {
            "success": False,
            "error": "Failed to retrieve analyses",
            "client_id": client_id,
            "analyses": [],
            "count": 0,
            "limit": limit,
            "offset": offset,
            "retrieved_at": datetime.utcnow().isoformat()
        }


@router.get("/stats")
async def get_persistence_stats() -> Dict[str, Any]:
    """Get storage and persistence statistics."""
    try:
        stats = analysis_persistence.get_storage_stats()
        
        # Ensure we always return a valid stats object, even if empty
        if not stats:
            stats = {
                "total_results": 0,
                "total_sessions": 0,
                "storage_size_bytes": 0,
                "storage_size_mb": 0.0,
                "storage_limit_mb": 500,
                "status_counts": {},
                "last_cleanup": 0
            }
        
        return {
            "success": True,
            "stats": stats,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get persistence stats: {e}")
        # Return safe default stats instead of 500 error to prevent frontend crashes
        return {
            "success": False,
            "error": "Failed to retrieve stats",
            "stats": {
                "total_results": 0,
                "total_sessions": 0,
                "storage_size_bytes": 0,
                "storage_size_mb": 0.0,
                "storage_limit_mb": 500,
                "status_counts": {},
                "last_cleanup": 0
            },
            "retrieved_at": datetime.utcnow().isoformat()
        }


@router.delete("/analysis/{analysis_id}")
async def delete_analysis_result(
    analysis_id: str,
    request: Request,
    client_session_id: Optional[str] = Query(None, description="Client session ID for authorization")
) -> Dict[str, Any]:
    """Delete a specific analysis result (if authorized)."""
    try:
        client_ip = request.client.host if request.client else None
        
        # Check if result exists and is authorized
        result = analysis_persistence.results_cache.get(analysis_id)
        
        if not result:
            # Return success even if not found to prevent 404 errors
            return {
                "success": True,
                "analysis_id": analysis_id,
                "message": "Analysis result not found or already deleted",
                "deleted_at": datetime.utcnow().isoformat(),
                "status": "not_found"
            }
        
        # Check authorization
        if client_session_id and result.client_session_id != client_session_id:
            if client_ip and result.client_ip != client_ip:
                # Return success but indicate unauthorized instead of 403 error
                return {
                    "success": False,
                    "analysis_id": analysis_id,
                    "message": "Access denied - insufficient permissions to delete this analysis",
                    "deleted_at": datetime.utcnow().isoformat(),
                    "status": "unauthorized"
                }
        
        # Remove the result
        await analysis_persistence._remove_result(analysis_id)
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "message": "Analysis result deleted successfully",
            "deleted_at": datetime.utcnow().isoformat(),
            "status": "deleted"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to delete analysis result {analysis_id}: {e}")
        # Return safe response instead of 500 error to prevent frontend crashes
        return {
            "success": False,
            "analysis_id": analysis_id,
            "message": f"Failed to delete analysis result: {str(e)}",
            "deleted_at": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(e)
        }


@router.post("/cleanup")
async def trigger_cleanup() -> Dict[str, Any]:
    """Manually trigger cleanup of expired results."""
    try:
        await analysis_persistence._cleanup_expired_results()
        
        return {
            "success": True,
            "message": "Cleanup completed",
            "cleaned_at": datetime.utcnow().isoformat(),
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to trigger cleanup: {e}")
        # Return safe response instead of 500 error to prevent frontend crashes
        return {
            "success": False,
            "message": f"Cleanup failed: {str(e)}",
            "cleaned_at": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(e)
        }