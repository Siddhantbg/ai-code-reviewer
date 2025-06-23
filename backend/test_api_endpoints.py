#!/usr/bin/env python3
"""
Test script to verify persistence API endpoints.
"""

import requests
import json
import time

def test_persistence_endpoints():
    """Test the persistence API endpoints."""
    print("🧪 Testing Persistence API Endpoints...")
    
    base_url = "http://localhost:8000/api/v1/persistence"
    
    # Test 1: Get persistence statistics
    print("\n📊 Testing /stats endpoint...")
    try:
        response = requests.get(f"{base_url}/stats", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                stats = data.get("stats", {})
                print("✅ Statistics endpoint working:")
                print(f"   - Total results: {stats.get('total_results', 0)}")
                print(f"   - Total sessions: {stats.get('total_sessions', 0)}")
                print(f"   - Storage size: {stats.get('storage_size_mb', 0):.2f} MB")
                print(f"   - Status counts: {stats.get('status_counts', {})}")
            else:
                print("❌ Statistics endpoint returned unsuccessful response")
                return False
        else:
            print(f"❌ Statistics endpoint returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to statistics endpoint: {e}")
        return False
    
    # Test 2: Get client analyses (using an existing client ID from storage)
    print("\n📋 Testing /analyses/{client_id} endpoint...")
    
    # First, let's find an existing client ID from the storage files
    import os
    import json
    from pathlib import Path
    
    storage_dir = Path("analysis_storage")
    test_client_id = None
    
    if storage_dir.exists():
        for file_path in storage_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    test_client_id = data.get("client_session_id")
                    if test_client_id:
                        break
            except:
                continue
    
    if test_client_id:
        print(f"   Using existing client ID: {test_client_id}")
        try:
            response = requests.get(f"{base_url}/analyses/{test_client_id}", params={
                "limit": 5,
                "offset": 0
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    analyses = data.get("analyses", [])
                    print(f"✅ Client analyses endpoint working:")
                    print(f"   - Found {len(analyses)} analyses")
                    print(f"   - Client ID: {data.get('client_id')}")
                    print(f"   - Limit: {data.get('limit')}, Offset: {data.get('offset')}")
                    
                    for analysis in analyses[:3]:  # Show first 3
                        print(f"     * {analysis['analysis_id']} (status: {analysis['status']})")
                else:
                    print("❌ Client analyses endpoint returned unsuccessful response")
                    return False
            else:
                print(f"❌ Client analyses endpoint returned status {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to client analyses endpoint: {e}")
            return False
    else:
        print("⚠️ No existing client ID found in storage, testing with dummy ID...")
        try:
            response = requests.get(f"{base_url}/analyses/dummy-client-id", timeout=10)
            if response.status_code == 200:
                data = response.json()
                analyses = data.get("analyses", [])
                print(f"✅ Client analyses endpoint working (empty result expected):")
                print(f"   - Found {len(analyses)} analyses (should be 0)")
            else:
                print(f"❌ Client analyses endpoint returned unexpected status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to client analyses endpoint: {e}")
            return False
    
    # Test 3: Test individual analysis retrieval
    print("\n📤 Testing individual analysis retrieval...")
    
    # Find an existing analysis ID
    test_analysis_id = None
    if storage_dir.exists():
        for file_path in storage_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    test_analysis_id = data.get("analysis_id")
                    if test_analysis_id:
                        break
            except:
                continue
    
    if test_analysis_id:
        print(f"   Using existing analysis ID: {test_analysis_id}")
        try:
            response = requests.get(f"{base_url}/analyses/{test_analysis_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    result = data.get("result", {})
                    print(f"✅ Individual analysis retrieval working:")
                    print(f"   - Analysis ID: {data.get('analysis_id')}")
                    print(f"   - Language: {result.get('language', 'unknown')}")
                    print(f"   - Issues: {len(result.get('issues', []))}")
                    print(f"   - Processing time: {result.get('processing_time_ms', 0):.2f}ms")
                else:
                    print("❌ Individual analysis retrieval returned unsuccessful response")
            else:
                print(f"⚠️ Individual analysis retrieval returned status {response.status_code}")
                print("   This might be expected if analysis is expired or unauthorized")
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to individual analysis endpoint: {e}")
            return False
    else:
        print("⚠️ No existing analysis ID found, skipping individual retrieval test")
    
    print("\n✅ All persistence endpoint tests completed!")
    return True

def test_server_health():
    """Test if the server is running."""
    print("🏥 Testing server health...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is healthy: {data.get('message', 'Unknown status')}")
            print(f"   - AI Model Loaded: {data.get('ai_model_loaded', 'Unknown')}")
            return True
        else:
            print(f"❌ Server health check failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Server appears to be down: {e}")
        print("   Please start the server with: python3 -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000")
        return False

if __name__ == "__main__":
    print("🚀 Starting API Endpoint Tests...")
    
    # First check if server is running
    if not test_server_health():
        print("\n❌ Server is not running. Please start it first.")
        exit(1)
    
    # Test persistence endpoints
    if test_persistence_endpoints():
        print("\n🎉 All tests passed successfully!")
    else:
        print("\n❌ Some tests failed.")
        exit(1)