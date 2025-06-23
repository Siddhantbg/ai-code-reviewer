#!/usr/bin/env python3
"""
Show example responses from persistence endpoints to verify 200 OK responses.
"""

from datetime import datetime
import json

def show_stats_response():
    """Show example /stats endpoint response."""
    print("📊 GET /api/v1/persistence/stats")
    print("Response (200 OK):")
    
    # Example successful response
    success_response = {
        "success": True,
        "stats": {
            "total_results": 6,
            "total_sessions": 2,
            "storage_size_bytes": 1048576,
            "storage_size_mb": 1.0,
            "storage_limit_mb": 500,
            "status_counts": {
                "completed": 6
            },
            "last_cleanup": 1640995000.0
        },
        "retrieved_at": datetime.utcnow().isoformat()
    }
    
    print(json.dumps(success_response, indent=2))
    print()
    
    # Example error response (still 200 OK)
    print("Response when service fails (200 OK with safe defaults):")
    error_response = {
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
    
    print(json.dumps(error_response, indent=2))
    print("\n" + "="*60 + "\n")

def show_client_analyses_response():
    """Show example /analyses/{client_id} endpoint response."""
    print("📋 GET /api/v1/persistence/analyses/{client_id}")
    print("Response (200 OK):")
    
    # Example successful response
    success_response = {
        "success": True,
        "client_id": "tbhzbpNX5GHaQPzfAAAD",
        "analyses": [
            {
                "analysis_id": "analysis-1750671752000-cxpnysy",
                "status": "completed",
                "created_at": 1640995200.0,
                "completed_at": 1640995210.0,
                "has_result": True,
                "retrieval_count": 2
            },
            {
                "analysis_id": "analysis-1750671868925-c6qcjap", 
                "status": "completed",
                "created_at": 1640995100.0,
                "completed_at": 1640995110.0,
                "has_result": True,
                "retrieval_count": 1
            }
        ],
        "count": 2,
        "limit": 10,
        "offset": 0,
        "retrieved_at": datetime.utcnow().isoformat()
    }
    
    print(json.dumps(success_response, indent=2))
    print()
    
    # Example error response (still 200 OK)
    print("Response when service fails (200 OK with empty array):")
    error_response = {
        "success": False,
        "error": "Failed to retrieve client analyses",
        "client_id": "unknown-client",
        "analyses": [],
        "count": 0,
        "limit": 10,
        "offset": 0,
        "retrieved_at": datetime.utcnow().isoformat()
    }
    
    print(json.dumps(error_response, indent=2))
    print("\n" + "="*60 + "\n")

def show_smart_routing_examples():
    """Show how the smart routing works for /analyses/{id}."""
    print("🧠 Smart Routing for /analyses/{id}")
    print("The endpoint automatically detects if ID is analysis_id or client_id:")
    print()
    
    print("Example 1: Analysis ID (has dashes and length > 20)")
    print("GET /api/v1/persistence/analyses/analysis-1750671752000-cxpnysy")
    print("→ Returns specific analysis result")
    print()
    
    print("Example 2: Client ID (WebSocket session ID)")
    print("GET /api/v1/persistence/analyses/tbhzbpNX5GHaQPzfAAAD")
    print("→ Returns client analysis history")
    print()
    
    print("Example 3: Unknown ID")
    print("GET /api/v1/persistence/analyses/unknown-id-123")
    print("→ Returns empty analysis history (200 OK)")
    print("\n" + "="*60 + "\n")

def main():
    """Show all endpoint examples."""
    print("🚀 Persistence Endpoint Response Examples")
    print("All endpoints return 200 OK to prevent frontend crashes")
    print("="*60 + "\n")
    
    show_stats_response()
    show_client_analyses_response()
    show_smart_routing_examples()
    
    print("✅ KEY BENEFITS:")
    print("• No 404 errors - all requests return 200 OK")
    print("• Safe default responses when data is missing")
    print("• Consistent JSON structure for easy frontend parsing")
    print("• Error information included in success:false responses")
    print("• Empty arrays instead of null values")
    print("• Smart routing handles both analysis_id and client_id")
    print()
    print("🚀 Ready to start server:")
    print("python3 -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000")

if __name__ == "__main__":
    main()