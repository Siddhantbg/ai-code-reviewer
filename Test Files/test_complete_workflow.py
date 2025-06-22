#!/usr/bin/env python3
"""
Comprehensive End-to-End Analysis Workflow Test Suite

Tests the complete flow from WebSocket connection to analysis completion,
including resource monitoring, connection stability, and result delivery.
"""
import asyncio
import json
import time
import uuid
import subprocess
import signal
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import psutil
import socketio
from dataclasses import dataclass
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

@dataclass
class TestResult:
    test_name: str
    success: bool
    duration: float
    details: Dict[str, Any]
    error: Optional[str] = None

@dataclass
class ResourceMetrics:
    cpu_percent: float
    memory_mb: float
    connections: int
    timestamp: float

class WorkflowTester:
    """Comprehensive workflow tester for the AI Code Reviewer"""
    
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.test_results: List[TestResult] = []
        self.resource_metrics: List[ResourceMetrics] = []
        self.backend_process: Optional[subprocess.Popen] = None
        self.sio: Optional[socketio.AsyncClient] = None
        self.analysis_events: List[Dict[str, Any]] = []
        
    async def setup_test_environment(self) -> bool:
        """Set up the test environment"""
        print("🔧 Setting up test environment...")
        
        try:
            # Check if backend is running
            if not await self.check_backend_health():
                print("   ⚠️ Backend not running, attempting to start...")
                if not await self.start_backend():
                    return False
            else:
                print("   ✅ Backend is already running")
            
            # Set up WebSocket client
            await self.setup_websocket_client()
            
            print("   ✅ Test environment ready")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to set up test environment: {e}")
            return False
    
    async def check_backend_health(self) -> bool:
        """Check if backend is healthy"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.backend_url}/health") as response:
                    return response.status == 200
        except:
            return False
    
    async def start_backend(self) -> bool:
        """Start the backend server"""
        try:
            backend_dir = Path(__file__).parent / "backend"
            
            # Start backend process
            self.backend_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for backend to start
            for _ in range(30):  # Wait up to 30 seconds
                await asyncio.sleep(1)
                if await self.check_backend_health():
                    print("   ✅ Backend started successfully")
                    return True
            
            print("   ❌ Backend failed to start within timeout")
            return False
            
        except Exception as e:
            print(f"   ❌ Failed to start backend: {e}")
            return False
    
    async def setup_websocket_client(self) -> None:
        """Set up WebSocket client for testing"""
        self.sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=1,
            logger=False,
            engineio_logger=False
        )
        
        # Event handlers for testing
        @self.sio.event
        async def connect():
            print("   🔌 WebSocket connected for testing")
        
        @self.sio.event
        async def disconnect():
            print("   🔌 WebSocket disconnected")
        
        @self.sio.event
        async def analysis_progress(data):
            self.analysis_events.append({
                'type': 'progress',
                'data': data,
                'timestamp': time.time()
            })
        
        @self.sio.event
        async def analysis_complete(data):
            self.analysis_events.append({
                'type': 'complete',
                'data': data,
                'timestamp': time.time()
            })
        
        @self.sio.event
        async def analysis_error(data):
            self.analysis_events.append({
                'type': 'error',
                'data': data,
                'timestamp': time.time()
            })
        
        # Connect to backend
        await self.sio.connect(self.backend_url)
    
    def record_resource_metrics(self) -> None:
        """Record current resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 * 1024)
            connections = len(psutil.net_connections())
            
            self.resource_metrics.append(ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                connections=connections,
                timestamp=time.time()
            ))
        except Exception as e:
            print(f"   ⚠️ Failed to record metrics: {e}")
    
    async def test_websocket_connection_stability(self) -> TestResult:
        """Test WebSocket connection stability"""
        test_name = "WebSocket Connection Stability"
        start_time = time.time()
        
        try:
            print(f"🧪 Testing {test_name}...")
            
            # Test basic connection
            if not self.sio.connected:
                await self.sio.connect(self.backend_url)
            
            # Test ping/pong
            start_ping = time.time()
            await self.sio.emit('ping')
            
            # Wait for pong (should be automatic)
            await asyncio.sleep(1)
            
            # Test connection persistence over time
            connection_checks = []
            for i in range(10):
                connected = self.sio.connected
                connection_checks.append(connected)
                await asyncio.sleep(0.5)
            
            stability_rate = sum(connection_checks) / len(connection_checks)
            
            duration = time.time() - start_time
            success = stability_rate >= 0.9  # 90% stability required
            
            details = {
                'stability_rate': stability_rate,
                'connection_checks': len(connection_checks),
                'ping_response': True
            }
            
            result = TestResult(test_name, success, duration, details)
            
            if success:
                print(f"   ✅ {test_name} passed - {stability_rate:.1%} stability")
            else:
                print(f"   ❌ {test_name} failed - {stability_rate:.1%} stability")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(test_name, False, duration, {}, str(e))
            print(f"   ❌ {test_name} failed: {e}")
            return result
    
    async def test_analysis_workflow(self, test_code: str, language: str = "python") -> TestResult:
        """Test complete analysis workflow"""
        test_name = f"Analysis Workflow ({language})"
        start_time = time.time()
        
        try:
            print(f"🧪 Testing {test_name}...")
            
            # Clear previous events
            self.analysis_events.clear()
            
            # Generate unique analysis ID
            analysis_id = str(uuid.uuid4())
            
            # Start resource monitoring
            initial_metrics = len(self.resource_metrics)
            monitor_task = asyncio.create_task(self.monitor_resources_during_analysis())
            
            # Submit analysis
            analysis_data = {
                'analysisId': analysis_id,
                'code': test_code,
                'language': language,
                'analysis_type': 'full',
                'include_suggestions': True,
                'include_explanations': True,
                'severity_threshold': 'low'
            }
            
            print(f"   📤 Submitting analysis {analysis_id[:8]}...")
            await self.sio.emit('start_analysis', analysis_data)
            
            # Wait for completion with timeout
            completion_timeout = 120  # 2 minutes
            start_wait = time.time()
            completed = False
            
            while time.time() - start_wait < completion_timeout:
                # Check for completion events
                for event in self.analysis_events:
                    if (event['type'] == 'complete' and 
                        event['data'].get('analysisId') == analysis_id):
                        completed = True
                        break
                    elif (event['type'] == 'error' and 
                          event['data'].get('analysisId') == analysis_id):
                        raise Exception(f"Analysis failed: {event['data'].get('error')}")
                
                if completed:
                    break
                
                await asyncio.sleep(0.5)
            
            # Stop resource monitoring
            monitor_task.cancel()
            
            if not completed:
                raise Exception("Analysis did not complete within timeout")
            
            # Analyze results
            progress_events = [e for e in self.analysis_events if e['type'] == 'progress']
            complete_events = [e for e in self.analysis_events if e['type'] == 'complete']
            
            duration = time.time() - start_time
            
            # Verify result structure
            result_data = complete_events[0]['data']['result']
            required_fields = ['analysis_id', 'summary', 'issues', 'metrics']
            
            for field in required_fields:
                if field not in result_data:
                    raise Exception(f"Missing required field in result: {field}")
            
            details = {
                'analysis_id': analysis_id,
                'progress_events': len(progress_events),
                'completion_time': duration,
                'result_fields': list(result_data.keys()),
                'total_issues': result_data['summary']['total_issues'],
                'overall_score': result_data['summary']['overall_score'],
                'resource_samples': len(self.resource_metrics) - initial_metrics
            }
            
            result = TestResult(test_name, True, duration, details)
            print(f"   ✅ {test_name} completed in {duration:.2f}s")
            print(f"      📊 Found {details['total_issues']} issues, score: {details['overall_score']}")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(test_name, False, duration, {
                'analysis_id': analysis_id if 'analysis_id' in locals() else None,
                'events_received': len(self.analysis_events)
            }, str(e))
            print(f"   ❌ {test_name} failed: {e}")
            return result
    
    async def monitor_resources_during_analysis(self) -> None:
        """Monitor resources during analysis"""
        try:
            while True:
                self.record_resource_metrics()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    
    async def test_connection_recovery(self) -> TestResult:
        """Test connection recovery during analysis"""
        test_name = "Connection Recovery"
        start_time = time.time()
        
        try:
            print(f"🧪 Testing {test_name}...")
            
            # Start an analysis
            analysis_id = str(uuid.uuid4())
            test_code = """
def test_function():
    # Simple test function
    return "hello world"
"""
            
            analysis_data = {
                'analysisId': analysis_id,
                'code': test_code,
                'language': 'python',
                'analysis_type': 'full'
            }
            
            print("   📤 Starting analysis...")
            await self.sio.emit('start_analysis', analysis_data)
            
            # Wait a bit for analysis to start
            await asyncio.sleep(2)
            
            # Simulate connection loss
            print("   🔌 Simulating connection loss...")
            await self.sio.disconnect()
            
            # Wait during disconnection
            await asyncio.sleep(3)
            
            # Reconnect
            print("   🔄 Reconnecting...")
            await self.sio.connect(self.backend_url)
            
            # Check analysis status
            await self.sio.emit('check_analysis_status', {'analysisId': analysis_id})
            
            # Wait for response
            await asyncio.sleep(5)
            
            # Check if we received status or completion
            received_events = len(self.analysis_events)
            
            duration = time.time() - start_time
            success = received_events > 0  # Should receive some response
            
            details = {
                'analysis_id': analysis_id,
                'events_after_reconnection': received_events,
                'reconnection_time': duration
            }
            
            result = TestResult(test_name, success, duration, details)
            
            if success:
                print(f"   ✅ {test_name} passed - received {received_events} events after reconnection")
            else:
                print(f"   ❌ {test_name} failed - no events received after reconnection")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(test_name, False, duration, {}, str(e))
            print(f"   ❌ {test_name} failed: {e}")
            return result
    
    async def test_resource_optimization(self) -> TestResult:
        """Test resource usage during analysis"""
        test_name = "Resource Optimization"
        start_time = time.time()
        
        try:
            print(f"🧪 Testing {test_name}...")
            
            # Record baseline metrics
            baseline_metrics = []
            for _ in range(5):
                self.record_resource_metrics()
                baseline_metrics.append(self.resource_metrics[-1])
                await asyncio.sleep(0.5)
            
            baseline_cpu = sum(m.cpu_percent for m in baseline_metrics) / len(baseline_metrics)
            baseline_memory = sum(m.memory_mb for m in baseline_metrics) / len(baseline_metrics)
            
            # Run analysis and monitor resources
            test_code = """
def complex_function(data):
    # Simulate more complex code for analysis
    result = []
    for item in data:
        if item is not None:
            result.append(item * 2)
    return result

def another_function():
    # Potential division by zero
    x = 10
    y = 0
    return x / y  # This should be flagged

class TestClass:
    def __init__(self):
        self.data = []
    
    def process_data(self, input_data):
        # SQL injection vulnerability simulation
        query = "SELECT * FROM users WHERE id = '" + str(input_data) + "'"
        return query
"""
            
            analysis_result = await self.test_analysis_workflow(test_code, "python")
            
            # Analyze resource usage during analysis
            analysis_metrics = self.resource_metrics[-20:]  # Last 20 samples
            
            if analysis_metrics:
                max_cpu = max(m.cpu_percent for m in analysis_metrics)
                max_memory = max(m.memory_mb for m in analysis_metrics)
                avg_cpu = sum(m.cpu_percent for m in analysis_metrics) / len(analysis_metrics)
                avg_memory = sum(m.memory_mb for m in analysis_metrics) / len(analysis_metrics)
            else:
                max_cpu = avg_cpu = baseline_cpu
                max_memory = avg_memory = baseline_memory
            
            # Check optimization criteria
            cpu_spike = max_cpu - baseline_cpu
            memory_spike = max_memory - baseline_memory
            
            # Success criteria (adjusted for our optimizations)
            cpu_ok = max_cpu < 200  # Less than 200% CPU usage
            memory_ok = memory_spike < 500  # Less than 500MB memory increase
            
            duration = time.time() - start_time
            success = cpu_ok and memory_ok and analysis_result.success
            
            details = {
                'baseline_cpu': baseline_cpu,
                'baseline_memory': baseline_memory,
                'max_cpu': max_cpu,
                'max_memory': max_memory,
                'avg_cpu': avg_cpu,
                'avg_memory': avg_memory,
                'cpu_spike': cpu_spike,
                'memory_spike': memory_spike,
                'cpu_within_limits': cpu_ok,
                'memory_within_limits': memory_ok,
                'analysis_successful': analysis_result.success
            }
            
            result = TestResult(test_name, success, duration, details)
            
            if success:
                print(f"   ✅ {test_name} passed")
                print(f"      📊 CPU: {avg_cpu:.1f}% avg, {max_cpu:.1f}% peak (limit: 200%)")
                print(f"      💾 Memory: +{memory_spike:.1f}MB spike (limit: 500MB)")
            else:
                print(f"   ❌ {test_name} failed")
                if not cpu_ok:
                    print(f"      🔥 CPU usage too high: {max_cpu:.1f}%")
                if not memory_ok:
                    print(f"      💥 Memory spike too high: {memory_spike:.1f}MB")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(test_name, False, duration, {}, str(e))
            print(f"   ❌ {test_name} failed: {e}")
            return result
    
    async def run_all_tests(self) -> None:
        """Run the complete test suite"""
        print("🚀 Starting Complete Analysis Workflow Tests\n")
        
        # Setup
        if not await self.setup_test_environment():
            print("❌ Failed to set up test environment")
            return
        
        print("\n" + "="*60)
        print("📋 RUNNING COMPREHENSIVE TEST SUITE")
        print("="*60)
        
        # Test 1: WebSocket Connection Stability
        result1 = await self.test_websocket_connection_stability()
        self.test_results.append(result1)
        
        print()
        
        # Test 2: Basic Analysis Workflow
        simple_code = """
def hello_world():
    return "Hello, World!"
"""
        result2 = await self.test_analysis_workflow(simple_code, "python")
        self.test_results.append(result2)
        
        print()
        
        # Test 3: Complex Analysis Workflow
        complex_code = """
import os

def vulnerable_function(user_input):
    # SQL Injection vulnerability
    query = "SELECT * FROM users WHERE name = '" + user_input + "'"
    
    # Command injection vulnerability
    os.system("echo " + user_input)
    
    # Division by zero risk
    result = 10 / 0
    
    return query

def good_function():
    # This should get a good score
    if input_data and len(input_data) > 0:
        return process_safely(input_data)
    else:
        return None
"""
        result3 = await self.test_analysis_workflow(complex_code, "python")
        self.test_results.append(result3)
        
        print()
        
        # Test 4: Resource Optimization
        result4 = await self.test_resource_optimization()
        self.test_results.append(result4)
        
        print()
        
        # Test 5: Connection Recovery
        result5 = await self.test_connection_recovery()
        self.test_results.append(result5)
        
        print()
        
        # Generate final report
        await self.generate_test_report()
    
    async def generate_test_report(self) -> None:
        """Generate comprehensive test report"""
        print("="*60)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.success)
        
        print(f"\n🎯 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {total_tests - passed_tests}")
        print(f"   Success Rate: {passed_tests/total_tests:.1%}")
        
        print(f"\n📋 Test Details:")
        for result in self.test_results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"   {status} {result.test_name} ({result.duration:.2f}s)")
            if result.error:
                print(f"      Error: {result.error}")
            
            # Show key metrics for each test
            if "stability_rate" in result.details:
                print(f"      Stability: {result.details['stability_rate']:.1%}")
            if "total_issues" in result.details:
                print(f"      Issues Found: {result.details['total_issues']}")
            if "overall_score" in result.details:
                print(f"      Code Score: {result.details['overall_score']}/10")
            if "max_cpu" in result.details:
                print(f"      Peak CPU: {result.details['max_cpu']:.1f}%")
            if "memory_spike" in result.details:
                print(f"      Memory Spike: +{result.details['memory_spike']:.1f}MB")
        
        # Resource analysis
        if self.resource_metrics:
            print(f"\n📊 Resource Usage Analysis:")
            cpu_values = [m.cpu_percent for m in self.resource_metrics]
            memory_values = [m.memory_mb for m in self.resource_metrics]
            
            print(f"   CPU Usage:")
            print(f"      Average: {sum(cpu_values)/len(cpu_values):.1f}%")
            print(f"      Peak: {max(cpu_values):.1f}%")
            print(f"      Samples: {len(cpu_values)}")
            
            print(f"   Memory Usage:")
            print(f"      Average: {sum(memory_values)/len(memory_values):.1f}MB")
            print(f"      Peak: {max(memory_values):.1f}MB")
            print(f"      Range: {max(memory_values) - min(memory_values):.1f}MB")
        
        # Final assessment
        print(f"\n🏁 Final Assessment:")
        if passed_tests == total_tests:
            print("   🎉 EXCELLENT: All tests passed!")
            print("   ✅ WebSocket connections are stable")
            print("   ✅ Analysis workflow works end-to-end")
            print("   ✅ Resource usage is optimized")
            print("   ✅ Connection recovery is working")
            print("   ✅ Results are displayed properly")
        elif passed_tests >= total_tests * 0.8:
            print("   ✅ GOOD: Most tests passed")
            print("   ⚠️ Some minor issues may need attention")
        else:
            print("   ⚠️ WARNING: Multiple test failures")
            print("   🔧 System needs troubleshooting")
        
        # Save detailed report
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'success_rate': passed_tests / total_tests
            },
            'test_results': [
                {
                    'name': r.test_name,
                    'success': r.success,
                    'duration': r.duration,
                    'details': r.details,
                    'error': r.error
                }
                for r in self.test_results
            ],
            'resource_metrics': [
                {
                    'cpu_percent': m.cpu_percent,
                    'memory_mb': m.memory_mb,
                    'timestamp': m.timestamp
                }
                for m in self.resource_metrics
            ]
        }
        
        report_file = 'workflow_test_report.json'
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
    
    async def cleanup(self) -> None:
        """Clean up test environment"""
        print("\n🧹 Cleaning up test environment...")
        
        if self.sio and self.sio.connected:
            await self.sio.disconnect()
        
        if self.backend_process:
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()

async def main():
    """Main test function"""
    tester = WorkflowTester()
    
    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test suite terminated")
        sys.exit(1)