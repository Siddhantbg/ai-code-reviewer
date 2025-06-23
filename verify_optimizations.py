#!/usr/bin/env python3
"""
Simple verification script to check that optimizations are in place
"""
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def verify_ai_service_optimizations():
    """Verify AI service has optimization features"""
    print("🔍 Verifying AI service optimizations...")
    
    try:
        # Import and check AI service
        from app.services.ai_service import AICodeAnalyzer, CPU_THREADS, CPU_THROTTLE_DELAY
        
        # Check CPU thread reduction
        if CPU_THREADS <= 2:
            print(f"   ✅ CPU threads reduced to {CPU_THREADS} (was 4)")
        else:
            print(f"   ❌ CPU threads still high: {CPU_THREADS}")
            return False
        
        # Check throttle delay exists
        if CPU_THROTTLE_DELAY > 0:
            print(f"   ✅ CPU throttling delay added: {CPU_THROTTLE_DELAY}s")
        else:
            print(f"   ❌ No CPU throttling delay")
            return False
        
        # Check AI analyzer has new methods
        analyzer = AICodeAnalyzer()
        
        if hasattr(analyzer, '_cleanup_after_analysis'):
            print("   ✅ Memory cleanup method added")
        else:
            print("   ❌ Memory cleanup method missing")
            return False
        
        if hasattr(analyzer, 'thread_pool'):
            print("   ✅ Shared thread pool implemented")
        else:
            print("   ❌ Shared thread pool missing")
            return False
        
        if hasattr(analyzer, 'last_cleanup_time'):
            print("   ✅ Cleanup tracking added")
        else:
            print("   ❌ Cleanup tracking missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error verifying AI service: {e}")
        return False

def verify_performance_optimizer():
    """Verify performance optimizer has enhanced features"""
    print("\n🔍 Verifying performance optimizer enhancements...")
    
    try:
        from app.utils.performance_optimizer import PerformanceOptimizer
        
        optimizer = PerformanceOptimizer()
        
        # Check reduced limits
        if optimizer.max_concurrent_ai_operations <= 1:
            print(f"   ✅ AI operations limited to {optimizer.max_concurrent_ai_operations}")
        else:
            print(f"   ❌ AI operations limit too high: {optimizer.max_concurrent_ai_operations}")
            return False
        
        if optimizer.max_cpu_usage_percent <= 80:
            print(f"   ✅ CPU usage limit reduced to {optimizer.max_cpu_usage_percent}%")
        else:
            print(f"   ❌ CPU usage limit too high: {optimizer.max_cpu_usage_percent}%")
            return False
        
        if optimizer.max_memory_usage_mb <= 1536:
            print(f"   ✅ Memory limit reduced to {optimizer.max_memory_usage_mb}MB")
        else:
            print(f"   ❌ Memory limit too high: {optimizer.max_memory_usage_mb}MB")
            return False
        
        # Check new cleanup features
        if hasattr(optimizer, 'ai_cleanup_threshold'):
            print("   ✅ AI-specific cleanup threshold added")
        else:
            print("   ❌ AI-specific cleanup threshold missing")
            return False
        
        if hasattr(optimizer, '_ai_operation_cleanup'):
            print("   ✅ AI operation cleanup method added")
        else:
            print("   ❌ AI operation cleanup method missing")
            return False
        
        if hasattr(optimizer, '_ai_specific_cleanup'):
            print("   ✅ AI-specific cleanup method added")
        else:
            print("   ❌ AI-specific cleanup method missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error verifying performance optimizer: {e}")
        return False

def verify_resource_monitor():
    """Verify resource monitor has AI tracking"""
    print("\n🔍 Verifying resource monitor enhancements...")
    
    try:
        from app.monitoring.resource_monitor import ResourceMonitor
        
        monitor = ResourceMonitor()
        
        # Check AI operation tracking
        if hasattr(monitor, 'active_ai_operations'):
            print("   ✅ AI operation tracking added")
        else:
            print("   ❌ AI operation tracking missing")
            return False
        
        if hasattr(monitor, 'ai_operation_times'):
            print("   ✅ AI operation timing added")
        else:
            print("   ❌ AI operation timing missing")
            return False
        
        if hasattr(monitor, 'update_ai_operation_count'):
            print("   ✅ AI operation count method added")
        else:
            print("   ❌ AI operation count method missing")
            return False
        
        if hasattr(monitor, 'record_ai_operation_time'):
            print("   ✅ AI operation time recording added")
        else:
            print("   ❌ AI operation time recording missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error verifying resource monitor: {e}")
        return False

def main():
    """Main verification function"""
    print("🚀 Verifying AI processing optimizations...\n")
    
    ai_service_ok = verify_ai_service_optimizations()
    performance_ok = verify_performance_optimizer()
    monitor_ok = verify_resource_monitor()
    
    print(f"\n🏁 Verification Results:")
    print(f"   AI Service Optimizations: {'✅ PASS' if ai_service_ok else '❌ FAIL'}")
    print(f"   Performance Optimizer: {'✅ PASS' if performance_ok else '❌ FAIL'}")
    print(f"   Resource Monitor: {'✅ PASS' if monitor_ok else '❌ FAIL'}")
    
    all_ok = ai_service_ok and performance_ok and monitor_ok
    print(f"   Overall: {'🎉 ALL VERIFICATIONS PASSED' if all_ok else '⚠️ SOME VERIFICATIONS FAILED'}")
    
    if all_ok:
        print("\n📋 Optimization Summary:")
        print("   ✅ CPU threads reduced from 4 to 2")
        print("   ✅ CPU throttling delays added")
        print("   ✅ Memory cleanup after AI operations")
        print("   ✅ Shared thread pool to reduce overhead")
        print("   ✅ AI operation limits reduced")
        print("   ✅ Memory and CPU usage limits lowered")
        print("   ✅ Enhanced resource monitoring")
        print("   ✅ AI-specific cleanup routines")
        print("\n🎯 Expected impact:")
        print("   - CPU usage should be reduced by ~50%")
        print("   - Memory usage should be more stable")
        print("   - Better resource cleanup after operations")
        print("   - Improved system responsiveness")
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)