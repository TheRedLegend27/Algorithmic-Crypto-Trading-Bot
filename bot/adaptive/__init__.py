"""
Adaptive trading bot components.

This module contains the core data structures, interfaces, and enums
for the adaptive algorithmic trading system.
"""

# Import enums
from .enums import (
    RegimeType,
    AdaptationType,
    SignalStrength,
    OptimizationMethod,
    ModelType,
    PerformanceMetricType
)

# Import data models
from .data_models import (
    MarketRegime,
    AdaptiveSignal,
    PerformanceMetrics,
    OptimizationResult,
    AdaptationEvent,
    MLModelMetadata,
    StrategyAllocation
)

# Import interfaces
from .interfaces import (
    MarketRegimeDetectorInterface,
    AdaptiveStrategyEngineInterface,
    MLEngineInterface,
    ParameterOptimizerInterface,
    PerformanceAnalyzerInterface,
    AdaptationControllerInterface,
    DataManagerInterface,
    RiskManagerInterface,
    MonitoringInterface
)

__all__ = [
    # Enums
    'RegimeType',
    'AdaptationType', 
    'SignalStrength',
    'OptimizationMethod',
    'ModelType',
    'PerformanceMetricType',
    
    # Data Models
    'MarketRegime',
    'AdaptiveSignal',
    'PerformanceMetrics',
    'OptimizationResult',
    'AdaptationEvent',
    'MLModelMetadata',
    'StrategyAllocation',
    
    # Interfaces
    'MarketRegimeDetectorInterface',
    'AdaptiveStrategyEngineInterface',
    'MLEngineInterface',
    'ParameterOptimizerInterface',
    'PerformanceAnalyzerInterface',
    'AdaptationControllerInterface',
    'DataManagerInterface',
    'RiskManagerInterface',
    'MonitoringInterface'
]