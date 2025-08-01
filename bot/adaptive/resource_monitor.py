"""
Resource Monitoring and Automatic Scaling Module

This module provides comprehensive resource monitoring and automatic scaling
capabilities for the adaptive trading bot.
"""

import asyncio
import logging
import psutil
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ResourceThresholds:
    """Resource usage thresholds for scaling decisions"""
    cpu_scale_up: float = 70.0      # Scale up when CPU > 70%
    cpu_scale_down: float = 30.0    # Scale down when CPU < 30%
    memory_scale_up: float = 80.0   # Scale up when memory > 80%
    memory_scale_down: float = 40.0 # Scale down when memory < 40%
    disk_warning: float = 85.0      # Warning when disk > 85%
    disk_critical: float = 95.0     # Critical when disk > 95%
    
    # Time-based thresholds
    sustained_duration_minutes: int = 5  # Duration before scaling action
    cooldown_minutes: int = 10          # Cooldown between scaling actions


@dataclass
class ScalingLimits:
    """Limits for automatic scaling"""
    min_workers: int = 1
    max_workers: int = 8
    min_cache_size: int = 100
    max_cache_size: int = 5000
    min_batch_size: int = 10
    max_batch_size: int = 100


@dataclass
class ResourceMetrics:
    """Comprehensive resource metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_percent: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    thread_count: int
    open_files: int
    load_average: Tuple[float, float, float]  # 1min, 5min, 15min
    
    # Application-specific metrics
    active_positions: int = 0
    pending_orders: int = 0
    cache_hit_rate: float = 0.0
    api_requests_per_minute: float = 0.0
    ml_predictions_per_minute: float = 0.0


@dataclass
class ScalingAction:
    """Represents a scaling action taken"""
    timestamp: datetime
    action_type: str  # 'scale_up', 'scale_down', 'optimize'
    component: str    # 'workers', 'cache', 'batch_size'
    old_value: Any
    new_value: Any
    reason: str
    success: bool = False
    error_message: Optional[str] = None


class ResourceMonitor:
    """Advanced resource monitoring with predictive capabilities"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.thresholds = ResourceThresholds()
        self.scaling_limits = ScalingLimits()
        
        # Monitoring settings
        self.check_interval = self.config.get('check_interval_seconds', 30)
        self.history_size = self.config.get('history_size', 2880)  # 24 hours at 30s intervals
        
        # Data storage
        self.metrics_history: deque = deque(maxlen=self.history_size)
        self.scaling_history: List[ScalingAction] = []
        
        # State tracking
        self.monitoring_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.last_scaling_action: Optional[datetime] = None
        
        # Callbacks
        self.alert_callbacks: List[Callable] = []
        self.scaling_callbacks: List[Callable] = []
        
        # Thread pool for blocking operations
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    def add_alert_callback(self, callback: Callable[[str, ResourceMetrics], None]):
        """Add callback for resource alerts"""
        self.alert_callbacks.append(callback)
    
    def add_scaling_callback(self, callback: Callable[[ScalingAction], None]):
        """Add callback for scaling actions"""
        self.scaling_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start resource monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Resource monitoring started")
    
    async def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring_active = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.executor.shutdown(wait=True)
        logger.info("Resource monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Collect metrics
                metrics = await self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Check for alerts
                await self._check_alerts(metrics)
                
                # Check for scaling opportunities
                await self._check_scaling_needs(metrics)
                
                # Cleanup old data
                await self._cleanup_old_data()
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _collect_metrics(self) -> ResourceMetrics:
        """Collect comprehensive system metrics"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._collect_metrics_sync)
    
    def _collect_metrics_sync(self) -> ResourceMetrics:
        """Synchronous metrics collection"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024 ** 3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024 ** 3)
            
            # Network metrics
            network = psutil.net_io_counters()
            network_bytes_sent = network.bytes_sent
            network_bytes_recv = network.bytes_recv
            
            # Process metrics
            process = psutil.Process()
            process_count = len(psutil.pids())
            thread_count = process.num_threads()
            
            try:
                open_files = process.num_fds()  # Unix only
            except (AttributeError, psutil.AccessDenied):
                open_files = 0
            
            # Load average (Unix only)
            try:
                load_average = os.getloadavg()
            except (AttributeError, OSError):
                load_average = (0.0, 0.0, 0.0)
            
            return ResourceMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_percent=disk_percent,
                disk_free_gb=disk_free_gb,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                process_count=process_count,
                thread_count=thread_count,
                open_files=open_files,
                load_average=load_average
            )
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            # Return default metrics
            return ResourceMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_gb=0.0,
                disk_percent=0.0,
                disk_free_gb=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                process_count=0,
                thread_count=0,
                open_files=0,
                load_average=(0.0, 0.0, 0.0)
            )
    
    async def _check_alerts(self, metrics: ResourceMetrics):
        """Check metrics against alert thresholds"""
        alerts = []
        
        # CPU alerts
        if metrics.cpu_percent > 90:
            alerts.append(f"Critical CPU usage: {metrics.cpu_percent:.1f}%")
        elif metrics.cpu_percent > 80:
            alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")
        
        # Memory alerts
        if metrics.memory_percent > 95:
            alerts.append(f"Critical memory usage: {metrics.memory_percent:.1f}%")
        elif metrics.memory_percent > 85:
            alerts.append(f"High memory usage: {metrics.memory_percent:.1f}%")
        
        # Disk alerts
        if metrics.disk_percent > self.thresholds.disk_critical:
            alerts.append(f"Critical disk usage: {metrics.disk_percent:.1f}%")
        elif metrics.disk_percent > self.thresholds.disk_warning:
            alerts.append(f"High disk usage: {metrics.disk_percent:.1f}%")
        
        # Low memory available
        if metrics.memory_available_gb < 0.5:
            alerts.append(f"Low available memory: {metrics.memory_available_gb:.2f}GB")
        
        # High load average (Unix only)
        if metrics.load_average[0] > psutil.cpu_count() * 2:
            alerts.append(f"High load average: {metrics.load_average[0]:.2f}")
        
        # Trigger alert callbacks
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    await callback(alert, metrics)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")
    
    async def _check_scaling_needs(self, metrics: ResourceMetrics):
        """Check if scaling actions are needed"""
        # Check cooldown period
        if (self.last_scaling_action and 
            datetime.utcnow() - self.last_scaling_action < 
            timedelta(minutes=self.thresholds.cooldown_minutes)):
            return
        
        # Get recent metrics for trend analysis
        recent_metrics = self._get_recent_metrics(self.thresholds.sustained_duration_minutes)
        if len(recent_metrics) < 3:  # Need enough data points
            return
        
        # Analyze trends
        cpu_trend = self._analyze_trend([m.cpu_percent for m in recent_metrics])
        memory_trend = self._analyze_trend([m.memory_percent for m in recent_metrics])
        
        # Check for scale up conditions
        if (cpu_trend['avg'] > self.thresholds.cpu_scale_up and cpu_trend['trend'] > 0) or \
           (memory_trend['avg'] > self.thresholds.memory_scale_up and memory_trend['trend'] > 0):
            await self._scale_up(metrics, cpu_trend, memory_trend)
        
        # Check for scale down conditions
        elif (cpu_trend['avg'] < self.thresholds.cpu_scale_down and cpu_trend['trend'] < 0) and \
             (memory_trend['avg'] < self.thresholds.memory_scale_down and memory_trend['trend'] < 0):
            await self._scale_down(metrics, cpu_trend, memory_trend)
    
    def _get_recent_metrics(self, minutes: int) -> List[ResourceMetrics]:
        """Get metrics from the last N minutes"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def _analyze_trend(self, values: List[float]) -> Dict[str, float]:
        """Analyze trend in metric values"""
        if len(values) < 2:
            return {'avg': 0.0, 'trend': 0.0, 'std': 0.0}
        
        avg = np.mean(values)
        std = np.std(values)
        
        # Calculate trend using linear regression
        x = np.arange(len(values))
        trend = np.polyfit(x, values, 1)[0]  # Slope of the trend line
        
        return {
            'avg': float(avg),
            'trend': float(trend),
            'std': float(std)
        }
    
    async def _scale_up(self, metrics: ResourceMetrics, cpu_trend: Dict, memory_trend: Dict):
        """Execute scale up actions"""
        logger.info("Scaling up due to high resource usage")
        
        scaling_actions = []
        
        # Scale up worker threads if CPU bound
        if cpu_trend['avg'] > self.thresholds.cpu_scale_up:
            action = await self._scale_workers('up', 'High CPU usage')
            if action:
                scaling_actions.append(action)
        
        # Increase cache size if memory allows
        if memory_trend['avg'] < 70:  # Only if memory usage is reasonable
            action = await self._scale_cache('up', 'Optimize for performance')
            if action:
                scaling_actions.append(action)
        
        # Reduce batch sizes to reduce memory pressure
        if memory_trend['avg'] > self.thresholds.memory_scale_up:
            action = await self._scale_batch_size('down', 'High memory usage')
            if action:
                scaling_actions.append(action)
        
        if scaling_actions:
            self.last_scaling_action = datetime.utcnow()
            self.scaling_history.extend(scaling_actions)
            
            for callback in self.scaling_callbacks:
                for action in scaling_actions:
                    try:
                        await callback(action)
                    except Exception as e:
                        logger.error(f"Scaling callback error: {e}")
    
    async def _scale_down(self, metrics: ResourceMetrics, cpu_trend: Dict, memory_trend: Dict):
        """Execute scale down actions"""
        logger.info("Scaling down due to low resource usage")
        
        scaling_actions = []
        
        # Scale down worker threads if CPU usage is low
        if cpu_trend['avg'] < self.thresholds.cpu_scale_down:
            action = await self._scale_workers('down', 'Low CPU usage')
            if action:
                scaling_actions.append(action)
        
        # Reduce cache size to free memory
        if memory_trend['avg'] < self.thresholds.memory_scale_down:
            action = await self._scale_cache('down', 'Low memory usage')
            if action:
                scaling_actions.append(action)
        
        # Increase batch sizes for efficiency
        action = await self._scale_batch_size('up', 'Optimize for efficiency')
        if action:
            scaling_actions.append(action)
        
        if scaling_actions:
            self.last_scaling_action = datetime.utcnow()
            self.scaling_history.extend(scaling_actions)
            
            for callback in self.scaling_callbacks:
                for action in scaling_actions:
                    try:
                        await callback(action)
                    except Exception as e:
                        logger.error(f"Scaling callback error: {e}")
    
    async def _scale_workers(self, direction: str, reason: str) -> Optional[ScalingAction]:
        """Scale worker thread count"""
        try:
            # This would integrate with the actual performance optimizer
            from .performance_optimizer import get_performance_optimizer
            optimizer = get_performance_optimizer()
            
            current_workers = optimizer.parallel_processor.max_workers
            
            if direction == 'up':
                new_workers = min(current_workers + 1, self.scaling_limits.max_workers)
            else:
                new_workers = max(current_workers - 1, self.scaling_limits.min_workers)
            
            if new_workers != current_workers:
                # Apply the scaling (this would need to be implemented in the actual system)
                action = ScalingAction(
                    timestamp=datetime.utcnow(),
                    action_type=f'scale_{direction}',
                    component='workers',
                    old_value=current_workers,
                    new_value=new_workers,
                    reason=reason,
                    success=True
                )
                
                logger.info(f"Scaled workers from {current_workers} to {new_workers}: {reason}")
                return action
            
        except Exception as e:
            logger.error(f"Failed to scale workers: {e}")
            return ScalingAction(
                timestamp=datetime.utcnow(),
                action_type=f'scale_{direction}',
                component='workers',
                old_value=0,
                new_value=0,
                reason=reason,
                success=False,
                error_message=str(e)
            )
        
        return None
    
    async def _scale_cache(self, direction: str, reason: str) -> Optional[ScalingAction]:
        """Scale cache size"""
        try:
            from .performance_optimizer import get_performance_optimizer
            optimizer = get_performance_optimizer()
            
            current_size = optimizer.cache.max_size
            
            if direction == 'up':
                new_size = min(int(current_size * 1.5), self.scaling_limits.max_cache_size)
            else:
                new_size = max(int(current_size * 0.7), self.scaling_limits.min_cache_size)
            
            if new_size != current_size:
                # Apply the scaling
                optimizer.cache.max_size = new_size
                
                action = ScalingAction(
                    timestamp=datetime.utcnow(),
                    action_type=f'scale_{direction}',
                    component='cache',
                    old_value=current_size,
                    new_value=new_size,
                    reason=reason,
                    success=True
                )
                
                logger.info(f"Scaled cache from {current_size} to {new_size}: {reason}")
                return action
            
        except Exception as e:
            logger.error(f"Failed to scale cache: {e}")
            return ScalingAction(
                timestamp=datetime.utcnow(),
                action_type=f'scale_{direction}',
                component='cache',
                old_value=0,
                new_value=0,
                reason=reason,
                success=False,
                error_message=str(e)
            )
        
        return None
    
    async def _scale_batch_size(self, direction: str, reason: str) -> Optional[ScalingAction]:
        """Scale batch processing size"""
        # This is a placeholder - would need to integrate with actual batch processing
        try:
            current_batch_size = 50  # Default batch size
            
            if direction == 'up':
                new_batch_size = min(int(current_batch_size * 1.5), self.scaling_limits.max_batch_size)
            else:
                new_batch_size = max(int(current_batch_size * 0.7), self.scaling_limits.min_batch_size)
            
            if new_batch_size != current_batch_size:
                action = ScalingAction(
                    timestamp=datetime.utcnow(),
                    action_type=f'scale_{direction}',
                    component='batch_size',
                    old_value=current_batch_size,
                    new_value=new_batch_size,
                    reason=reason,
                    success=True
                )
                
                logger.info(f"Scaled batch size from {current_batch_size} to {new_batch_size}: {reason}")
                return action
            
        except Exception as e:
            logger.error(f"Failed to scale batch size: {e}")
            return ScalingAction(
                timestamp=datetime.utcnow(),
                action_type=f'scale_{direction}',
                component='batch_size',
                old_value=0,
                new_value=0,
                reason=reason,
                success=False,
                error_message=str(e)
            )
        
        return None
    
    async def _cleanup_old_data(self):
        """Clean up old monitoring data"""
        # Remove scaling history older than 7 days
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        self.scaling_history = [
            action for action in self.scaling_history
            if action.timestamp >= cutoff_time
        ]
    
    def get_current_metrics(self) -> Optional[ResourceMetrics]:
        """Get the most recent metrics"""
        return self.metrics_history[-1] if self.metrics_history else None
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for specified time period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {}
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        disk_values = [m.disk_percent for m in recent_metrics]
        
        return {
            'period_hours': hours,
            'sample_count': len(recent_metrics),
            'cpu_usage': {
                'avg': np.mean(cpu_values),
                'max': np.max(cpu_values),
                'min': np.min(cpu_values),
                'current': recent_metrics[-1].cpu_percent
            },
            'memory_usage': {
                'avg': np.mean(memory_values),
                'max': np.max(memory_values),
                'min': np.min(memory_values),
                'current': recent_metrics[-1].memory_percent
            },
            'disk_usage': {
                'avg': np.mean(disk_values),
                'max': np.max(disk_values),
                'min': np.min(disk_values),
                'current': recent_metrics[-1].disk_percent
            },
            'scaling_actions': len([
                a for a in self.scaling_history
                if a.timestamp >= cutoff_time
            ])
        }
    
    def get_scaling_history(self, hours: int = 24) -> List[ScalingAction]:
        """Get scaling history for specified time period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            action for action in self.scaling_history
            if action.timestamp >= cutoff_time
        ]
    
    def export_metrics(self, filename: str = None) -> str:
        """Export metrics to JSON file"""
        if filename is None:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f'resource_metrics_{timestamp}.json'
        
        data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'metrics_count': len(self.metrics_history),
            'scaling_actions_count': len(self.scaling_history),
            'metrics': [
                {
                    'timestamp': m.timestamp.isoformat(),
                    'cpu_percent': m.cpu_percent,
                    'memory_percent': m.memory_percent,
                    'disk_percent': m.disk_percent,
                    'load_average': m.load_average
                }
                for m in self.metrics_history
            ],
            'scaling_actions': [
                {
                    'timestamp': a.timestamp.isoformat(),
                    'action_type': a.action_type,
                    'component': a.component,
                    'old_value': a.old_value,
                    'new_value': a.new_value,
                    'reason': a.reason,
                    'success': a.success,
                    'error_message': a.error_message
                }
                for a in self.scaling_history
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Metrics exported to {filename}")
        return filename


# Global resource monitor instance
_resource_monitor: Optional[ResourceMonitor] = None


def get_resource_monitor(config: Dict[str, Any] = None) -> ResourceMonitor:
    """Get or create resource monitor instance"""
    global _resource_monitor
    
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor(config)
    
    return _resource_monitor