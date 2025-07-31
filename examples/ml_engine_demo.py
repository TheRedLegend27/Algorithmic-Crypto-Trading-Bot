#!/usr/bin/env python3
"""
Demo script for the ML Engine functionality.

This script demonstrates how to use the ML Engine for:
- Feature engineering from market data
- Training machine learning models
- Making predictions on trading signals
- Model persistence and loading
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.adaptive.ml_engine import MLEngine, FeatureEngineer
from bot.adaptive.data_models import AdaptiveSignal, MarketRegime
from bot.adaptive.enums import ModelType, RegimeType, SignalStrength


def create_sample_market_data(periods=1000):
    """Create sample market data for demonstration."""
    print("Creating sample market data...")
    
    dates = pd.date_range(start='2023-01-01', periods=periods, freq='1h')
    np.random.seed(42)
    
    # Create realistic price data with trends and volatility
    base_price = 100
    price_changes = np.random.randn(periods) * 0.02  # 2% volatility
    trend = np.linspace(0, 0.5, periods)  # Gradual upward trend
    
    prices = base_price * np.exp(np.cumsum(price_changes + trend/periods))
    
    market_data = pd.DataFrame({
        'open': prices,
        'high': prices * (1 + np.random.rand(periods) * 0.01),
        'low': prices * (1 - np.random.rand(periods) * 0.01),
        'close': prices * (1 + (np.random.randn(periods) * 0.005)),
        'volume': np.random.randint(1000, 10000, periods)
    }, index=dates)
    
    # Ensure OHLC consistency
    market_data['high'] = market_data[['open', 'high', 'close']].max(axis=1)
    market_data['low'] = market_data[['open', 'low', 'close']].min(axis=1)
    
    print(f"Created market data with {len(market_data)} periods")
    print(f"Price range: ${market_data['close'].min():.2f} - ${market_data['close'].max():.2f}")
    
    return market_data


def create_sample_trade_outcomes(market_data, num_trades=100):
    """Create sample trade outcomes for training."""
    print(f"Creating {num_trades} sample trade outcomes...")
    
    trade_outcomes = []
    
    # Sample random timestamps from the market data
    sample_indices = np.random.choice(len(market_data), num_trades, replace=False)
    
    for i, idx in enumerate(sample_indices):
        timestamp = market_data.index[idx]
        
        # Create somewhat realistic profit/loss based on market conditions
        # Higher volatility periods tend to have more extreme outcomes
        if idx > 20:  # Ensure we have enough data for volatility calculation
            recent_volatility = market_data['close'].iloc[idx-20:idx].pct_change().std()
            base_profit = np.random.randn() * 50  # Base random profit/loss
            volatility_factor = recent_volatility * 1000  # Scale volatility
            profit = base_profit * (1 + volatility_factor)
        else:
            profit = np.random.randn() * 50
        
        trade_outcomes.append({
            'timestamp': timestamp,
            'profit': profit,
            'signal_type': 'buy' if np.random.rand() > 0.5 else 'sell',
            'pair': 'BTCUSD'
        })
    
    profitable_trades = sum(1 for trade in trade_outcomes if trade['profit'] > 0)
    print(f"Generated {profitable_trades}/{num_trades} profitable trades ({profitable_trades/num_trades*100:.1f}%)")
    
    return trade_outcomes


def demonstrate_feature_engineering():
    """Demonstrate the feature engineering capabilities."""
    print("\n" + "="*60)
    print("FEATURE ENGINEERING DEMONSTRATION")
    print("="*60)
    
    # Create sample data
    market_data = create_sample_market_data(200)
    
    # Initialize feature engineer
    feature_engineer = FeatureEngineer()
    
    # Create technical features
    print("\nCreating technical features...")
    technical_features = feature_engineer.create_technical_features(market_data)
    print(f"Created {len(technical_features.columns)} technical features")
    
    # Show some sample features
    feature_sample = technical_features[['returns', 'rsi_14', 'macd', 'bb_position', 'volatility_20']].tail()
    print("\nSample technical features:")
    print(feature_sample.round(4))
    
    # Create market structure features
    print("\nCreating market structure features...")
    market_features = feature_engineer.create_market_structure_features(technical_features)
    print(f"Created {len(market_features.columns)} market structure features")
    
    # Show sample market structure features
    structure_sample = market_features[['trend_strength', 'volatility_regime', 'trend_regime']].tail()
    print("\nSample market structure features:")
    print(structure_sample)
    
    return market_data, technical_features


def demonstrate_model_training():
    """Demonstrate ML model training."""
    print("\n" + "="*60)
    print("MODEL TRAINING DEMONSTRATION")
    print("="*60)
    
    # Create sample data
    market_data = create_sample_market_data(500)
    trade_outcomes = create_sample_trade_outcomes(market_data, 50)
    
    # Initialize ML engine
    ml_engine = MLEngine(model_storage_path="demo_models")
    
    # Train models
    print("\nTraining ML models...")
    ml_engine.train_models(market_data, trade_outcomes)
    
    # Show model information
    print("\nTrained models:")
    for model_type in ml_engine.models:
        metadata = ml_engine.model_metadata[model_type]
        confidence = ml_engine.get_model_confidence(model_type)
        print(f"  {model_type.value}:")
        print(f"    Training accuracy: {metadata.training_accuracy:.3f}")
        print(f"    Validation accuracy: {metadata.validation_accuracy:.3f}")
        print(f"    Current confidence: {confidence:.3f}")
        print(f"    Features used: {len(metadata.features_used)}")
    
    # Show feature importance for Random Forest
    if ModelType.RANDOM_FOREST in ml_engine.models:
        importance = ml_engine.get_feature_importance(ModelType.RANDOM_FOREST)
        if importance:
            print(f"\nTop 10 most important features (Random Forest):")
            sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
            for feature, score in sorted_features:
                print(f"  {feature}: {score:.4f}")
    
    return ml_engine


def demonstrate_predictions():
    """Demonstrate making predictions with trained models."""
    print("\n" + "="*60)
    print("PREDICTION DEMONSTRATION")
    print("="*60)
    
    # Train a model first
    market_data = create_sample_market_data(300)
    trade_outcomes = create_sample_trade_outcomes(market_data, 30)
    
    ml_engine = MLEngine(model_storage_path="demo_models")
    ml_engine.train_models(market_data, trade_outcomes)
    
    # Create sample signals for prediction
    print("\nMaking predictions on sample trading signals...")
    
    sample_signals = [
        {
            'regime': RegimeType.TRENDING_BULL,
            'signal_strength': SignalStrength.STRONG,
            'confidence': 0.8,
            'market_conditions': {'rsi': 65, 'volatility': 0.02, 'volume': 5000}
        },
        {
            'regime': RegimeType.RANGING,
            'signal_strength': SignalStrength.MODERATE,
            'confidence': 0.6,
            'market_conditions': {'rsi': 45, 'volatility': 0.01, 'volume': 3000}
        },
        {
            'regime': RegimeType.HIGH_VOLATILITY,
            'signal_strength': SignalStrength.WEAK,
            'confidence': 0.4,
            'market_conditions': {'rsi': 80, 'volatility': 0.05, 'volume': 8000}
        }
    ]
    
    for i, signal_data in enumerate(sample_signals, 1):
        # Create market regime
        regime = MarketRegime(
            regime_type=signal_data['regime'],
            confidence=0.8,
            volatility_level=signal_data['market_conditions']['volatility'],
            trend_strength=0.5,
            momentum=0.3,
            detected_at=datetime.now()
        )
        
        # Create adaptive signal
        signal = AdaptiveSignal(
            pair='BTCUSD',
            signal_type='buy',
            strength=signal_data['signal_strength'],
            confidence=signal_data['confidence'],
            price=100.0,
            timestamp=datetime.now(),
            regime_context=regime,
            ml_confidence=0.7
        )
        
        # Make prediction
        prediction = ml_engine.predict_trade_outcome(signal, signal_data['market_conditions'])
        
        print(f"\nSignal {i}:")
        print(f"  Regime: {signal_data['regime'].value}")
        print(f"  Strength: {signal_data['signal_strength'].value}")
        print(f"  Market conditions: {signal_data['market_conditions']}")
        print(f"  Predicted success probability: {prediction:.3f}")
        
        # Interpret the prediction
        if prediction > 0.7:
            recommendation = "STRONG BUY"
        elif prediction > 0.6:
            recommendation = "BUY"
        elif prediction > 0.4:
            recommendation = "HOLD"
        else:
            recommendation = "AVOID"
        
        print(f"  Recommendation: {recommendation}")


def demonstrate_model_persistence():
    """Demonstrate model saving and loading."""
    print("\n" + "="*60)
    print("MODEL PERSISTENCE DEMONSTRATION")
    print("="*60)
    
    # Train and save models
    print("Training and saving models...")
    market_data = create_sample_market_data(200)
    trade_outcomes = create_sample_trade_outcomes(market_data, 20)
    
    ml_engine1 = MLEngine(model_storage_path="demo_models")
    ml_engine1.train_models(market_data, trade_outcomes)
    
    print(f"Saved {len(ml_engine1.models)} models to disk")
    
    # Load models in a new instance
    print("\nLoading models in new ML engine instance...")
    ml_engine2 = MLEngine(model_storage_path="demo_models")
    
    print(f"Loaded {len(ml_engine2.models)} models from disk")
    
    # Verify models work the same
    regime = MarketRegime(
        regime_type=RegimeType.TRENDING_BULL,
        confidence=0.8,
        volatility_level=0.02,
        trend_strength=0.5,
        momentum=0.3,
        detected_at=datetime.now()
    )
    
    signal = AdaptiveSignal(
        pair='BTCUSD',
        signal_type='buy',
        strength=SignalStrength.STRONG,
        confidence=0.8,
        price=100.0,
        timestamp=datetime.now(),
        regime_context=regime,
        ml_confidence=0.7
    )
    
    market_conditions = {'rsi': 65, 'volatility': 0.02}
    
    pred1 = ml_engine1.predict_trade_outcome(signal, market_conditions)
    pred2 = ml_engine2.predict_trade_outcome(signal, market_conditions)
    
    print(f"\nPrediction from original engine: {pred1:.6f}")
    print(f"Prediction from loaded engine: {pred2:.6f}")
    print(f"Predictions match: {abs(pred1 - pred2) < 1e-10}")


def cleanup_demo_files():
    """Clean up demo files."""
    import shutil
    if os.path.exists("demo_models"):
        shutil.rmtree("demo_models")
        print("\nCleaned up demo model files")


def main():
    """Run the ML engine demonstration."""
    print("ML ENGINE DEMONSTRATION")
    print("="*60)
    print("This demo shows the capabilities of the adaptive trading bot's ML engine.")
    print("It includes feature engineering, model training, predictions, and persistence.")
    
    try:
        # Run demonstrations
        demonstrate_feature_engineering()
        demonstrate_model_training()
        demonstrate_predictions()
        demonstrate_model_persistence()
        
        print("\n" + "="*60)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nThe ML engine is ready for integration with the adaptive trading system.")
        print("Key capabilities demonstrated:")
        print("  ✓ Feature engineering from market data")
        print("  ✓ Training multiple ML model types")
        print("  ✓ Making predictions on trading signals")
        print("  ✓ Model persistence and loading")
        print("  ✓ Feature importance analysis")
        print("  ✓ Model confidence scoring")
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cleanup_demo_files()


if __name__ == "__main__":
    main()