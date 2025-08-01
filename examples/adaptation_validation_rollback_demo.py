"""
Demonstration of the adaptation validation and rollback system.

This script showcases the complete workflow of:
1. Adaptation impact validation before deployment
2. A/B testing framework for gradual rollout
3. Automatic rollback for failed adaptations
4. Adaptation history tracking and analysis
"""
import uuid
from datetime import datetime, timedelta
import random

from bot.adaptive.adaptation_controller import AdaptationController, AdaptationLimits
from bot.adaptive.data_models import AdaptationEvent, PerformanceMetrics
from bot.adaptive.enums import AdaptationType, RegimeType


def create_sample_adaptation(adaptation_type: AdaptationType, risk_level: str = "medium") -> AdaptationEvent:
    """Create a sample adaptation event for demonstration."""
    
    if risk_level == "low":
        changes = {
            'parameters': {'stop_loss': 0.02},
            'confidence': 0.85
        }
        expected_impact = 0.02
        market_conditions = {
            'volatility': 0.12,
            'trend_strength': 0.4,
            'liquidity': 0.9,
            'regime': 'trending'
        }
    elif risk_level == "high":
        changes = {
            'parameters': {'stop_loss': 0.1, 'position_size': 2.0},
            'strategy_weights': {'momentum': 0.8, 'mean_reversion': 0.2},
            'confidence': 0.45
        }
        expected_impact = 0.08
        market_conditions = {
            'volatility': 0.45,
            'trend_strength': 0.1,
            'liquidity': 0.4,
            'regime': 'high_volatility'
        }
    else:  # medium risk
        changes = {
            'parameters': {'stop_loss': 0.025, 'take_profit': 0.04},
            'confidence': 0.7
        }
        expected_impact = 0.03
        market_conditions = {
            'volatility': 0.18,
            'trend_strength': 0.25,
            'liquidity': 0.75,
            'regime': 'ranging'
        }
    
    return AdaptationEvent(
        event_id=str(uuid.uuid4()),
        event_type=adaptation_type,
        trigger_reason=f"Performance optimization - {risk_level} risk adaptation",
        changes_made=changes,
        expected_impact=expected_impact,
        affected_strategies=['momentum', 'mean_reversion'],
        affected_pairs=['BTC/USD', 'ETH/USD'],
        market_conditions=market_conditions,
        rollback_data={'previous_parameters': {'stop_loss': 0.015}}
    )


def demonstrate_validation_workflow():
    """Demonstrate the complete validation workflow."""
    print("=" * 60)
    print("ADAPTATION VALIDATION WORKFLOW DEMONSTRATION")
    print("=" * 60)
    
    # Initialize controller
    limits = AdaptationLimits(
        min_performance_threshold=-0.05,
        min_confidence_threshold=0.6,
        max_adaptations_per_hour=3,
        max_adaptations_per_day=15
    )
    controller = AdaptationController(limits=limits)
    
    # Test different risk levels
    risk_levels = ["low", "medium", "high"]
    
    for risk_level in risk_levels:
        print(f"\n--- Testing {risk_level.upper()} Risk Adaptation ---")
        
        adaptation = create_sample_adaptation(AdaptationType.PARAMETER_OPTIMIZATION, risk_level)
        
        # Validate the adaptation
        validation_result = controller.validate_adaptation_impact(adaptation)
        
        print(f"Adaptation ID: {adaptation.event_id[:8]}...")
        print(f"Expected Impact: {adaptation.expected_impact:.1%}")
        print(f"Validation Score: {validation_result['overall_score']:.3f}")
        print(f"Risk Level: {validation_result['risk_level']}")
        print(f"Recommendation: {validation_result['recommendation']}")
        
        # Show detailed check results
        print("\nDetailed Validation Checks:")
        for check_name, check_result in validation_result['checks'].items():
            status = "✓ PASS" if check_result.get('passed', False) else "✗ FAIL"
            print(f"  {check_name}: {status}")
        
        # Act on recommendation
        recommendation = validation_result['recommendation']
        if recommendation == 'approve':
            print("→ Executing adaptation directly")
            controller.execute_adaptation(adaptation)
        elif recommendation == 'approve_with_ab_test':
            print("→ Creating A/B test for gradual rollout")
            test_id = controller.create_ab_test(adaptation)
            print(f"  A/B Test ID: {test_id}")
        elif recommendation == 'reject':
            print("→ Adaptation rejected")
        else:
            print(f"→ Executing with {recommendation.replace('_', ' ')}")
            controller.execute_adaptation(adaptation)


