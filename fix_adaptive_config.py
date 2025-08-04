#!/usr/bin/env python3
"""
Fix adaptive bot configuration issues.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.adaptive.adaptive_config import AdaptiveBotConfig

def fix_configuration():
    """Fix configuration issues in the adaptive bot."""
    print("🔧 Fixing adaptive bot configuration...")
    
    # Create a more reasonable configuration
    config = AdaptiveBotConfig()
    
    # Get current adaptation config
    adaptation_config = config.get_adaptation_config()
    
    print("Current adaptation configuration:")
    for key, value in adaptation_config.items():
        print(f"  {key}: {value}")
    
    # Recommended fixes
    fixes = {
        'adaptation_confidence_threshold': 0.6,  # Lower from 0.8 to 0.6
        'min_performance_threshold': -0.1,       # More reasonable threshold
        'max_adaptations_per_hour': 3,           # Allow more adaptations
        'min_time_between_adaptations_minutes': 15,  # Reduce from 30 to 15
    }
    
    print("\n🔧 Recommended configuration fixes:")
    for key, value in fixes.items():
        current = adaptation_config.get(key, "Not set")
        print(f"  {key}: {current} → {value}")
    
    # Update the configuration file
    config_updates = """
# Adaptive Bot Configuration Updates
# Add these to your bot/adaptive/adaptive_config.py

RECOMMENDED_ADAPTATION_CONFIG = {
    'adaptation_confidence_threshold': 0.6,  # Lower threshold for more adaptations
    'min_performance_threshold': -0.1,       # -10% performance drop triggers adaptation
    'max_adaptations_per_hour': 3,           # Allow more frequent adaptations
    'min_time_between_adaptations_minutes': 15,  # Reduce minimum time between adaptations
    'emergency_drawdown_threshold': -0.15,   # -15% drawdown triggers emergency adaptation
    'min_data_points_for_adaptation': 50,    # Reduce from 100 to 50 for faster learning
}

# Paper Trading Configuration
PAPER_TRADING_CONFIG = {
    'initial_capital': 10000.0,              # Start with $10k virtual capital
    'realistic_slippage': 0.001,             # 0.1% slippage simulation
    'realistic_fees': 0.0025,                # 0.25% trading fees
    'enable_partial_fills': True,            # Simulate partial order fills
}

# ML Engine Configuration
ML_ENGINE_CONFIG = {
    'min_training_samples': 100,             # Minimum samples before training
    'retrain_frequency_hours': 24,          # Retrain models daily
    'ensemble_confidence_threshold': 0.4,   # Lower threshold for ensemble predictions
    'online_learning_enabled': True,        # Enable continuous learning
}
"""
    
    print("\n📝 Configuration recommendations saved to adaptive_config_fixes.txt")
    with open('adaptive_config_fixes.txt', 'w') as f:
        f.write(config_updates)
    
    print("✅ Configuration analysis complete!")

if __name__ == "__main__":
    fix_configuration()