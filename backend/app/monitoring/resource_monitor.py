# backend/app/monitoring/resource_monitor.py
import asyncio
import psutil
import time
import logging
import gc
from collections import defaultdict, deque
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class ResourceMetrics:
    """Resource usage metrics snapshot"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_available: int
    memory_used: int
    active_connections: int
    active_analyses: int
    thread_count: int
    file_descriptors: int
    disk_io_read: int
    disk_io_write: int
    network_io_sent: int
    network_io_recv: int

@dataclass
class PerformanceThresholds:
    """Performance thresholds for alerts"""
    cpu_warning: float = 80.0
    cpu_critical: float = 95.0
    memory_warning: float = 85.0
    memory_critical: float = 95.0
    connections_warning: int = 100
    connections_critical: int = 200
    analyses_warning: int = 10
    analyses_critical: int = 20
    response_time_warning: float = 5.0
    response_time_critical: float = 15.0

class ResourceMonitor:
    """Comprehensive system resource monitoring"""
    
    def __init__(self, collection_interval: int = 30):
        self.collection_interval = collection_interval
        self.metrics_history = deque(maxlen=1440)  # 12 hours at 30s intervals
        self.thresholds = PerformanceThresholds()
        self.alert_history = deque(maxlen=100)
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Performance counters
        self.request_counters = defaultdict(int)
        self.response_times = deque(maxlen=1000)
        self.error_counts = defaultdict(int)
        
        # Resource tracking
        self.active_connections = 0
        self.active_analyses = 0
        self.peak_memory = 0
        self.peak_cpu = 0
        
        # Process reference
        self.process = psutil.Process()
        
        # Last I/O counters for delta calculation
        self.last_io_counters = None
        self.last_net_counters = None
        
    async def start_monitoring(self):
        """Start continuous resource monitoring"""
        if self.is_monitoring:
            logger.warning("Resource monitoring already running")
            return
            
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"🔍 Started resource monitoring (interval: {self.collection_interval}s)")
        
    async def stop_monitoring(self):
        """Stop resource monitoring"""
        if not self.is_monitoring:
            return
            
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Stopped resource monitoring")
        
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while self.is_monitoring:
                try:
                    # Collect metrics
                    metrics = await self._collect_metrics()
                    
                    # Store metrics
                    self.metrics_history.append(metrics)
                    
                    # Check thresholds and generate alerts
                    await self._check_thresholds(metrics)
                    
                    # Periodic cleanup
                    if len(self.metrics_history) % 120 == 0:  # Every hour
                        await self._periodic_cleanup()
                        
                    # Log summary every 10 minutes
                    if len(self.metrics_history) % 20 == 0:
                        await self._log_summary(metrics)
                        
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                    
                await asyncio.sleep(self.collection_interval)
                
        except asyncio.CancelledError:
            logger.info("📊 Resource monitoring loop cancelled")
            
    async def _collect_metrics(self) -> ResourceMetrics:
        """Collect current resource metrics"""
        try:
            # CPU and memory
            cpu_percent = self.process.cpu_percent(interval=None)
            memory_info = self.process.memory_info()
            system_memory = psutil.virtual_memory()
            
            # Process info
            thread_count = self.process.num_threads()
            
            # File descriptors (Unix systems)
            try:
                file_descriptors = self.process.num_fds()
            except (AttributeError, OSError):
                file_descriptors = 0
                
            # I/O counters
            try:
                io_counters = self.process.io_counters()
                if self.last_io_counters:
                    disk_io_read = io_counters.read_bytes - self.last_io_counters.read_bytes
                    disk_io_write = io_counters.write_bytes - self.last_io_counters.write_bytes
                else:
                    disk_io_read = disk_io_write = 0
                self.last_io_counters = io_counters
            except (AttributeError, OSError):
                disk_io_read = disk_io_write = 0
                
            # Network I/O
            try:
                net_counters = psutil.net_io_counters()
                if self.last_net_counters:
                    network_io_sent = net_counters.bytes_sent - self.last_net_counters.bytes_sent
                    network_io_recv = net_counters.bytes_recv - self.last_net_counters.bytes_recv
                else:
                    network_io_sent = network_io_recv = 0
                self.last_net_counters = net_counters
            except (AttributeError, OSError):
                network_io_sent = network_io_recv = 0
                
            # Update peaks
            self.peak_memory = max(self.peak_memory, memory_info.rss)
            self.peak_cpu = max(self.peak_cpu, cpu_percent)
            
            metrics = ResourceMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=system_memory.percent,
                memory_available=system_memory.available,
                memory_used=memory_info.rss,
                active_connections=self.active_connections,
                active_analyses=self.active_analyses,
                thread_count=thread_count,
                file_descriptors=file_descriptors,
                disk_io_read=disk_io_read,
                disk_io_write=disk_io_write,
                network_io_sent=network_io_sent,
                network_io_recv=network_io_recv
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error collecting metrics: {e}")
            # Return default metrics to prevent monitoring failure
            return ResourceMetrics(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available=0,
                memory_used=0,
                active_connections=self.active_connections,
                active_analyses=self.active_analyses,
                thread_count=0,
                file_descriptors=0,
                disk_io_read=0,
                disk_io_write=0,
                network_io_sent=0,
                network_io_recv=0
            )
            
    async def _check_thresholds(self, metrics: ResourceMetrics):
        """Check metrics against thresholds and generate alerts"""
        alerts = []
        
        # CPU alerts
        if metrics.cpu_percent >= self.thresholds.cpu_critical:
            alerts.append(f"🚨 CRITICAL: CPU usage {metrics.cpu_percent:.1f}% (threshold: {self.thresholds.cpu_critical}%)")
        elif metrics.cpu_percent >= self.thresholds.cpu_warning:
            alerts.append(f"⚠️ WARNING: CPU usage {metrics.cpu_percent:.1f}% (threshold: {self.thresholds.cpu_warning}%)")
            
        # Memory alerts
        if metrics.memory_percent >= self.thresholds.memory_critical:
            alerts.append(f"🚨 CRITICAL: Memory usage {metrics.memory_percent:.1f}% (threshold: {self.thresholds.memory_critical}%)")
        elif metrics.memory_percent >= self.thresholds.memory_warning:
            alerts.append(f"⚠️ WARNING: Memory usage {metrics.memory_percent:.1f}% (threshold: {self.thresholds.memory_warning}%)")
            
        # Connection alerts
        if metrics.active_connections >= self.thresholds.connections_critical:
            alerts.append(f"🚨 CRITICAL: {metrics.active_connections} active connections (threshold: {self.thresholds.connections_critical})")
        elif metrics.active_connections >= self.thresholds.connections_warning:
            alerts.append(f"⚠️ WARNING: {metrics.active_connections} active connections (threshold: {self.thresholds.connections_warning})")
            
        # Analysis alerts
        if metrics.active_analyses >= self.thresholds.analyses_critical:
            alerts.append(f"🚨 CRITICAL: {metrics.active_analyses} active analyses (threshold: {self.thresholds.analyses_critical})")
        elif metrics.active_analyses >= self.thresholds.analyses_warning:
            alerts.append(f"⚠️ WARNING: {metrics.active_analyses} active analyses (threshold: {self.thresholds.analyses_warning})")
            
        # Log alerts
        for alert in alerts:
            logger.warning(alert)
            self.alert_history.append({
                'timestamp': metrics.timestamp,
                'alert': alert,
                'metrics': metrics
            })
            
    async def _periodic_cleanup(self):
        """Perform periodic cleanup operations"""
        try:
            # Force garbage collection
            collected = gc.collect()
            logger.info(f"🧹 Garbage collection: {collected} objects collected")
            
            # Clear old error counts
            current_time = time.time()
            for key in list(self.error_counts.keys()):
                if current_time - key > 3600:  # Clear errors older than 1 hour
                    del self.error_counts[key]
                    
        except Exception as e:
            logger.error(f"❌ Error in periodic cleanup: {e}")
            
    async def _log_summary(self, metrics: ResourceMetrics):
        """Log resource usage summary"""
        if len(self.metrics_history) < 2:
            return
            
        # Calculate averages over last 10 minutes
        recent_metrics = list(self.metrics_history)[-20:]
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        
        logger.info(
            f"📊 RESOURCE_SUMMARY: "
            f"CPU: {metrics.cpu_percent:.1f}% (avg: {avg_cpu:.1f}%), "
            f"Memory: {metrics.memory_percent:.1f}% (avg: {avg_memory:.1f}%), "
            f"Connections: {metrics.active_connections}, "
            f"Analyses: {metrics.active_analyses}, "
            f"Threads: {metrics.thread_count}, "
            f"FDs: {metrics.file_descriptors}"
        )
        
    def update_connection_count(self, count: int):
        """Update active connection count"""
        self.active_connections = count
        
    def update_analysis_count(self, count: int):
        """Update active analysis count"""
        self.active_analyses = count
        
    def record_request(self, endpoint: str):
        """Record API request"""
        self.request_counters[endpoint] += 1
        
    def record_response_time(self, response_time: float):
        """Record response time"""
        self.response_times.append(response_time)
        
    def record_error(self, error_type: str):
        """Record error occurrence"""
        self.error_counts[time.time()] = error_type
        
    def get_current_metrics(self) -> Optional[ResourceMetrics]:
        """Get most recent metrics"""
        return self.metrics_history[-1] if self.metrics_history else None
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        if not self.metrics_history:
            return {"status": "no_data"}
            
        current = self.metrics_history[-1]
        
        # Calculate averages over different time periods
        last_hour = [m for m in self.metrics_history if current.timestamp - m.timestamp <= 3600]
        last_10min = [m for m in self.metrics_history if current.timestamp - m.timestamp <= 600]
        
        def calculate_stats(metrics_list):
            if not metrics_list:
                return {"avg": 0, "max": 0, "min": 0}
            cpu_values = [m.cpu_percent for m in metrics_list]
            memory_values = [m.memory_percent for m in metrics_list]
            return {
                "cpu": {"avg": sum(cpu_values) / len(cpu_values), "max": max(cpu_values), "min": min(cpu_values)},
                "memory": {"avg": sum(memory_values) / len(memory_values), "max": max(memory_values), "min": min(memory_values)}
            }
            
        return {
            "timestamp": current.timestamp,
            "current": {
                "cpu_percent": current.cpu_percent,
                "memory_percent": current.memory_percent,
                "memory_used_mb": current.memory_used // (1024 * 1024),
                "memory_available_mb": current.memory_available // (1024 * 1024),
                "active_connections": current.active_connections,
                "active_analyses": current.active_analyses,
                "thread_count": current.thread_count,
                "file_descriptors": current.file_descriptors
            },
            "peaks": {
                "memory_mb": self.peak_memory // (1024 * 1024),
                "cpu_percent": self.peak_cpu
            },
            "stats": {
                "last_10min": calculate_stats(last_10min),
                "last_hour": calculate_stats(last_hour)
            },
            "recent_alerts": list(self.alert_history)[-10:],
            "request_counts": dict(self.request_counters),
            "avg_response_time": sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            "error_count_last_hour": len([e for e in self.error_counts.keys() if current.timestamp - e <= 3600]),
            "thresholds": {
                "cpu_warning": self.thresholds.cpu_warning,
                "cpu_critical": self.thresholds.cpu_critical,
                "memory_warning": self.thresholds.memory_warning,
                "memory_critical": self.thresholds.memory_critical,
                "connections_warning": self.thresholds.connections_warning,
                "connections_critical": self.thresholds.connections_critical
            }
        }

# Global resource monitor instance
resource_monitor = ResourceMonitor()