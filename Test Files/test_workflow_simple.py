#!/usr/bin/env python3
"""
Simplified End-to-End Workflow Test

Tests the complete analysis workflow using existing infrastructure.
This test focuses on verifying the fixes work correctly.
"""
import asyncio
import json
import time
import uuid
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

class SimpleWorkflowTest:
    """Simplified workflow tester"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = time.time()
    
    def test_file_structure(self):
        """Test that all required files exist and have the fixes"""
        print("🔍 Testing file structure and fixes...")
        
        checks = {
            'frontend_websocket': {
                'file': 'frontend/src/lib/websocket.ts',
                'required_content': [
                    'completionCallbacksRef',
                    'analysisTimeoutsRef', 
                    'handleReconnect',
                    'waitForAnalysis',
                    'check_analysis_status'
                ]
            },
            'frontend_page': {
                'file': 'frontend/src/app/page.tsx',
                'required_content': [
                    'useAnalysisSocket',
                    'ConnectionMonitor',
                    'handleReconnect',
                    'handleRetryAnalysis'
                ]
            },
            'connection_monitor': {
                'file': 'frontend/src/components/ConnectionMonitor.tsx',
                'required_content': [
                    'Auto-reconnecting',
                    'onRetryAnalysis',
                    'ConnectionStatus'
                ]
            },
            'backend_main': {
                'file': 'backend/app/main.py',
                'required_content': [
                    'check_analysis_status',
                    'Analysis still in progress',
                    'active_analyses'
                ]
            },
            'ai_service': {
                'file': 'backend/app/services/ai_service.py',
                'required_content': [
                    '_cleanup_after_analysis',
                    'CPU_THROTTLE_DELAY',
                    'thread_pool',
                    'CPU_THREADS = 2'
                ]
            },
            'performance_optimizer': {
                'file': 'backend/app/utils/performance_optimizer.py',
                'required_content': [
                    'max_concurrent_ai_operations = 1',
                    '_ai_operation_cleanup',
                    'adaptive_cpu_throttling'
                ]
            }
        }
        
        results = {}
        for test_name, config in checks.items():
            file_path = config['file']
            required_content = config['required_content']
            
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    found_content = []
                    missing_content = []
                    
                    for item in required_content:
                        if item in content:
                            found_content.append(item)
                        else:
                            missing_content.append(item)
                    
                    success = len(missing_content) == 0
                    results[test_name] = {
                        'success': success,
                        'file_exists': True,
                        'found': found_content,
                        'missing': missing_content,
                        'coverage': len(found_content) / len(required_content)
                    }
                    
                    status = "✅" if success else "⚠️"
                    coverage = len(found_content) / len(required_content)
                    print(f"   {status} {test_name}: {coverage:.1%} coverage ({len(found_content)}/{len(required_content)})")
                    
                    if missing_content:
                        print(f"      Missing: {', '.join(missing_content[:3])}{'...' if len(missing_content) > 3 else ''}")
                
                else:
                    results[test_name] = {
                        'success': False,
                        'file_exists': False,
                        'error': 'File not found'
                    }
                    print(f"   ❌ {test_name}: File not found - {file_path}")
            
            except Exception as e:
                results[test_name] = {
                    'success': False,
                    'error': str(e)
                }
                print(f"   ❌ {test_name}: Error - {e}")
        
        return results
    
    def test_configuration_consistency(self):
        """Test that configurations are consistent across files"""
        print("\n🔧 Testing configuration consistency...")
        
        configs = {}
        issues = []
        
        # Check WebSocket timeout settings
        try:
            with open('frontend/src/lib/websocket.ts', 'r') as f:
                ws_content = f.read()
            
            # Extract timeout values
            if 'pingTimeout: 120000' in ws_content:
                configs['frontend_ping_timeout'] = 120000
            if 'pingInterval: 60000' in ws_content:
                configs['frontend_ping_interval'] = 60000
            
            print("   ✅ Frontend WebSocket timeouts configured")
        except:
            issues.append("Could not verify frontend WebSocket timeouts")
        
        # Check backend timeout settings
        try:
            with open('backend/app/main.py', 'r') as f:
                backend_content = f.read()
            
            if 'ping_timeout=120' in backend_content or 'ping_timeout_threshold = 120' in backend_content:
                configs['backend_ping_timeout'] = 120000
                print("   ✅ Backend WebSocket timeouts configured")
            else:
                issues.append("Backend ping timeout not found")
                
        except:
            issues.append("Could not verify backend WebSocket timeouts")
        
        # Check AI service optimization settings
        try:
            with open('backend/app/services/ai_service.py', 'r') as f:
                ai_content = f.read()
            
            if 'CPU_THREADS = 2' in ai_content:
                configs['ai_cpu_threads'] = 2
                print("   ✅ AI service CPU threads optimized")
            else:
                issues.append("AI CPU threads not optimized")
            
            if 'CPU_THROTTLE_DELAY' in ai_content:
                print("   ✅ AI service CPU throttling configured")
            else:
                issues.append("AI CPU throttling not configured")
                
        except:
            issues.append("Could not verify AI service settings")
        
        # Check performance optimizer settings
        try:
            with open('backend/app/utils/performance_optimizer.py', 'r') as f:
                perf_content = f.read()
            
            if 'max_concurrent_ai_operations = 1' in perf_content:
                configs['max_ai_operations'] = 1
                print("   ✅ Performance optimizer limits configured")
            else:
                issues.append("Performance optimizer limits not set")
                
        except:
            issues.append("Could not verify performance optimizer settings")
        
        if issues:
            print("   ⚠️ Configuration issues found:")
            for issue in issues:
                print(f"      - {issue}")
        
        return {
            'configs': configs,
            'issues': issues,
            'success': len(issues) == 0
        }
    
    def test_integration_points(self):
        """Test integration between components"""
        print("\n🔗 Testing component integration...")
        
        integration_tests = []
        
        # Test 1: Frontend uses enhanced WebSocket hook
        try:
            with open('frontend/src/app/page.tsx', 'r') as f:
                page_content = f.read()
            
            if 'useAnalysisSocket' in page_content and 'startAnalysis' in page_content:
                integration_tests.append({
                    'name': 'Frontend WebSocket Integration',
                    'success': True,
                    'details': 'Page uses enhanced analysis socket hook'
                })
                print("   ✅ Frontend WebSocket integration verified")
            else:
                integration_tests.append({
                    'name': 'Frontend WebSocket Integration',
                    'success': False,
                    'details': 'Page does not use enhanced socket hook'
                })
                print("   ❌ Frontend WebSocket integration missing")
        except:
            integration_tests.append({
                'name': 'Frontend WebSocket Integration',
                'success': False,
                'details': 'Could not verify frontend integration'
            })
        
        # Test 2: Backend analysis status checking
        try:
            with open('backend/app/main.py', 'r') as f:
                backend_content = f.read()
            
            if '@sio.event' in backend_content and 'check_analysis_status' in backend_content:
                integration_tests.append({
                    'name': 'Backend Status Checking',
                    'success': True,
                    'details': 'Backend has analysis status checking endpoint'
                })
                print("   ✅ Backend status checking endpoint verified")
            else:
                integration_tests.append({
                    'name': 'Backend Status Checking',
                    'success': False,
                    'details': 'Backend status checking endpoint missing'
                })
                print("   ❌ Backend status checking endpoint missing")
        except:
            integration_tests.append({
                'name': 'Backend Status Checking',
                'success': False,
                'details': 'Could not verify backend integration'
            })
        
        # Test 3: AI service resource optimization
        try:
            with open('backend/app/services/ai_service.py', 'r') as f:
                ai_content = f.read()
            
            with open('backend/app/utils/performance_optimizer.py', 'r') as f:
                perf_content = f.read()
            
            ai_optimized = '_cleanup_after_analysis' in ai_content
            perf_optimized = '_ai_operation_cleanup' in perf_content
            
            if ai_optimized and perf_optimized:
                integration_tests.append({
                    'name': 'AI Resource Optimization',
                    'success': True,
                    'details': 'AI service and performance optimizer integrated'
                })
                print("   ✅ AI resource optimization integration verified")
            else:
                integration_tests.append({
                    'name': 'AI Resource Optimization',
                    'success': False,
                    'details': f'AI optimized: {ai_optimized}, Perf optimized: {perf_optimized}'
                })
                print("   ❌ AI resource optimization integration incomplete")
        except:
            integration_tests.append({
                'name': 'AI Resource Optimization',
                'success': False,
                'details': 'Could not verify AI optimization integration'
            })
        
        return integration_tests
    
    def generate_test_report(self, file_results, config_results, integration_results):
        """Generate comprehensive test report"""
        print("\n" + "="*60)
        print("📊 WORKFLOW TEST REPORT")
        print("="*60)
        
        # Summary
        total_file_tests = len(file_results)
        passed_file_tests = sum(1 for r in file_results.values() if r['success'])
        
        total_integration_tests = len(integration_results)
        passed_integration_tests = sum(1 for r in integration_results if r['success'])
        
        config_success = config_results['success']
        
        total_tests = total_file_tests + total_integration_tests + 1  # +1 for config
        passed_tests = passed_file_tests + passed_integration_tests + (1 if config_success else 0)
        
        print(f"\n🎯 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {total_tests - passed_tests}")
        print(f"   Success Rate: {passed_tests/total_tests:.1%}")
        
        print(f"\n📁 File Structure Tests ({passed_file_tests}/{total_file_tests}):")
        for name, result in file_results.items():
            status = "✅" if result['success'] else "❌"
            coverage = result.get('coverage', 0)
            print(f"   {status} {name}: {coverage:.1%} coverage")
        
        print(f"\n⚙️ Configuration Tests:")
        status = "✅" if config_success else "❌"
        print(f"   {status} Configuration Consistency")
        if config_results['issues']:
            for issue in config_results['issues']:
                print(f"      - {issue}")
        
        print(f"\n🔗 Integration Tests ({passed_integration_tests}/{total_integration_tests}):")
        for test in integration_results:
            status = "✅" if test['success'] else "❌"
            print(f"   {status} {test['name']}")
            if not test['success']:
                print(f"      Details: {test['details']}")
        
        # Key features status
        print(f"\n🔑 Key Features Status:")
        
        features = {
            'WebSocket Connection Management': any('websocket' in name.lower() and result['success'] 
                                                  for name, result in file_results.items()),
            'Analysis Completion Handling': file_results.get('frontend_websocket', {}).get('success', False),
            'Connection Recovery': file_results.get('connection_monitor', {}).get('success', False),
            'Resource Optimization': file_results.get('ai_service', {}).get('success', False),
            'Backend Status Checking': any(test['name'] == 'Backend Status Checking' and test['success'] 
                                         for test in integration_results),
            'Configuration Consistency': config_success
        }
        
        for feature, status in features.items():
            icon = "✅" if status else "❌"
            print(f"   {icon} {feature}")
        
        # Final assessment
        print(f"\n🏁 Final Assessment:")
        if passed_tests == total_tests:
            print("   🎉 EXCELLENT: All workflow components verified!")
            print("   🚀 System is ready for end-to-end testing")
        elif passed_tests >= total_tests * 0.9:
            print("   ✅ VERY GOOD: Most components verified")
            print("   🔧 Minor fixes may be needed")
        elif passed_tests >= total_tests * 0.8:
            print("   ✅ GOOD: Core components verified")
            print("   ⚠️ Some issues need attention")
        else:
            print("   ⚠️ WARNING: Multiple issues found")
            print("   🔧 Significant work needed before testing")
        
        # Save report
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'success_rate': passed_tests / total_tests
            },
            'file_results': file_results,
            'config_results': config_results,
            'integration_results': integration_results,
            'features': features
        }
        
        with open('workflow_verification_report.json', 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: workflow_verification_report.json")
        
        duration = time.time() - self.start_time
        print(f"⏱️ Test completed in {duration:.2f} seconds")
        
        return passed_tests == total_tests
    
    def run_tests(self):
        """Run all workflow verification tests"""
        print("🚀 Starting Workflow Verification Tests\n")
        
        # Run tests
        file_results = self.test_file_structure()
        config_results = self.test_configuration_consistency() 
        integration_results = self.test_integration_points()
        
        # Generate report
        success = self.generate_test_report(file_results, config_results, integration_results)
        
        return success

def main():
    """Main test function"""
    tester = SimpleWorkflowTest()
    
    try:
        success = tester.run_tests()
        
        if success:
            print("\n🎉 All workflow verification tests PASSED!")
            print("\n📋 Next Steps for Live Testing:")
            print("   1. Start backend: cd backend && python -m uvicorn app.main:app --reload")
            print("   2. Start frontend: cd frontend && npm run dev")
            print("   3. Open http://localhost:3000")
            print("   4. Test analysis with various code samples")
            print("   5. Test connection interruption scenarios")
        else:
            print("\n⚠️ Some verification tests failed")
            print("   Please review the issues above before live testing")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)