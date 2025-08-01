"""
Integration tests for adaptation validation and rollback system.

This module tests the complete workflow of adaptation validation,
A/B testing, and rollback functionality in realistic scenarios.
"""
import unittest
from datetime import datetime, timedelta
import uuid
import time

from bot.adaptive.adaptation_controller import AdaptationController, AdaptationLimits
from bot.adaptive.data_models import AdaptationEvent, PerformanceMetrics
from bot.adaptive.enums import AdaptationType, RegimeType


class TestAdaptationValidationRollbackIntegration(unittest.TestCase):
    """Integration test cases for adaptation validation and rollback system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.limits = AdaptationLimits(
            min_performance_threshold=-0.05,
            min_confidence_threshold=0.6,
            max_adaptations_per_hour=5,
            max_adaptations_per_day=20
        )
        
        self.controller = AdaptationController(limits=self.limits)
    
    def test_complete_validation_workflow(self):
        """Test complete validation workflow from creation to recommendation."""
        # Create a realistic adaptation event
        adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Performance degradation detected in momentum strategy",
            changes_made={
                'parameters': {
                    'stop_loss': 0.025,  # 2.5% stop loss
                    'take_profit': 0.045,  # 4.5% take profit
                    'position_size_multiplier': 0.8  # Reduce position size
                },
                'confidence': 0.75
            },
            expected_impact=0.03,
            affected_strategies=['momentum', 'breakout'],
            affected_pairs=['BTC/USD', 'ETH/USD'],
            market_conditions={
                'volatility': 0.18,
                'trend_strength': 0.25,
                'liquidity': 0.85,
                'regime': 'ranging'
            }
        )
        
        # Step 1: Validate the adaptation
        validation_result = self.controller.validate_adaptation_impact(adaptation)
        
        # Verify validation structure
        self.assertIn('validation_id', validation_result)
        self.assertIn('overall_score', validation_result)
        self.assertIn('recommendation', validation_result)
        self.assertIn('risk_level', validation_result)
        
        # Check all validation checks were performed
        expected_checks = [
            'risk_assessment', 'performance_simulation', 'resource_impact',
            'conflict_detection', 'market_suitability', 'historical_analysis'
        ]
        
        for check in expected_checks:
            self.assertIn(check, validation_result['checks'])
        
        print(f"Validation completed: Score={validation_result['overall_score']:.3f}, "
              f"Risk={validation_result['risk_level']}, "
              f"Recommendation={validation_result['recommendation']}")
        
        # Step 2: Based on recommendation, proceed with appropriate action
        recommendation = validation_result['recommendation']
        
        if recommendation == 'approve':
            # Direct approval - execute adaptation
            success = self.controller.execute_adaptation(adaptation)
            self.assertTrue(success)
            print("Adaptation approved and executed directly")
            
        elif recommendation == 'approve_with_ab_test':
            # Create and run A/B test
            test_id = self.controller.create_ab_test(adaptation)
            self.assertIsNotNone(test_id)
            
            start_success = self.controller.start_ab_test(test_id)
            self.assertTrue(start_success)
            
            # Simulate some trade data
            self._simulate_ab_test_trades(test_id, 20)
            
            # Analyze results
            ab_results = self.controller.analyze_ab_test(test_id)
            self.assertIn('recommendation', ab_results)
            
            print(f"A/B test completed: Winner={ab_results.get('winner', 'none')}, "
                  f"Recommendation={ab_results['recommendation']}")
            
        elif recommendation == 'reject':
            print("Adaptation rejected based on validation")
            
        else:  # approve_with_monitoring
            # Execute with enhanced monitoring
            success = self.controller.execute_adaptation(adaptation)
            self.assertTrue(success)
            print("Adaptation approved with monitoring")
    
    def test_rollback_workflow(self):
        """Test complete rollback workflow."""
        # Create adaptation that will be rolled back
        adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.STRATEGY_REBALANCING,
            trigger_reason="Strategy rebalancing for better performance",
            changes_made={
                'strategy_weights': {
                    'momentum': 0.6,
                    'mean_reversion': 0.3,
                    'arbitrage': 0.1
                }
            },
            expected_impact=0.02,
            affected_strategies=['momentum', 'mean_reversion', 'arbitrage'],
            rollback_data={
                'previous_strategy_weights': {
                    'momentum': 0.4,
                    'mean_reversion': 0.4,
                    'arbitrage': 0.2
                }
            }
        )
        
        # Execute the adaptation
        self.controller.execute_adaptation(adaptation)
        self.assertIn(adaptation.event_id, self.controller.pending_adaptations)
        
        # Simulate poor performance that triggers rollback
        adaptation.actual_impact = -0.08  # 8% loss
        adaptation.success = False
        
        # Perform rollback
        rollback_success = self.controller.rollback_failed_adaptation(
            adaptation.event_id, 
            "Performance degraded by 8% after adaptation"
        )
        
        self.assertTrue(rollback_success)
        
        # Verify rollback was recorded
        self.assertEqual(len(self.controller.rollback_history), 1)
        rollback_record = self.controller.rollback_history[0]
        
        self.assertEqual(rollback_record['adaptation_id'], adaptation.event_id)
        self.assertTrue(rollback_record['success'])
        self.assertEqual(rollback_record['reason'], "Performance degraded by 8% after adaptation")
        
        # Verify adaptation state
        self.assertFalse(adaptation.success)
        self.assertFalse(adaptation.rollback_available)
        self.assertNotIn(adaptation.event_id, self.controller.pending_adaptations)
        
        # Verify rollback event was added to history
        rollback_events = [e for e in self.controller.adaptation_history 
                          if "rollback" in e.trigger_reason.lower()]
        self.assertEqual(len(rollback_events), 1)
        
        print(f"Rollback completed successfully for adaptation {adaptation.event_id}")
    
    def test_concurrent_ab_tests(self):
        """Test handling of multiple concurrent A/B tests."""
        adaptations = []
        test_ids = []
        
        # Create multiple adaptations for A/B testing
        for i in range(3):
            adaptation = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                trigger_reason=f"Test adaptation {i}",
                changes_made={
                    'parameters': {f'param_{i}': 0.1 + i * 0.01}
                },
                expected_impact=0.01,
                affected_strategies=[f'strategy_{i}']
            )
            adaptations.append(adaptation)
            
            # Create A/B test
            test_id = self.controller.create_ab_test(adaptation)
            test_ids.append(test_id)
            
            # Start the test
            self.controller.start_ab_test(test_id)
        
        # Verify all tests are running
        for test_id in test_ids:
            ab_test = self.controller.ab_tests[test_id]
            self.assertEqual(ab_test['status'], 'running')
        
        # Simulate trade data for all tests
        for test_id in test_ids:
            self._simulate_ab_test_trades(test_id, 15)
        
        # Analyze all tests
        results = []
        for test_id in test_ids:
            result = self.controller.analyze_ab_test(test_id)
            results.append(result)
        
        # Verify all analyses completed
        for result in results:
            self.assertIn('recommendation', result)
            self.assertIn('winner', result)
        
        print(f"Successfully managed {len(test_ids)} concurrent A/B tests")
    
    def test_adaptation_history_analysis(self):
        """Test comprehensive adaptation history analysis."""
        # Create a diverse set of historical adaptations
        adaptation_types = [
            AdaptationType.PARAMETER_OPTIMIZATION,
            AdaptationType.STRATEGY_REBALANCING,
            AdaptationType.EMERGENCY_ADAPTATION
        ]
        
        for i in range(15):
            adaptation = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=adaptation_types[i % len(adaptation_types)],
                trigger_reason=f"Historical adaptation {i}",
                changes_made={'test_param': i * 0.01},
                expected_impact=0.01 + (i % 3) * 0.01,
                actual_impact=0.02 if i % 4 != 0 else -0.01,  # 75% success rate
                success=i % 4 != 0,
                timestamp=datetime.now() - timedelta(days=i)
            )
            self.controller.adaptation_history.append(adaptation)
        
        # Add some rollbacks
        for i in range(3):
            rollback = {
                'rollback_id': str(uuid.uuid4()),
                'adaptation_id': f'adaptation_{i}',
                'reason': f'Rollback {i}',
                'timestamp': datetime.now() - timedelta(days=i),
                'success': True
            }
            self.controller.rollback_history.append(rollback)
        
        # Perform analysis
        analysis = self.controller.get_adaptation_history_analysis(days_back=20)
        
        # Verify analysis completeness
        expected_fields = [
            'total_adaptations', 'successful_adaptations', 'failed_adaptations',
            'rollbacks', 'average_impact', 'adaptation_types', 'success_rate_by_type',
            'insights', 'recommendations'
        ]
        
        for field in expected_fields:
            self.assertIn(field, analysis)
        
        # Verify calculations
        self.assertEqual(analysis['total_adaptations'], 15)
        self.assertEqual(analysis['successful_adaptations'], 11)  # 75% of 15, but some pending
        self.assertEqual(analysis['rollbacks'], 3)
        
        # Verify insights and recommendations are generated
        self.assertIsInstance(analysis['insights'], list)
        self.assertIsInstance(analysis['recommendations'], list)
        self.assertGreater(len(analysis['insights']), 0)
        
        print(f"History analysis completed: {analysis['total_adaptations']} adaptations, "
              f"{len(analysis['insights'])} insights, {len(analysis['recommendations'])} recommendations")
    
    def test_validation_with_conflicts(self):
        """Test validation when there are conflicting pending adaptations."""
        # Create first adaptation and make it pending
        first_adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="First adaptation",
            changes_made={
                'parameters': {'stop_loss': 0.02}
            },
            expected_impact=0.01,
            affected_strategies=['momentum']
        )
        
        self.controller.pending_adaptations[first_adaptation.event_id] = first_adaptation
        
        # Create conflicting adaptation
        conflicting_adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Conflicting adaptation",
            changes_made={
                'parameters': {'stop_loss': 0.03}  # Same parameter
            },
            expected_impact=0.02,
            affected_strategies=['momentum']  # Same strategy
        )
        
        # Validate conflicting adaptation
        validation_result = self.controller.validate_adaptation_impact(conflicting_adaptation)
        
        # Should detect conflicts
        conflict_check = validation_result['checks']['conflict_detection']
        self.assertGreater(conflict_check['conflict_count'], 0)
        self.assertFalse(conflict_check['passed'])
        
        # Overall recommendation should account for conflicts
        self.assertIn(validation_result['recommendation'], ['reject', 'approve_with_ab_test'])
        
        print(f"Conflict detection working: {conflict_check['conflict_count']} conflicts detected")
    
    def test_emergency_adaptation_workflow(self):
        """Test emergency adaptation workflow with relaxed validation."""
        # Create emergency adaptation
        emergency_adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.EMERGENCY_ADAPTATION,
            trigger_reason="Emergency response to severe market conditions",
            changes_made={
                'parameters': {
                    'stop_loss': 0.01,  # Tighter stop loss
                    'position_size_multiplier': 0.5  # Reduce position size significantly
                },
                'strategy_weights': {
                    'momentum': 0.2,  # Reduce risky strategies
                    'mean_reversion': 0.8
                },
                'confidence': 0.4  # Lower confidence due to emergency
            },
            expected_impact=-0.02,  # Expected short-term loss for risk reduction
            affected_strategies=['momentum', 'mean_reversion']
        )
        
        # Validate emergency adaptation
        validation_result = self.controller.validate_adaptation_impact(emergency_adaptation)
        
        # Emergency adaptations should have different validation criteria
        self.assertIn('emergency', emergency_adaptation.trigger_reason.lower())
        
        # Should still get a recommendation despite lower confidence
        self.assertIn(validation_result['recommendation'], 
                     ['approve', 'approve_with_monitoring', 'approve_with_ab_test', 'reject'])
        
        print(f"Emergency adaptation validation: {validation_result['recommendation']}")
    
    def _simulate_ab_test_trades(self, test_id: str, num_trades: int):
        """Simulate trade data for A/B test."""
        import random
        
        for i in range(num_trades):
            # Simulate realistic trade returns
            base_return = random.normalvariate(0.01, 0.02)  # 1% mean, 2% std
            
            trade_data = {
                'trade_id': f'trade_{test_id}_{i}',
                'return': base_return,
                'timestamp': datetime.now() - timedelta(minutes=i),
                'pair': 'BTC/USD',
                'strategy': 'test_strategy'
            }
            
            self.controller.update_ab_test(test_id, trade_data)
    
    def test_performance_degradation_detection_and_rollback(self):
        """Test automatic rollback when performance degradation is detected."""
        # Create adaptation with rollback capability
        adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Optimize parameters for better performance",
            changes_made={
                'parameters': {'risk_multiplier': 1.5}
            },
            expected_impact=0.03,
            rollback_data={'parameters': {'risk_multiplier': 1.0}},
            auto_rollback_threshold=-0.05  # Rollback if performance drops by 5%
        )
        
        # Execute adaptation
        self.controller.execute_adaptation(adaptation)
        
        # Simulate performance monitoring that detects degradation
        adaptation.actual_impact = -0.08  # 8% performance drop
        
        # Check if rollback should be triggered
        should_rollback = adaptation.should_rollback()
        self.assertTrue(should_rollback)
        
        # Perform automatic rollback
        rollback_success = self.controller.rollback_failed_adaptation(
            adaptation.event_id,
            f"Automatic rollback: performance dropped to {adaptation.actual_impact:.1%}"
        )
        
        self.assertTrue(rollback_success)
        
        # Verify rollback was properly recorded
        rollback_record = self.controller.rollback_history[-1]
        self.assertEqual(rollback_record['adaptation_id'], adaptation.event_id)
        self.assertIn('automatic rollback', rollback_record['reason'].lower())
        
        print(f"Automatic rollback triggered and executed successfully")


if __name__ == '__main__':
    # Run integration tests
    unittest.main(verbosity=2)