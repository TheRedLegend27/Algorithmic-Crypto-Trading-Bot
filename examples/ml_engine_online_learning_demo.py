"""
Demo script showing the online learning capabilities of the ML Engine.

This script demonstrates:
1. Training initial models
2. Making predictions with context storage
3. Updating models with trade results
4. Model drift detection
5. Model rollback functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil

from bot.adaptive.ml_engine import MLEngine
from bot.adaptive.data_models import AdaptiveSignal, MarketRegime
from bot.adaptive.enums import ModelType, RegimeType, SignalStrength


def create_sample_data():
    """Create sample market data and trade outcomes for demonstration."""
    # Create sample market data
    dates = pd.date_range(start='2023-01-01', periods=1000, freq='1h')
    np.random.seed(42)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.cumsum(np.random.randn(1000) * 100),
        'high': 0,
        'low': 0,
        'close': 0,
        'volume': np.random.randint(1000, 10000, 1000)
    })
    
    # Calculate OHLC properly
    market_data['close'] = market_data['open'] + np.random.randn(1000) * 50
    market_data['high'] = market_data[['open', 'close']].max(axis=1) + np.abs(np.random.randn(1000) * 25)
    market_data['low'] = market_data[['open', 'close']].min(axis=1) - np.abs(np.random.randn(1000) * 25)
    
    market_data.set_index('timestamp', inplace=True)
    
    # Create sample trade outcomes
    trade_outcomes = []
    for i in range(100):
        outcome = {
            'timestamp': dates[i * 10],
            'profit': np.random.randn() * 100,
            'trade_id': f'trade_{i}',
            'pair': 'BTCUSD'
        }
        outcome['actual_outcome'] = 1 if outcome['profit'] > 0 else 0
        trade_outcomes.append(outcome)
    
    return market_data, trade_outcomes


def create_sample_signal():
    """Create a sample adaptive signal for demonstration."""
    regime = MarketRegime(
        regime_type=RegimeType.TRENDING_BULL,
        confidence=0.8,
        volatility_level=0.3,
        trend_strength=0.7,
        momentum=0.6,
        detected_at=datetime.now()
    )
    
    signal = AdaptiveSignal(
        pair="BTCUSD",
        signal_type="buy",
        strength=SignalStrength.STRONG,
        confidence=0.8,
        price=50000.0,
        timestamp=datetime.now(),
        regime_context=regime,
        ml_confidence=0.7
    )
    
    return signal


def demonstrate_online_learning():
    """Demonstrate the online learning capabilities."""
    print("=== ML Engine Online Learning Demo ===\n")
    
    # Create temporary directory for models
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary model storage: {temp_dir}")
    
    try:
        # Initialize ML Engine
        ml_engine = MLEngine(model_storage_path=temp_dir)
        print("✓ ML Engine initialized")
        
        # Create sample data
        market_data, trade_outcomes = create_sample_data()
        print(f"✓ Created sample data: {len(market_data)} market data points, {len(trade_outcomes)} trade outcomes")
        
        # Train initial models
        print("\n1. Training initial models...")
        ml_engine.train_models(market_data, trade_outcomes)
        print(f"✓ Trained {len(ml_engine.models)} models")
        
        # Display model information
        for model_type, metadata in ml_engine.model_metadata.items():
            print(f"  - {model_type.value}: accuracy={metadata.validation_accuracy:.3f}, confidence={ml_engine.get_model_confidence(model_type):.3f}")
        
        # Make predictions with context storage
        print("\n2. Making predictions with context storage...")
        signal = create_sample_signal()
        market_conditions = {'rsi': 65.0, 'volatility': 0.02}
        
        prediction = ml_engine.predict_trade_outcome(signal, market_conditions)
        print(f"✓ Prediction: {prediction:.3f}")
        print(f"✓ Stored {len(ml_engine.prediction_contexts)} prediction contexts")
        
        # Simulate trade results and online learning
        print("\n3. Simulating trade results and online learning...")
        
        for i in range(10):
            # Create trade result
            trade_result = {
                'pair': 'BTCUSD',
                'timestamp': datetime.now() - timedelta(minutes=i),
                'profit': np.random.randn() * 100,
                'trade_id': f'online_trade_{i}',
                'prediction': prediction + np.random.randn() * 0.1,
                'actual_outcome': np.random.choice([0, 1])
            }
            
            # Update online
            ml_engine.update_online(trade_result)
            
            if i == 0:
                print(f"✓ First online update completed")
        
        print(f"✓ Processed {len(ml_engine.trade_results_buffer)} trade results")
        
        # Check performance history
        print("\n4. Checking model performance history...")
        for model_type in ml_engine.models:
            history = ml_engine.get_model_performance_history(model_type)
            if history:
                recent_accuracy = np.mean([entry['accuracy'] for entry in history[-5:]])
                print(f"  - {model_type.value}: {len(history)} predictions, recent accuracy: {recent_accuracy:.3f}")
        
        # Demonstrate drift detection
        print("\n5. Demonstrating drift detection...")
        for model_type in ml_engine.models:
            drift_result = ml_engine.detect_model_drift(model_type)
            print(f"  - {model_type.value}: drift_detected={drift_result['drift_detected']}, score={drift_result['drift_score']:.3f}")
            if drift_result['drift_detected']:
                print(f"    Reason: {drift_result['reason']}")
        
        # Demonstrate model backup and rollback
        print("\n6. Demonstrating model backup and rollback...")
        
        # Create backup
        ml_engine._create_model_backup()
        backup_count = len(ml_engine.model_backup)
        print(f"✓ Created model backup ({backup_count} backup entries)")
        
        # Simulate model degradation by modifying metadata
        original_accuracy = ml_engine.model_metadata[ModelType.RANDOM_FOREST].validation_accuracy
        ml_engine.model_metadata[ModelType.RANDOM_FOREST].validation_accuracy = 0.3  # Simulate poor performance
        print(f"✓ Simulated model degradation (accuracy: {original_accuracy:.3f} → 0.3)")
        
        # Rollback model
        rollback_success = ml_engine.rollback_model(ModelType.RANDOM_FOREST, 'latest')
        restored_accuracy = ml_engine.model_metadata[ModelType.RANDOM_FOREST].validation_accuracy
        print(f"✓ Model rollback {'successful' if rollback_success else 'failed'}")
        print(f"✓ Restored accuracy: {restored_accuracy:.3f}")
        
        # Show configuration
        print("\n7. Online learning configuration:")
        config = ml_engine.online_learning_config
        for key, value in config.items():
            print(f"  - {key}: {value}")
        
        print("\n=== Demo completed successfully! ===")
        
    except Exception as e:
        print(f"❌ Error during demo: {str(e)}")
        raise
    
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir)
        print(f"✓ Cleaned up temporary directory")


if __name__ == "__main__":
    demonstrate_online_learning()