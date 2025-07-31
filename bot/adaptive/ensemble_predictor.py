"""
Enhanced Ensemble Prediction System for the adaptive trading bot.

This module implements advanced ensemble methods that combine multiple ML models
with sophisticated confidence scoring, uncertainty quantification, and fallback mechanisms.
"""
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from sklearn.ensemble import VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
import warnings
warnings.filterwarnings('ignore')

from .interfaces import MLEngineInterface
from .data_models import AdaptiveSignal, MLModelMetadata, PerformanceMetrics
from .enums import ModelType, RegimeType


@dataclass
class EnsemblePrediction:
    """Enhanced prediction result with confidence and uncertainty metrics."""
    prediction: float  # Main prediction probability
    confidence: float  # Overall confidence in the prediction
    uncertainty: float  # Uncertainty/variance in the prediction
    
    # Individual model contributions
    model_predictions: Dict[ModelType, float] = field(default_factory=dict)
    model_weights: Dict[ModelType, float] = field(default_factory=dict)
    model_confidences: Dict[ModelType, float] = field(default_factory=dict)
    
    # Ensemble metadata
    ensemble_method: str = "weighted_average"
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    
    # Quality metrics
    prediction_quality: float = 0.0  # Overall quality score
    consensus_level: float = 0.0  # Agreement between models
    
    # Context
    timestamp: datetime = field(default_factory=datetime.now)
    market_regime: Optional[RegimeType] = None
    
    def get_prediction_interval(self, confidence_level: float = 0.95) -> Tuple[float, float]:
        """Calculate prediction interval based on uncertainty."""
        z_score = 1.96 if confidence_level == 0.95 else 2.58  # 95% or 99%
        margin = z_score * self.uncertainty
        return (
            max(0.0, self.prediction - margin),
            min(1.0, self.prediction + margin)
        )


@dataclass
class ModelPerformanceTracker:
    """Tracks individual model performance for dynamic weighting."""
    model_type: ModelType
    recent_accuracy: float = 0.5
    long_term_accuracy: float = 0.5
    prediction_count: int = 0
    
    # Performance by regime
    regime_performance: Dict[RegimeType, float] = field(default_factory=dict)
    
    # Reliability metrics
    calibration_score: float = 0.5  # How well probabilities match actual outcomes
    consistency_score: float = 0.5  # How consistent predictions are
    
    # Temporal performance
    recent_predictions: List[Tuple[float, bool]] = field(default_factory=list)  # (prediction, actual)
    performance_trend: float = 0.0  # Positive = improving, negative = declining
    
    # Last update
    last_updated: datetime = field(default_factory=datetime.now)
    
    def update_performance(self, prediction: float, actual_outcome: bool) -> None:
        """Update performance metrics with new prediction result."""
        self.recent_predictions.append((prediction, actual_outcome))
        
        # Keep only recent predictions (last 100)
        if len(self.recent_predictions) > 100:
            self.recent_predictions = self.recent_predictions[-100:]
        
        self.prediction_count += 1
        
        # Update accuracy metrics
        if len(self.recent_predictions) >= 4:  # Lower threshold for testing
            recent_data = self.recent_predictions[-min(20, len(self.recent_predictions)):]
            recent_outcomes = [outcome for _, outcome in recent_data]
            recent_preds = [pred for pred, _ in recent_data]
            
            # Calculate recent accuracy
            self.recent_accuracy = np.mean([
                1.0 if (pred > 0.5) == outcome else 0.0
                for pred, outcome in recent_data
            ])
            
            # Calculate calibration score (Brier score)
            brier_scores = [(pred - float(outcome))**2 for pred, outcome in recent_data]
            self.calibration_score = 1.0 - np.mean(brier_scores)  # Higher is better
            
            # Calculate consistency (inverse of prediction variance)
            pred_variance = np.var(recent_preds)
            self.consistency_score = 1.0 / (1.0 + pred_variance)
        
        # Update long-term accuracy with exponential moving average
        alpha = 0.1  # Learning rate
        accuracy = 1.0 if (prediction > 0.5) == actual_outcome else 0.0
        self.long_term_accuracy = alpha * accuracy + (1 - alpha) * self.long_term_accuracy
        
        # Calculate performance trend
        if len(self.recent_predictions) >= 10:  # Lower threshold
            mid_point = len(self.recent_predictions) // 2
            first_half = self.recent_predictions[:mid_point]
            second_half = self.recent_predictions[mid_point:]
            
            if len(first_half) > 0 and len(second_half) > 0:
                first_half_acc = np.mean([1.0 if (p > 0.5) == o else 0.0 for p, o in first_half])
                second_half_acc = np.mean([1.0 if (p > 0.5) == o else 0.0 for p, o in second_half])
                
                self.performance_trend = second_half_acc - first_half_acc
        
        self.last_updated = datetime.now()
    
    def get_dynamic_weight(self, base_weight: float = 1.0) -> float:
        """Calculate dynamic weight based on recent performance."""
        # Base weight adjustment factors
        accuracy_factor = self.recent_accuracy
        calibration_factor = self.calibration_score
        consistency_factor = self.consistency_score
        trend_factor = 1.0 + (self.performance_trend * 0.5)  # Boost improving models
        
        # Combine factors
        performance_multiplier = (
            accuracy_factor * 0.4 +
            calibration_factor * 0.3 +
            consistency_factor * 0.2 +
            trend_factor * 0.1
        )
        
        return base_weight * performance_multiplier


