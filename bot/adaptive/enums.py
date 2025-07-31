"""
Enums for the adaptive trading bot system.
"""
from enum import Enum, auto


class RegimeType(Enum):
    """Market regime types for adaptive strategy selection."""
    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNCERTAIN = "uncertain"


class AdaptationType(Enum):
    """Types of adaptations the system can make."""
    STRATEGY_WEIGHT_CHANGE = "strategy_weight_change"
    PARAMETER_OPTIMIZATION = "parameter_optimization"
    REGIME_DETECTION_UPDATE = "regime_detection_update"
    RISK_PARAMETER_ADJUSTMENT = "risk_parameter_adjustment"
    MODEL_UPDATE = "model_update"
    EMERGENCY_ADAPTATION = "emergency_adaptation"


class SignalStrength(Enum):
    """Signal strength levels for adaptive signals."""
    VERY_WEAK = 0.2
    WEAK = 0.4
    MODERATE = 0.6
    STRONG = 0.8
    VERY_STRONG = 1.0


class OptimizationMethod(Enum):
    """Methods used for parameter optimization."""
    BAYESIAN = "bayesian"
    GENETIC_ALGORITHM = "genetic_algorithm"
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    WALK_FORWARD = "walk_forward"


class ModelType(Enum):
    """Types of machine learning models used."""
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    NEURAL_NETWORK = "neural_network"
    ENSEMBLE = "ensemble"
    LINEAR_REGRESSION = "linear_regression"


class PerformanceMetricType(Enum):
    """Types of performance metrics tracked."""
    TOTAL_RETURN = "total_return"
    ANNUALIZED_RETURN = "annualized_return"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR_RATIO = "calmar_ratio"


class ParameterType(Enum):
    """Types of parameters for optimization."""
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"


class OptimizationType(Enum):
    """Types of optimization algorithms available."""
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    PARTICLE_SWARM = "particle_swarm"
    SIMULATED_ANNEALING = "simulated_annealing"


class ValidationMethod(Enum):
    """Methods for validating optimization results."""
    WALK_FORWARD = "walk_forward"
    CROSS_VALIDATION = "cross_validation"
    HOLDOUT = "holdout"
    BOOTSTRAP = "bootstrap"
    TIME_SERIES_SPLIT = "time_series_split"


class ConstraintType(Enum):
    """Types of parameter constraints."""
    RANGE = "range"
    RELATIONSHIP = "relationship"  # e.g., param1 < param2
    CONDITIONAL = "conditional"  # e.g., if param1 > x then param2 < y
    CUSTOM = "custom"