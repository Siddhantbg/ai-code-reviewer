#!/usr/bin/env python3
"""
Test script to verify analysis persistence functionality.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the app directory to sys.path so we can import modules
sys.path.insert(0, str(Path(__file__).parent / "app"))

from services.analysis_persistence import AnalysisPersistenceService

async def test_persistence():
    """Test the analysis persistence functionality."""
    print("🧪 Testing Analysis Persistence Service...")
    
    # Initialize persistence service
    persistence = AnalysisPersistenceService(storage_dir="test_storage")
    
    # Test data
    test_analysis_id = "test-analysis-123"
    test_client_id = "test-client-456"
    test_client_ip = "127.0.0.1"
    test_code_hash = "test-hash-789"
    test_result_data = {
        "analysis_id": test_analysis_id,
        "timestamp": "2025-06-23T10:00:00Z",
        "language": "python",
        "filename": "test.py",
        "processing_time_ms": 1000,
        "issues": [
            {
                "id": "test_issue_1",
                "type": "bug",
                "severity": "medium",
                "title": "Test Bug",
                "description": "This is a test bug"
            }
        ]
    }
    
    print(f"📝 Storing analysis result: {test_analysis_id}")
    
    # Test storing analysis result
    success = await persistence.store_analysis_result(
        analysis_id=test_analysis_id,
        client_session_id=test_client_id,
        client_ip=test_client_ip,
        code_hash=test_code_hash,
        result_data=test_result_data,
        status='completed'
    )
    
    if success:
        print("✅ Analysis result stored successfully")
    else:
        print("❌ Failed to store analysis result")
        return False
    
    # Test retrieving analysis result
    print(f"📤 Retrieving analysis result: {test_analysis_id}")
    retrieved_data = await persistence.retrieve_analysis_result(
        analysis_id=test_analysis_id,
        client_session_id=test_client_id,
        client_ip=test_client_ip
    )
    
    if retrieved_data:
        print("✅ Analysis result retrieved successfully")
        print(f"   - Analysis ID: {retrieved_data.get('analysis_id')}")
        print(f"   - Language: {retrieved_data.get('language')}")
        print(f"   - Issues count: {len(retrieved_data.get('issues', []))}")
    else:
        print("❌ Failed to retrieve analysis result")
        return False
    
    # Test getting client analyses
    print(f"📋 Getting client analyses for: {test_client_id}")
    client_analyses = await persistence.get_client_analyses(
        client_session_id=test_client_id,
        client_ip=test_client_ip,
        limit=10,
        offset=0
    )
    
    if client_analyses:
        print(f"✅ Found {len(client_analyses)} analyses for client")
        for analysis in client_analyses:
            print(f"   - {analysis['analysis_id']} (status: {analysis['status']})")
    else:
        print("⚠️ No analyses found for client")
    
    # Test storage statistics
    print("📊 Getting storage statistics...")
    stats = persistence.get_storage_stats()
    
    if stats:
        print("✅ Storage statistics retrieved:")
        print(f"   - Total results: {stats.get('total_results', 0)}")
        print(f"   - Total sessions: {stats.get('total_sessions', 0)}")
        print(f"   - Storage size: {stats.get('storage_size_mb', 0):.2f} MB")
        print(f"   - Status counts: {stats.get('status_counts', {})}")
    else:
        print("❌ Failed to get storage statistics")
        return False
    
    # Clean up test storage
    test_storage_dir = Path("test_storage")
    if test_storage_dir.exists():
        for file in test_storage_dir.glob("*.json"):
            file.unlink()
        test_storage_dir.rmdir()
        print("🧹 Cleaned up test storage")
    
    print("✅ All persistence tests passed!")
    return True

async def test_existing_data():
    """Test with existing analysis data."""
    print("\n🔍 Testing with existing analysis data...")
    
    # Initialize persistence service with actual data
    persistence = AnalysisPersistenceService(storage_dir="analysis_storage")
    
    # Wait a moment for the service to load existing data
    await asyncio.sleep(1)
    
    # Get statistics
    stats = persistence.get_storage_stats()
    print(f"📊 Existing data statistics:")
    print(f"   - Total results: {stats.get('total_results', 0)}")
    print(f"   - Total sessions: {stats.get('total_sessions', 0)}")
    print(f"   - Storage size: {stats.get('storage_size_mb', 0):.2f} MB")
    
    # List some client sessions
    print(f"📋 Client sessions:")
    for session_id, analysis_ids in list(persistence.client_sessions.items())[:3]:
        print(f"   - {session_id}: {len(analysis_ids)} analyses")
        
        # Get analyses for this client
        analyses = await persistence.get_client_analyses(
            client_session_id=session_id,
            limit=3
        )
        for analysis in analyses:
            print(f"     * {analysis['analysis_id']} ({analysis['status']})")
    
    print("✅ Existing data test completed!")

if __name__ == "__main__":
    async def main():
        try:
            # Test basic persistence functionality
            success = await test_persistence()
            if not success:
                sys.exit(1)
            
            # Test with existing data
            await test_existing_data()
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    asyncio.run(main())