class EnsemblePredictor:
    """Advanced ensemble prediction system with confidence scoring and fallback mechanisms."""
    
    def __init__(self, ml_engine: MLEngineInterface):
        self.logger = logging.getLogger(__name__)
        self.ml_engine = ml_engine
        
        # Performance tracking for individual models
        self.model_trackers: Dict[ModelType, ModelPerformanceTracker] = {}
        
        # Ensemble configuration
        self.ensemble_config = {
            'min_models_for_ensemble': 2,
            'confidence_threshold': 0.6,
            'uncertainty_threshold': 0.3,
            'consensus_threshold': 0.7,
            'fallback_prediction': 0.5,
            'weight_decay_factor': 0.95,  # Decay old performance
            'regime_weight_adjustment': True
        }
        
        # Ensemble methods
        self.ensemble_methods = {
            'weighted_average': self._weighted_average_ensemble,
            'stacking': self._stacking_ensemble,
            'bayesian_model_averaging': self._bayesian_model_averaging,
            'confidence_weighted': self._confidence_weighted_ensemble
        }
        
        # Fallback mechanisms
        self.fallback_strategies = [
            self._technical_analysis_fallback,
            self._regime_based_fallback,
            self._historical_average_fallback,
            self._conservative_fallback
        ]
        
        # Initialize model trackers
        self._initialize_model_trackers()
    
    def predict_with_ensemble(
        self, 
        signal: AdaptiveSignal, 
        market_conditions: Dict[str, Any],
        ensemble_method: str = 'weighted_average'
    ) -> EnsemblePrediction:
        """
        Generate ensemble prediction with confidence scoring and uncertainty quantification.
        
        Args:
            signal: Adaptive signal to predict outcome for
            market_conditions: Current market conditions
            ensemble_method: Method to use for ensemble prediction
            
        Returns:
            EnsemblePrediction with detailed confidence and uncertainty metrics
        """
        try:
            # Get predictions from individual models
            model_predictions = self._get_individual_predictions(signal, market_conditions)
            
            if len(model_predictions) < self.ensemble_config['min_models_for_ensemble']:
                self.logger.warning(f"Insufficient models for ensemble ({len(model_predictions)}), using fallback")
                return self._apply_fallback_mechanism(signal, market_conditions, "insufficient_models")
            
            # Calculate model weights based on recent performance
            model_weights = self._calculate_dynamic_weights(
                model_predictions, 
                signal.regime_context.regime_type
            )
            
            # Apply ensemble method
            if ensemble_method not in self.ensemble_methods:
                ensemble_method = 'weighted_average'
                self.logger.warning(f"Unknown ensemble method, using {ensemble_method}")
            
            ensemble_result = self.ensemble_methods[ensemble_method](
                model_predictions, model_weights, signal, market_conditions
            )
            
            # Calculate confidence and uncertainty
            confidence = self._calculate_ensemble_confidence(
                model_predictions, model_weights, ensemble_result
            )
            
            uncertainty = self._calculate_prediction_uncertainty(
                model_predictions, model_weights
            )
            
            # Calculate quality metrics
            consensus_level = self._calculate_consensus_level(model_predictions)
            prediction_quality = self._calculate_prediction_quality(
                ensemble_result, confidence, uncertainty, consensus_level
            )
            
            # Check if fallback is needed based on quality
            if (confidence < self.ensemble_config['confidence_threshold'] or 
                uncertainty > self.ensemble_config['uncertainty_threshold'] or
                consensus_level < self.ensemble_config['consensus_threshold']):
                
                self.logger.info("Low quality ensemble prediction, applying fallback")
                return self._apply_fallback_mechanism(
                    signal, market_conditions, 
                    f"low_quality: conf={confidence:.3f}, unc={uncertainty:.3f}, cons={consensus_level:.3f}"
                )
            
            # Create ensemble prediction result
            prediction = EnsemblePrediction(
                prediction=ensemble_result,
                confidence=confidence,
                uncertainty=uncertainty,
                model_predictions=model_predictions,
                model_weights=model_weights,
                model_confidences={
                    model_type: self.model_trackers[model_type].recent_accuracy
                    for model_type in model_predictions.keys()
                    if model_type in self.model_trackers
                },
                ensemble_method=ensemble_method,
                fallback_used=False,
                prediction_quality=prediction_quality,
                consensus_level=consensus_level,
                market_regime=signal.regime_context.regime_type
            )
            
            self.logger.debug(
                f"Ensemble prediction: {ensemble_result:.3f} "
                f"(confidence: {confidence:.3f}, uncertainty: {uncertainty:.3f})"
            )
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"Error in ensemble prediction: {str(e)}")
            return self._apply_fallback_mechanism(signal, market_conditions, f"error: {str(e)}")
    
    def update_model_performance(
        self, 
        model_type: ModelType, 
        prediction: float, 
        actual_outcome: bool,
        regime: Optional[RegimeType] = None
    ) -> None:
        """Update performance tracking for a specific model."""
        if model_type not in self.model_trackers:
            self.model_trackers[model_type] = ModelPerformanceTracker(model_type)
        
        tracker = self.model_trackers[model_type]
        tracker.update_performance(prediction, actual_outcome)
        
        # Update regime-specific performance
        if regime:
            if regime not in tracker.regime_performance:
                tracker.regime_performance[regime] = 0.5
            
            # Update with exponential moving average
            alpha = 0.1
            accuracy = 1.0 if (prediction > 0.5) == actual_outcome else 0.0
            tracker.regime_performance[regime] = (
                alpha * accuracy + (1 - alpha) * tracker.regime_performance[regime]
            )
    
    def get_model_performance_summary(self) -> Dict[ModelType, Dict[str, Any]]:
        """Get performance summary for all tracked models."""
        summary = {}
        
        for model_type, tracker in self.model_trackers.items():
            summary[model_type] = {
                'recent_accuracy': tracker.recent_accuracy,
                'long_term_accuracy': tracker.long_term_accuracy,
                'calibration_score': tracker.calibration_score,
                'consistency_score': tracker.consistency_score,
                'performance_trend': tracker.performance_trend,
                'prediction_count': tracker.prediction_count,
                'regime_performance': dict(tracker.regime_performance),
                'dynamic_weight': tracker.get_dynamic_weight(),
                'last_updated': tracker.last_updated
            }
        
        return summary
    
    def _get_individual_predictions(
        self, 
        signal: AdaptiveSignal, 
        market_conditions: Dict[str, Any]
    ) -> Dict[ModelType, float]:
        """Get predictions from all available individual models."""
        predictions = {}
        
        # Get available models from ML engine
        available_models = getattr(self.ml_engine, 'models', {})
        
        # Prepare features for prediction
        features = self._prepare_prediction_features(signal, market_conditions)
        
        for model_type, model in available_models.items():
            if model_type == ModelType.ENSEMBLE:
                continue  # Skip ensemble model to avoid recursion
            
            try:
                # Call model directly to avoid circular dependency
                if hasattr(model, 'predict_proba'):
                    prediction = model.predict_proba([features])[0][1]
                elif hasattr(model, 'predict'):
                    prediction = float(model.predict([features])[0])
                else:
                    self.logger.warning(f"Model {model_type.value} has no predict method")
                    continue
                
                predictions[model_type] = max(0.0, min(1.0, prediction))
                
                self.logger.debug(f"Model {model_type.value} prediction: {prediction:.3f}")
                
            except Exception as e:
                self.logger.warning(f"Failed to get prediction from {model_type.value}: {str(e)}")
                continue
        
        return predictions
    
    def _prepare_prediction_features(self, signal: AdaptiveSignal, market_conditions: Dict[str, Any]) -> List[float]:
        """Prepare features for prediction from signal and market conditions."""
        # Use the ML engine's feature preparation method if available
        if hasattr(self.ml_engine, '_prepare_prediction_features'):
            return self.ml_engine._prepare_prediction_features(signal, market_conditions)
        
        # Fallback feature preparation
        features = []
        
        # Signal features
        features.extend([
            signal.confidence,
            signal.ml_confidence,
            signal.strength.value,
            signal.regime_context.confidence,
            signal.regime_context.volatility_level,
            signal.regime_context.trend_strength,
            signal.regime_context.momentum
        ])
        
        # Market condition features
        if 'rsi' in market_conditions:
            features.append(market_conditions['rsi'])
        else:
            features.append(50.0)  # Neutral RSI
        
        if 'volatility' in market_conditions:
            features.append(market_conditions['volatility'])
        else:
            features.append(0.02)  # Default volatility
        
        # Pad or truncate to match expected feature count
        expected_features = len(getattr(self.ml_engine, 'feature_columns', {}).get('default', []))
        if expected_features > 0:
            while len(features) < expected_features:
                features.append(0.0)
            features = features[:expected_features]
        
        return features
    
    def _calculate_dynamic_weights(
        self, 
        model_predictions: Dict[ModelType, float],
        current_regime: RegimeType
    ) -> Dict[ModelType, float]:
        """Calculate dynamic weights for models based on performance."""
        weights = {}
        total_weight = 0.0
        
        for model_type in model_predictions.keys():
            if model_type not in self.model_trackers:
                self.model_trackers[model_type] = ModelPerformanceTracker(model_type)
            
            tracker = self.model_trackers[model_type]
            
            # Base weight from recent performance
            base_weight = tracker.get_dynamic_weight()
            
            # Adjust for regime-specific performance
            if (self.ensemble_config['regime_weight_adjustment'] and 
                current_regime in tracker.regime_performance):
                regime_performance = tracker.regime_performance[current_regime]
                regime_adjustment = regime_performance / 0.5  # Normalize around 0.5
                base_weight *= regime_adjustment
            
            weights[model_type] = max(0.1, base_weight)  # Minimum weight
            total_weight += weights[model_type]
        
        # Normalize weights
        if total_weight > 0:
            for model_type in weights:
                weights[model_type] /= total_weight
        else:
            # Equal weights if no performance data
            equal_weight = 1.0 / len(model_predictions)
            weights = {model_type: equal_weight for model_type in model_predictions.keys()}
        
        return weights
    
    def _weighted_average_ensemble(
        self, 
        predictions: Dict[ModelType, float],
        weights: Dict[ModelType, float],
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> float:
        """Simple weighted average ensemble method."""
        weighted_sum = sum(predictions[model_type] * weights[model_type] 
                          for model_type in predictions.keys())
        return weighted_sum
    
    def _confidence_weighted_ensemble(
        self, 
        predictions: Dict[ModelType, float],
        weights: Dict[ModelType, float],
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> float:
        """Ensemble method that weights by model confidence."""
        confidence_weights = {}
        total_confidence_weight = 0.0
        
        for model_type in predictions.keys():
            if model_type in self.model_trackers:
                confidence = self.model_trackers[model_type].calibration_score
                confidence_weight = weights[model_type] * confidence
                confidence_weights[model_type] = confidence_weight
                total_confidence_weight += confidence_weight
        
        if total_confidence_weight == 0:
            return self._weighted_average_ensemble(predictions, weights, signal, market_conditions)
        
        # Normalize confidence weights
        for model_type in confidence_weights:
            confidence_weights[model_type] /= total_confidence_weight
        
        # Calculate confidence-weighted prediction
        weighted_sum = sum(predictions[model_type] * confidence_weights[model_type] 
                          for model_type in predictions.keys())
        return weighted_sum
    
    def _stacking_ensemble(
        self, 
        predictions: Dict[ModelType, float],
        weights: Dict[ModelType, float],
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> float:
        """Stacking ensemble using a meta-learner (simplified version)."""
        # For now, use a simple linear combination
        # In a full implementation, this would use a trained meta-model
        
        # Apply non-linear transformation to predictions
        transformed_predictions = {}
        for model_type, pred in predictions.items():
            # Apply sigmoid-like transformation to emphasize extreme predictions
            transformed = 1 / (1 + np.exp(-5 * (pred - 0.5)))
            transformed_predictions[model_type] = transformed
        
        # Weighted average of transformed predictions
        weighted_sum = sum(transformed_predictions[model_type] * weights[model_type] 
                          for model_type in predictions.keys())
        return weighted_sum
    
    def _bayesian_model_averaging(
        self, 
        predictions: Dict[ModelType, float],
        weights: Dict[ModelType, float],
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> float:
        """Bayesian model averaging ensemble method."""
        # Calculate posterior probabilities based on model performance
        posterior_weights = {}
        
        for model_type in predictions.keys():
            if model_type in self.model_trackers:
                tracker = self.model_trackers[model_type]
                # Use accuracy as likelihood
                likelihood = tracker.recent_accuracy
                # Use base weight as prior
                prior = weights[model_type]
                # Posterior proportional to likelihood * prior
                posterior_weights[model_type] = likelihood * prior
            else:
                posterior_weights[model_type] = weights[model_type]
        
        # Normalize posterior weights
        total_posterior = sum(posterior_weights.values())
        if total_posterior > 0:
            for model_type in posterior_weights:
                posterior_weights[model_type] /= total_posterior
        
        # Calculate BMA prediction
        bma_prediction = sum(predictions[model_type] * posterior_weights[model_type] 
                           for model_type in predictions.keys())
        return bma_prediction
    
    def _calculate_ensemble_confidence(
        self, 
        predictions: Dict[ModelType, float],
        weights: Dict[ModelType, float],
        ensemble_prediction: float
    ) -> float:
        """Calculate confidence in the ensemble prediction."""
        if not predictions:
            return 0.0
        
        # Factor 1: Agreement between models (inverse of variance)
        pred_values = list(predictions.values())
        prediction_variance = np.var(pred_values)
        agreement_score = 1.0 / (1.0 + prediction_variance)
        
        # Factor 2: Individual model confidences
        model_confidence_scores = []
        for model_type in predictions.keys():
            if model_type in self.model_trackers:
                model_confidence_scores.append(self.model_trackers[model_type].calibration_score)
        
        avg_model_confidence = np.mean(model_confidence_scores) if model_confidence_scores else 0.5
        
        # Factor 3: Prediction extremeness (more extreme predictions are more confident)
        extremeness = abs(ensemble_prediction - 0.5) * 2  # 0 to 1 scale
        
        # Factor 4: Number of models (more models = more confidence)
        model_count_factor = min(1.0, len(predictions) / 5.0)  # Cap at 5 models
        
        # Combine factors
        confidence = (
            agreement_score * 0.3 +
            avg_model_confidence * 0.3 +
            extremeness * 0.2 +
            model_count_factor * 0.2
        )
        
        return max(0.0, min(1.0, confidence))
    
    def _calculate_prediction_uncertainty(
        self, 
        predictions: Dict[ModelType, float],
        weights: Dict[ModelType, float]
    ) -> float:
        """Calculate uncertainty in the ensemble prediction."""
        if len(predictions) < 2:
            return 0.5  # High uncertainty with few models
        
        # Weighted variance of predictions
        pred_values = list(predictions.values())
        weight_values = [weights[model_type] for model_type in predictions.keys()]
        
        weighted_mean = np.average(pred_values, weights=weight_values)
        weighted_variance = np.average((pred_values - weighted_mean)**2, weights=weight_values)
        
        # Normalize uncertainty to 0-1 scale
        uncertainty = min(1.0, weighted_variance * 4)  # Scale factor
        
        return uncertainty
    
    def _calculate_consensus_level(self, predictions: Dict[ModelType, float]) -> float:
        """Calculate the level of consensus among models."""
        if len(predictions) < 2:
            return 1.0  # Perfect consensus with one model
        
        pred_values = list(predictions.values())
        
        # Calculate pairwise agreement
        agreements = []
        for i, pred1 in enumerate(pred_values):
            for pred2 in pred_values[i+1:]:
                # Agreement based on how close predictions are
                agreement = 1.0 - abs(pred1 - pred2)
                agreements.append(agreement)
        
        return np.mean(agreements) if agreements else 0.0
    
    def _calculate_prediction_quality(
        self, 
        prediction: float,
        confidence: float,
        uncertainty: float,
        consensus: float
    ) -> float:
        """Calculate overall prediction quality score."""
        # Combine multiple quality factors
        quality = (
            confidence * 0.4 +
            (1.0 - uncertainty) * 0.3 +
            consensus * 0.3
        )
        
        return max(0.0, min(1.0, quality))
    
    def _apply_fallback_mechanism(
        self, 
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any],
        reason: str
    ) -> EnsemblePrediction:
        """Apply fallback mechanism when ensemble prediction fails or is low quality."""
        self.logger.info(f"Applying fallback mechanism: {reason}")
        
        # Try fallback strategies in order
        for fallback_strategy in self.fallback_strategies:
            try:
                fallback_prediction = fallback_strategy(signal, market_conditions)
                if fallback_prediction is not None:
                    return EnsemblePrediction(
                        prediction=fallback_prediction,
                        confidence=0.3,  # Lower confidence for fallback
                        uncertainty=0.5,  # Higher uncertainty
                        fallback_used=True,
                        fallback_reason=reason,
                        ensemble_method="fallback",
                        prediction_quality=0.3,
                        consensus_level=1.0,  # Single prediction
                        market_regime=signal.regime_context.regime_type
                    )
            except Exception as e:
                self.logger.warning(f"Fallback strategy failed: {str(e)}")
                continue
        
        # Ultimate fallback - conservative neutral prediction
        return EnsemblePrediction(
            prediction=self.ensemble_config['fallback_prediction'],
            confidence=0.1,
            uncertainty=0.9,
            fallback_used=True,
            fallback_reason=f"{reason} - all fallbacks failed",
            ensemble_method="conservative_fallback",
            prediction_quality=0.1,
            consensus_level=1.0,
            market_regime=signal.regime_context.regime_type
        )
    
    def _technical_analysis_fallback(
        self, 
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> Optional[float]:
        """Fallback based on technical analysis indicators."""
        try:
            # Use signal strength and confidence as base
            base_prediction = 0.5 + (signal.strength.value - 0.6) * signal.confidence
            
            # Adjust based on market conditions
            if 'rsi' in market_conditions:
                rsi = market_conditions['rsi']
                if rsi > 70:  # Overbought
                    base_prediction *= 0.8 if signal.signal_type == 'buy' else 1.2
                elif rsi < 30:  # Oversold
                    base_prediction *= 1.2 if signal.signal_type == 'buy' else 0.8
            
            return max(0.0, min(1.0, base_prediction))
            
        except Exception as e:
            self.logger.warning(f"Technical analysis fallback failed: {str(e)}")
            return None
    
    def _regime_based_fallback(
        self, 
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> Optional[float]:
        """Fallback based on market regime characteristics."""
        try:
            regime = signal.regime_context.regime_type
            
            # Base prediction on regime and signal type
            if regime == RegimeType.TRENDING_BULL and signal.signal_type == 'buy':
                return 0.7
            elif regime == RegimeType.TRENDING_BEAR and signal.signal_type == 'sell':
                return 0.7
            elif regime == RegimeType.RANGING:
                return 0.5  # Neutral in ranging markets
            elif regime == RegimeType.HIGH_VOLATILITY:
                return 0.4  # Lower confidence in volatile markets
            else:
                return 0.5
                
        except Exception as e:
            self.logger.warning(f"Regime-based fallback failed: {str(e)}")
            return None
    
    def _historical_average_fallback(
        self, 
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> Optional[float]:
        """Fallback based on historical average performance."""
        try:
            # Use overall model performance as fallback
            if self.model_trackers:
                avg_performance = np.mean([
                    tracker.long_term_accuracy 
                    for tracker in self.model_trackers.values()
                ])
                return avg_performance
            else:
                return 0.5
                
        except Exception as e:
            self.logger.warning(f"Historical average fallback failed: {str(e)}")
            return None
    
    def _conservative_fallback(
        self, 
        signal: AdaptiveSignal,
        market_conditions: Dict[str, Any]
    ) -> Optional[float]:
        """Conservative fallback - always returns neutral prediction."""
        return self.ensemble_config['fallback_prediction']
    
    def _initialize_model_trackers(self) -> None:
        """Initialize performance trackers for all model types."""
        for model_type in ModelType:
            if model_type != ModelType.ENSEMBLE:  # Don't track ensemble itself
                self.model_trackers[model_type] = ModelPerformanceTracker(model_type)