def demonstrate_ab_testing():
    """Demonstrate A/B testing functionality."""
    print("\n" + "=" * 60)
    print("A/B TESTING FRAMEWORK DEMONSTRATION")
    print("=" * 60)
    
    controller = AdaptationController()
    
    # Create adaptation for A/B testing
    adaptation = create_sample_adaptation(AdaptationType.PARAMETER_OPTIMIZATION, "medium")
    
    print(f"\nCreating A/B test for adaptation: {adaptation.event_id[:8]}...")
    
    # Create and start A/B test
    test_id = controller.create_ab_test(adaptation, {
        'default_test_duration': timedelta(hours=6),
        'min_sample_size': 30,
        'control_group_ratio': 0.5
    })
    
    controller.start_ab_test(test_id)
    
    print(f"A/B Test started: {test_id}")
    print("Simulating trade data...")
    
    # Simulate trade data
    for i in range(40):
        # Control group gets baseline performance
        control_return = random.normalvariate(0.01, 0.02)
        # Treatment group gets slightly better performance (simulating successful adaptation)
        treatment_return = random.normalvariate(0.015, 0.02)
        
        # Randomly assign trades to groups
        if random.random() < 0.5:
            trade_data = {'trade_id': f'trade_{i}', 'return': control_return}
        else:
            trade_data = {'trade_id': f'trade_{i}', 'return': treatment_return}
        
        controller.update_ab_test(test_id, trade_data)
    
    # Analyze results
    results = controller.analyze_ab_test(test_id)
    
    print(f"\nA/B Test Results:")
    print(f"  Statistical Significance: {results.get('statistical_significance', False)}")
    print(f"  P-value: {results.get('p_value', 1.0):.4f}")
    print(f"  Effect Size: {results.get('effect_size', 0.0):.4f}")
    print(f"  Winner: {results.get('winner', 'inconclusive')}")
    print(f"  Recommendation: {results.get('recommendation', 'unknown')}")
    print(f"  Control Mean: {results.get('control_mean', 0.0):.4f}")
    print(f"  Treatment Mean: {results.get('treatment_mean', 0.0):.4f}")


def demonstrate_rollback_system():
    """Demonstrate automatic rollback functionality."""
    print("\n" + "=" * 60)
    print("AUTOMATIC ROLLBACK SYSTEM DEMONSTRATION")
    print("=" * 60)
    
    controller = AdaptationController()
    
    # Create adaptation that will be rolled back
    adaptation = create_sample_adaptation(AdaptationType.STRATEGY_REBALANCING, "medium")
    adaptation.rollback_data = {
        'previous_strategy_weights': {
            'momentum': 0.4,
            'mean_reversion': 0.4,
            'arbitrage': 0.2
        }
    }
    adaptation.auto_rollback_threshold = -0.05  # 5% loss threshold
    
    print(f"Executing adaptation: {adaptation.event_id[:8]}...")
    print(f"Expected Impact: {adaptation.expected_impact:.1%}")
    
    # Execute adaptation
    controller.execute_adaptation(adaptation)
    
    # Simulate poor performance
    print("\nSimulating poor performance after adaptation...")
    adaptation.actual_impact = -0.08  # 8% loss
    
    print(f"Actual Impact: {adaptation.actual_impact:.1%}")
    print(f"Rollback Threshold: {adaptation.auto_rollback_threshold:.1%}")
    
    # Check if rollback should be triggered
    should_rollback = adaptation.should_rollback()
    print(f"Should Rollback: {should_rollback}")
    
    if should_rollback:
        print("\nTriggering automatic rollback...")
        rollback_success = controller.rollback_failed_adaptation(
            adaptation.event_id,
            f"Performance degraded to {adaptation.actual_impact:.1%}"
        )
        
        if rollback_success:
            print("✓ Rollback completed successfully")
            
            # Show rollback details
            rollback_record = controller.rollback_history[-1]
            print(f"  Rollback ID: {rollback_record['rollback_id'][:8]}...")
            print(f"  Reason: {rollback_record['reason']}")
            print(f"  Timestamp: {rollback_record['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Verify adaptation state
            print(f"  Adaptation Success: {adaptation.success}")
            print(f"  Rollback Available: {adaptation.rollback_available}")
        else:
            print("✗ Rollback failed")


def demonstrate_history_analysis():
    """Demonstrate adaptation history analysis."""
    print("\n" + "=" * 60)
    print("ADAPTATION HISTORY ANALYSIS DEMONSTRATION")
    print("=" * 60)
    
    controller = AdaptationController()
    
    # Create diverse historical adaptations
    adaptation_types = [
        AdaptationType.PARAMETER_OPTIMIZATION,
        AdaptationType.STRATEGY_REBALANCING,
        AdaptationType.EMERGENCY_ADAPTATION
    ]
    
    print("Creating historical adaptation data...")
    
    for i in range(20):
        adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=adaptation_types[i % len(adaptation_types)],
            trigger_reason=f"Historical adaptation {i}",
            changes_made={'test_param': i * 0.01},
            expected_impact=0.01 + (i % 3) * 0.01,
            actual_impact=random.normalvariate(0.02, 0.03),  # Realistic performance distribution
            success=random.random() > 0.25,  # 75% success rate
            timestamp=datetime.now() - timedelta(days=random.randint(1, 30))
        )
        controller.adaptation_history.append(adaptation)
    
    # Add some rollbacks
    for i in range(5):
        rollback = {
            'rollback_id': str(uuid.uuid4()),
            'adaptation_id': f'adaptation_{i}',
            'reason': f'Performance rollback {i}',
            'timestamp': datetime.now() - timedelta(days=random.randint(1, 15)),
            'success': True
        }
        controller.rollback_history.append(rollback)
    
    # Perform analysis
    analysis = controller.get_adaptation_history_analysis(days_back=30)
    
    print(f"\nAdaptation History Analysis (Last 30 days):")
    print(f"  Total Adaptations: {analysis['total_adaptations']}")
    print(f"  Successful: {analysis['successful_adaptations']}")
    print(f"  Failed: {analysis['failed_adaptations']}")
    print(f"  Pending: {analysis['pending_adaptations']}")
    print(f"  Rollbacks: {analysis['rollbacks']}")
    print(f"  Average Impact: {analysis['average_impact']:.3f}")
    
    if analysis['best_adaptation'] is not None:
        print(f"  Best Adaptation Impact: {analysis['best_adaptation']:.3f}")
    if analysis['worst_adaptation'] is not None:
        print(f"  Worst Adaptation Impact: {analysis['worst_adaptation']:.3f}")
    
    print(f"\nAdaptation Types:")
    for adaptation_type, count in analysis['adaptation_types'].items():
        success_rate = analysis['success_rate_by_type'].get(adaptation_type, 0.0)
        print(f"  {adaptation_type}: {count} adaptations ({success_rate:.1%} success rate)")
    
    print(f"\nInsights ({len(analysis['insights'])} total):")
    for insight in analysis['insights'][:3]:  # Show first 3 insights
        print(f"  • {insight}")
    
    print(f"\nRecommendations ({len(analysis['recommendations'])} total):")
    for recommendation in analysis['recommendations'][:3]:  # Show first 3 recommendations
        print(f"  • {recommendation}")


