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

router = APIRouter(prefix="/api/persistence", tags=["persistence"])


@router.get("/analyses/{client_session_id}")
async def get_client_analyses(
    client_session_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return")
) -> Dict[str, Any]:
    """Get all available analysis results for a client session."""
    try:
        client_ip = request.client.host if request.client else None
        
        analyses = await analysis_persistence.get_client_analyses(
            client_session_id=client_session_id,
            client_ip=client_ip,
            limit=limit
        )
        
        return {
            "success": True,
            "session_id": client_session_id,
            "analyses": analyses,
            "count": len(analyses),
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get client analyses for {client_session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve analyses: {str(e)}"
        )


@router.get("/analysis/{analysis_id}")
async def get_analysis_result(
    analysis_id: str,
    request: Request,
    client_session_id: Optional[str] = Query(None, description="Client session ID for authorization")
) -> Dict[str, Any]:
    """Retrieve a specific analysis result."""
    try:
        client_ip = request.client.host if request.client else None
        
        result_data = await analysis_persistence.retrieve_analysis_result(
            analysis_id=analysis_id,
            client_session_id=client_session_id,
            client_ip=client_ip
        )
        
        if not result_data:
            raise HTTPException(
                status_code=404,
                detail="Analysis result not found, expired, or access denied"
            )
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "result": result_data,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get analysis result {analysis_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve analysis result: {str(e)}"
        )


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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check analysis status: {str(e)}"
        )


@router.get("/stats")
async def get_persistence_stats() -> Dict[str, Any]:
    """Get storage and persistence statistics."""
    try:
        stats = analysis_persistence.get_storage_stats()
        
        return {
            "success": True,
            "stats": stats,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get persistence stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve stats: {str(e)}"
        )


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
            raise HTTPException(
                status_code=404,
                detail="Analysis result not found"
            )
        
        # Check authorization
        if client_session_id and result.client_session_id != client_session_id:
            if client_ip and result.client_ip != client_ip:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied"
                )
        
        # Remove the result
        await analysis_persistence._remove_result(analysis_id)
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "message": "Analysis result deleted successfully",
            "deleted_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete analysis result {analysis_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete analysis result: {str(e)}"
        )


@router.post("/cleanup")
async def trigger_cleanup() -> Dict[str, Any]:
    """Manually trigger cleanup of expired results."""
    try:
        await analysis_persistence._cleanup_expired_results()
        
        return {
            "success": True,
            "message": "Cleanup completed",
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to trigger cleanup: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )