"""
Data models for the adaptive trading bot system.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from .enums import RegimeType, AdaptationType, SignalStrength, OptimizationMethod, ModelType, ParameterType, OptimizationType


@dataclass
class MarketRegime:
    """Represents the current market regime and its characteristics."""
    regime_type: RegimeType
    confidence: float  # 0.0 to 1.0
    volatility_level: float  # Normalized volatility measure
    trend_strength: float  # -1.0 (strong bear) to 1.0 (strong bull)
    momentum: float  # -1.0 (negative) to 1.0 (positive)
    detected_at: datetime
    supporting_indicators: Dict[str, float] = field(default_factory=dict)
    timeframe_analysis: Dict[str, float] = field(default_factory=dict)  # e.g., {"5m": 0.8, "1h": 0.6}
    
    def __post_init__(self):
        """Validate the data after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        if not -1.0 <= self.trend_strength <= 1.0:
            raise ValueError("Trend strength must be between -1.0 and 1.0")
        if not -1.0 <= self.momentum <= 1.0:
            raise ValueError("Momentum must be between -1.0 and 1.0")


@dataclass
class AdaptiveSignal:
    """Enhanced trading signal with adaptive context and metadata."""
    pair: str
    signal_type: str  # 'buy', 'sell', 'hold'
    strength: SignalStrength
    confidence: float  # 0.0 to 1.0
    price: float
    timestamp: datetime
    
    # Adaptive context
    regime_context: MarketRegime
    ml_confidence: float  # ML model confidence in this signal
    strategy_weights: Dict[str, float] = field(default_factory=dict)  # Contributing strategy weights
    parameter_adjustments: Dict[str, float] = field(default_factory=dict)  # Dynamic parameter adjustments
    
    # Risk and position sizing
    suggested_position_size: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Metadata
    adaptation_metadata: Dict[str, Any] = field(default_factory=dict)
    contributing_indicators: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate the signal data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        if not 0.0 <= self.ml_confidence <= 1.0:
            raise ValueError("ML confidence must be between 0.0 and 1.0")
        if self.signal_type not in ['buy', 'sell', 'hold']:
            raise ValueError("Signal type must be 'buy', 'sell', or 'hold'")


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for strategies and the overall system."""
    # Basic return metrics
    total_return: float
    annualized_return: float
    excess_return: float  # Return above benchmark
    
    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    
    # Risk metrics
    max_drawdown: float
    volatility: float
    downside_deviation: float
    
    # Trade statistics
    win_rate: float  # Percentage of winning trades
    profit_factor: float  # Gross profit / Gross loss
    avg_trade_duration: timedelta
    trades_count: int
    avg_win: float
    avg_loss: float
    
    # Regime-specific performance
    regime_performance: Dict[RegimeType, float] = field(default_factory=dict)
    
    # Time-based metrics
    last_updated: datetime = field(default_factory=datetime.now)
    measurement_period: timedelta = field(default=timedelta(days=30))
    
    # Additional metrics
    recovery_factor: Optional[float] = None  # Net profit / Max drawdown
    expectancy: Optional[float] = None  # Expected value per trade
    
    def __post_init__(self):
        """Calculate derived metrics."""
        if self.max_drawdown != 0:
            self.recovery_factor = self.total_return / abs(self.max_drawdown)
        
        if self.trades_count > 0:
            self.expectancy = (self.win_rate * self.avg_win) - ((1 - self.win_rate) * abs(self.avg_loss))


@dataclass
class OptimizationResult:
    """Result of a parameter optimization process."""
    strategy_name: str
    optimization_method: OptimizationMethod
    
    # Parameter changes
    old_parameters: Dict[str, float]
    new_parameters: Dict[str, float]
    
    # Performance impact
    performance_improvement: float  # Expected improvement in target metric
    confidence_score: float  # Confidence in the optimization result
    validation_score: float  # Out-of-sample validation score
    
    # Optional fields with defaults
    parameter_bounds: Dict[str, tuple] = field(default_factory=dict)  # (min, max) for each param
    
    # Optimization details
    iterations_performed: int = 0
    optimization_time: timedelta = field(default=timedelta())
    validation_period: timedelta = field(default=timedelta(days=7))
    
    # Metadata
    applied_at: Optional[datetime] = None
    market_regime_during_optimization: Optional[RegimeType] = None
    data_points_used: int = 0
    
    def get_parameter_changes(self) -> Dict[str, float]:
        """Get the absolute change in each parameter."""
        changes = {}
        for param in self.old_parameters:
            if param in self.new_parameters:
                changes[param] = self.new_parameters[param] - self.old_parameters[param]
        return changes
    
    def get_parameter_change_percentages(self) -> Dict[str, float]:
        """Get the percentage change in each parameter."""
        percentages = {}
        for param in self.old_parameters:
            if param in self.new_parameters and self.old_parameters[param] != 0:
                old_val = self.old_parameters[param]
                new_val = self.new_parameters[param]
                percentages[param] = ((new_val - old_val) / old_val) * 100
        return percentages


@dataclass
class AdaptationEvent:
    """Record of a system adaptation event."""
    event_id: str
    event_type: AdaptationType
    trigger_reason: str
    
    # Changes made
    changes_made: Dict[str, Any]
    
    # Impact assessment
    expected_impact: float  # Expected performance improvement
    
    # Optional fields with defaults
    affected_strategies: List[str] = field(default_factory=list)
    affected_pairs: List[str] = field(default_factory=list)
    actual_impact: Optional[float] = None  # Measured impact after implementation
    success: Optional[bool] = None  # Whether the adaptation was successful
    
    # Timing
    timestamp: datetime = field(default_factory=datetime.now)
    evaluation_period: timedelta = field(default=timedelta(hours=24))
    
    # Control
    rollback_available: bool = True
    rollback_data: Optional[Dict[str, Any]] = None
    auto_rollback_threshold: float = -0.05  # Rollback if performance drops by 5%
    
    # Context
    market_conditions: Optional[Dict[str, Any]] = None
    system_state: Optional[Dict[str, Any]] = None
    
    def is_due_for_evaluation(self) -> bool:
        """Check if enough time has passed to evaluate the adaptation."""
        return datetime.now() - self.timestamp >= self.evaluation_period
    
    def should_rollback(self) -> bool:
        """Determine if the adaptation should be rolled back."""
        if not self.rollback_available or self.actual_impact is None:
            return False
        return self.actual_impact < self.auto_rollback_threshold


@dataclass
class MLModelMetadata:
    """Metadata for machine learning models used in the system."""
    model_id: str
    model_type: ModelType
    version: str
    
    # Training information
    trained_at: datetime
    training_data_size: int
    training_period: timedelta
    
    # Performance metrics
    training_accuracy: float
    validation_accuracy: float
    
    # Optional fields with defaults
    features_used: List[str] = field(default_factory=list)
    test_accuracy: Optional[float] = None
    
    # Model configuration
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    feature_importance: Dict[str, float] = field(default_factory=dict)
    
    # Deployment information
    deployed_at: Optional[datetime] = None
    is_active: bool = False
    prediction_count: int = 0
    
    # Performance tracking
    recent_accuracy: Optional[float] = None
    drift_score: Optional[float] = None
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyAllocation:
    """Represents the allocation of capital to different strategies."""
    strategy_name: str
    allocation_percentage: float  # 0.0 to 1.0
    current_weight: float  # Current dynamic weight based on performance
    base_weight: float  # Base weight before performance adjustments
    
    # Performance tracking
    recent_performance: float
    performance_trend: float  # Positive = improving, negative = declining
    confidence_level: float
    
    # Constraints
    min_allocation: float = 0.0
    max_allocation: float = 1.0
    
    # Status
    is_active: bool = True
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate allocation data."""
        if not 0.0 <= self.allocation_percentage <= 1.0:
            raise ValueError("Allocation percentage must be between 0.0 and 1.0")
        if not self.min_allocation <= self.allocation_percentage <= self.max_allocation:
            raise ValueError("Allocation must be within min/max bounds")


@dataclass
class ParameterBounds:
    """Defines bounds and constraints for optimization parameters."""
    param_type: ParameterType
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    categories: Optional[List[Any]] = None
    default_value: Optional[Any] = None
    
    # Constraints
    step_size: Optional[float] = None  # For discrete parameters
    constraints: List[str] = field(default_factory=list)  # Constraint descriptions
    
    def __post_init__(self):
        """Validate parameter bounds."""
        if self.param_type in [ParameterType.CONTINUOUS, ParameterType.INTEGER]:
            if self.min_value is None or self.max_value is None:
                raise ValueError(f"min_value and max_value required for {self.param_type}")
            if self.min_value >= self.max_value:
                raise ValueError("min_value must be less than max_value")
        elif self.param_type == ParameterType.CATEGORICAL:
            if not self.categories or len(self.categories) == 0:
                raise ValueError("categories required for CATEGORICAL parameter type")
    
    def is_valid_value(self, value: Any) -> bool:
        """Check if a value is valid for this parameter."""
        if self.param_type == ParameterType.CONTINUOUS:
            return isinstance(value, (int, float)) and self.min_value <= value <= self.max_value
        elif self.param_type == ParameterType.INTEGER:
            return isinstance(value, int) and self.min_value <= value <= self.max_value
        elif self.param_type == ParameterType.CATEGORICAL:
            return value in self.categories
        return False


@dataclass
class ParameterSet:
    """A set of parameters for a strategy or system component."""
    name: str
    parameters: Dict[str, Any]
    regime_context: Optional[RegimeType] = None
    performance_score: Optional[float] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    
    # Validation
    is_validated: bool = False
    validation_results: Dict[str, Any] = field(default_factory=dict)
    
    def update_usage(self):
        """Update usage statistics."""
        self.last_used = datetime.now()
        self.usage_count += 1


@dataclass 
class OptimizationResult:
    """Enhanced optimization result with additional fields for parameter optimization."""
    optimization_id: str
    strategy_name: str
    optimization_method: str
    
    # Parameter changes
    old_parameters: Dict[str, Any]
    new_parameters: Dict[str, Any]
    
    # Performance impact
    performance_improvement: float
    confidence_score: float
    
    # Timing and validation
    validation_period: timedelta
    applied_at: datetime
    
    # Success tracking
    success: bool = True
    error_message: Optional[str] = None
    
    # Additional metrics
    out_of_sample_performance: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def get_parameter_changes(self) -> Dict[str, Any]:
        """Get the change in each parameter."""
        changes = {}
        for param in self.old_parameters:
            if param in self.new_parameters:
                old_val = self.old_parameters[param]
                new_val = self.new_parameters[param]
                if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                    changes[param] = new_val - old_val
                else:
                    changes[param] = f"{old_val} -> {new_val}"
        return changes