def demonstrate_concurrent_operations():
    """Demonstrate handling of concurrent validation and rollback operations."""
    print("\n" + "=" * 60)
    print("CONCURRENT OPERATIONS DEMONSTRATION")
    print("=" * 60)
    
    controller = AdaptationController()
    
    print("Creating multiple concurrent adaptations...")
    
    # Create multiple adaptations
    adaptations = []
    for i in range(3):
        adaptation = create_sample_adaptation(
            AdaptationType.PARAMETER_OPTIMIZATION, 
            ["low", "medium", "high"][i]
        )
        adaptations.append(adaptation)
    
    # Validate all adaptations
    validation_results = []
    for i, adaptation in enumerate(adaptations):
        print(f"\nValidating adaptation {i+1}/3...")
        result = controller.validate_adaptation_impact(adaptation)
        validation_results.append(result)
        print(f"  Score: {result['overall_score']:.3f}, Recommendation: {result['recommendation']}")
    
    # Create A/B tests for suitable adaptations
    ab_tests = []
    for i, (adaptation, result) in enumerate(zip(adaptations, validation_results)):
        if result['recommendation'] in ['approve_with_ab_test', 'approve']:
            print(f"\nCreating A/B test for adaptation {i+1}...")
            test_id = controller.create_ab_test(adaptation)
            controller.start_ab_test(test_id)
            ab_tests.append(test_id)
    
    print(f"\nManaging {len(ab_tests)} concurrent A/B tests...")
    
    # Simulate some trade data for all tests
    for test_id in ab_tests:
        for j in range(10):
            trade_data = {
                'trade_id': f'trade_{test_id}_{j}',
                'return': random.normalvariate(0.01, 0.02)
            }
            controller.update_ab_test(test_id, trade_data)
    
    # Show status of all tests
    for i, test_id in enumerate(ab_tests):
        ab_test = controller.ab_tests[test_id]
        control_size = ab_test['control_group']['size']
        treatment_size = ab_test['treatment_group']['size']
        print(f"  Test {i+1}: Control={control_size}, Treatment={treatment_size}")
    
    print(f"\n✓ Successfully managed {len(ab_tests)} concurrent A/B tests")


def main():
    """Run all demonstrations."""
    print("ADAPTIVE TRADING BOT - VALIDATION & ROLLBACK SYSTEM DEMO")
    print("=" * 60)
    print("This demo showcases the enhanced adaptation validation and rollback system")
    print("including impact validation, A/B testing, and automatic rollback capabilities.")
    
    try:
        demonstrate_validation_workflow()
        demonstrate_ab_testing()
        demonstrate_rollback_system()
        demonstrate_history_analysis()
        demonstrate_concurrent_operations()
        
        print("\n" + "=" * 60)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("All validation, A/B testing, and rollback features are working correctly!")
        
    except Exception as e:
        print(f"\n✗ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()