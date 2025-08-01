"""
Unit tests for adaptation validation and rollback system.

This module tests the enhanced validation, A/B testing, and rollback
functionality of the AdaptationController.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import uuid
import numpy as np

from bot.adaptive.adaptation_controller import AdaptationController, AdaptationLimits
from bot.adaptive.data_models import AdaptationEvent, PerformanceMetrics
from bot.adaptive.enums import AdaptationType, RegimeType


class TestAdaptationValidationRollback(unittest.TestCase):
    """Test cases for adaptation validation and rollback system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.limits = AdaptationLimits(
            min_performance_threshold=-0.05,
            min_confidence_threshold=0.6,
            max_adaptations_per_hour=2,
            max_adaptations_per_day=10
        )
        
        self.controller = AdaptationController(limits=self.limits)
        
        # Create sample adaptation event
        self.sample_adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Performance degradation detected",
            changes_made={
                'parameters': {'stop_loss': 0.02, 'take_profit': 0.04},
                'confidence': 0.75
            },
            expected_impact=0.03,
            affected_strategies=['momentum', 'mean_reversion'],
            market_conditions={
                'volatility': 0.15,
                'trend_strength': 0.3,
                'liquidity': 0.8,
                'regime': 'trending'
            }
        )
        
        # Create sample performance metrics
        self.sample_metrics = PerformanceMetrics(
            total_return=0.05,
            annualized_return=0.12,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            max_drawdown=-0.03,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=150,
            regime_performance={
                RegimeType.TRENDING_BULL: 0.08,
                RegimeType.RANGING: 0.02
            }
        )
    
    def test_validate_adaptation_impact_comprehensive(self):
        """Test comprehensive adaptation impact validation."""
        # Test successful validation
        validation_result = self.controller.validate_adaptation_impact(self.sample_adaptation)
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('validation_id', validation_result)
        self.assertIn('overall_score', validation_result)
        self.assertIn('recommendation', validation_result)
        self.assertIn('risk_level', validation_result)
        self.assertIn('checks', validation_result)
        
        # Check that all required validation checks are present
        required_checks = [
            'risk_assessment', 'performance_simulation', 'resource_impact',
            'conflict_detection', 'market_suitability', 'historical_analysis'
        ]
        
        for check in required_checks:
            self.assertIn(check, validation_result['checks'])
            self.assertIn('passed', validation_result['checks'][check])
        
        # Validation should be stored
        self.assertIn(validation_result['validation_id'], self.controller.validation_results)
    
    def test_validate_adaptation_impact_high_risk(self):
        """Test validation of high-risk adaptation."""
        # Create high-risk adaptation
        high_risk_adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.EMERGENCY_ADAPTATION,
            trigger_reason="Emergency response to severe losses",
            changes_made={
                'parameters': {'stop_loss': 0.5},  # Very large change
                'strategy_weights': {'momentum': 0.8, 'mean_reversion': 0.2}
            },
            expected_impact=-0.1,  # Negative expected impact
            affected_strategies=['momentum', 'mean_reversion', 'arbitrage', 'scalping'],
            market_conditions={'volatility': 0.6}  # High volatility
        )
        
        validation_result = self.controller.validate_adaptation_impact(high_risk_adaptation)
        
        # Should have high risk level
        self.assertEqual(validation_result['risk_level'], 'high')
        
        # Risk assessment should fail
        self.assertFalse(validation_result['checks']['risk_assessment']['passed'])
        
        # Should recommend rejection or A/B testing
        self.assertIn(validation_result['recommendation'], ['reject', 'approve_with_ab_test'])
    
    def test_create_ab_test(self):
        """Test A/B test creation."""
        test_id = self.controller.create_ab_test(self.sample_adaptation)
        
        self.assertIsInstance(test_id, str)
        self.assertIn(test_id, self.controller.ab_tests)
        
        ab_test = self.controller.ab_tests[test_id]
        self.assertEqual(ab_test['status'], 'created')
        self.assertEqual(ab_test['adaptation_id'], self.sample_adaptation.event_id)
        self.assertIn('control_group', ab_test)
        self.assertIn('treatment_group', ab_test)
        self.assertIn('results', ab_test)
    
    def test_create_ab_test_max_concurrent_limit(self):
        """Test A/B test creation with maximum concurrent limit."""
        # Create maximum number of concurrent tests
        for i in range(self.controller.ab_test_config['max_concurrent_tests']):
            adaptation = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                trigger_reason=f"Test adaptation {i}",
                changes_made={'parameters': {'test': i}},
                expected_impact=0.01
            )
            self.controller.create_ab_test(adaptation)
        
        # Attempting to create another should raise an error
        with self.assertRaises(ValueError):
            self.controller.create_ab_test(self.sample_adaptation)
    
    def test_start_ab_test(self):
        """Test starting an A/B test."""
        test_id = self.controller.create_ab_test(self.sample_adaptation)
        
        # Start the test
        success = self.controller.start_ab_test(test_id)
        self.assertTrue(success)
        
        ab_test = self.controller.ab_tests[test_id]
        self.assertEqual(ab_test['status'], 'running')
        self.assertIsNotNone(ab_test['started_at'])
        
        # Test groups should be initialized
        self.assertIn('allocation_ratio', ab_test['control_group'])
        self.assertIn('allocation_ratio', ab_test['treatment_group'])
    
    def test_start_ab_test_invalid_status(self):
        """Test starting A/B test with invalid status."""
        test_id = self.controller.create_ab_test(self.sample_adaptation)
        
        # Manually change status
        self.controller.ab_tests[test_id]['status'] = 'completed'
        
        # Should fail to start
        success = self.controller.start_ab_test(test_id)
        self.assertFalse(success)
    
    def test_update_ab_test(self):
        """Test updating A/B test with trade data."""
        test_id = self.controller.create_ab_test(self.sample_adaptation)
        self.controller.start_ab_test(test_id)
        
        # Add some trade data
        trade_data = {
            'trade_id': 'test_trade_1',
            'return': 0.02,
            'timestamp': datetime.now()
        }
        
        self.controller.update_ab_test(test_id, trade_data)
        
        ab_test = self.controller.ab_tests[test_id]
        
        # Trade should be assigned to one of the groups
        total_trades = (len(ab_test['control_group']['trades']) + 
                       len(ab_test['treatment_group']['trades']))
        self.assertEqual(total_trades, 1)
        
        # Group size should be updated
        total_size = ab_test['control_group']['size'] + ab_test['treatment_group']['size']
        self.assertEqual(total_size, 1)
    
    def test_analyze_ab_test(self):
        """Test A/B test analysis."""
        test_id = self.controller.create_ab_test(self.sample_adaptation)
        self.controller.start_ab_test(test_id)
        
        # Add trade data to both groups
        ab_test = self.controller.ab_tests[test_id]
        
        # Manually add trades to ensure we have data in both groups
        control_trades = [{'return': 0.01}, {'return': 0.02}, {'return': -0.01}]
        treatment_trades = [{'return': 0.03}, {'return': 0.04}, {'return': 0.02}]
        
        ab_test['control_group']['trades'] = control_trades
        ab_test['treatment_group']['trades'] = treatment_trades
        
        # Analyze the test
        results = self.controller.analyze_ab_test(test_id)
        
        self.assertIn('statistical_significance', results)
        self.assertIn('p_value', results)
        self.assertIn('effect_size', results)
        self.assertIn('confidence_interval', results)
        self.assertIn('winner', results)
        self.assertIn('recommendation', results)
    
    def test_rollback_failed_adaptation(self):
        """Test automatic rollback of failed adaptation."""
        # Add adaptation to history
        self.sample_adaptation.rollback_data = {'previous_parameters': {'stop_loss': 0.01}}
        self.controller.adaptation_history.append(self.sample_adaptation)
        self.controller.pending_adaptations[self.sample_adaptation.event_id] = self.sample_adaptation
        
        # Rollback the adaptation
        success = self.controller.rollback_failed_adaptation(
            self.sample_adaptation.event_id, 
            "Performance degradation"
        )
        
        self.assertTrue(success)
        
        # Check that rollback was recorded
        self.assertEqual(len(self.controller.rollback_history), 1)
        rollback_record = self.controller.rollback_history[0]
        self.assertEqual(rollback_record['adaptation_id'], self.sample_adaptation.event_id)
        self.assertEqual(rollback_record['reason'], "Performance degradation")
        self.assertTrue(rollback_record['success'])
        
        # Original adaptation should be marked as failed
        self.assertFalse(self.sample_adaptation.success)
        self.assertFalse(self.sample_adaptation.rollback_available)
        
        # Should be removed from pending adaptations
        self.assertNotIn(self.sample_adaptation.event_id, self.controller.pending_adaptations)
        
        # Rollback event should be added to history
        rollback_events = [e for e in self.controller.adaptation_history 
                          if e.event_type == AdaptationType.EMERGENCY_ADAPTATION 
                          and "rollback" in e.trigger_reason.lower()]
        self.assertEqual(len(rollback_events), 1)
    
    def test_rollback_nonexistent_adaptation(self):
        """Test rollback of non-existent adaptation."""
        success = self.controller.rollback_failed_adaptation("nonexistent_id")
        self.assertFalse(success)
        self.assertEqual(len(self.controller.rollback_history), 0)
    
    def test_rollback_unavailable_adaptation(self):
        """Test rollback of adaptation that's not available for rollback."""
        self.sample_adaptation.rollback_available = False
        self.controller.adaptation_history.append(self.sample_adaptation)
        
        success = self.controller.rollback_failed_adaptation(self.sample_adaptation.event_id)
        self.assertFalse(success)
    
    def test_get_adaptation_history_analysis(self):
        """Test adaptation history analysis."""
        # Add some sample adaptations to history
        adaptations = []
        for i in range(5):
            adaptation = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                trigger_reason=f"Test adaptation {i}",
                changes_made={'parameters': {'test': i}},
                expected_impact=0.01,
                actual_impact=0.02 if i % 2 == 0 else -0.01,
                success=i % 2 == 0,
                timestamp=datetime.now() - timedelta(days=i)
            )
            adaptations.append(adaptation)
            self.controller.adaptation_history.append(adaptation)
        
        # Add some rollbacks
        for i in range(2):
            rollback = {
                'rollback_id': str(uuid.uuid4()),
                'adaptation_id': adaptations[i].event_id,
                'reason': 'Test rollback',
                'timestamp': datetime.now() - timedelta(days=i),
                'success': True
            }
            self.controller.rollback_history.append(rollback)
        
        # Analyze history
        analysis = self.controller.get_adaptation_history_analysis(days_back=10)
        
        self.assertIn('total_adaptations', analysis)
        self.assertIn('successful_adaptations', analysis)
        self.assertIn('failed_adaptations', analysis)
        self.assertIn('rollbacks', analysis)
        self.assertIn('average_impact', analysis)
        self.assertIn('adaptation_types', analysis)
        self.assertIn('insights', analysis)
        self.assertIn('recommendations', analysis)
        
        self.assertEqual(analysis['total_adaptations'], 5)
        self.assertEqual(analysis['successful_adaptations'], 3)  # i % 2 == 0 for i in [0,1,2,3,4]
        self.assertEqual(analysis['failed_adaptations'], 2)
        self.assertEqual(analysis['rollbacks'], 2)
    
    def test_get_rollback_history(self):
        """Test getting rollback history."""
        # Add some rollbacks
        rollbacks = []
        for i in range(3):
            rollback = {
                'rollback_id': str(uuid.uuid4()),
                'adaptation_id': f'adaptation_{i}',
                'reason': f'Test rollback {i}',
                'timestamp': datetime.now() - timedelta(days=i),
                'success': True
            }
            rollbacks.append(rollback)
            self.controller.rollback_history.append(rollback)
        
        # Get recent rollbacks
        recent_rollbacks = self.controller.get_rollback_history(days_back=2)
        
        # Should get rollbacks from last 2 days (indices 0 and 1)
        self.assertEqual(len(recent_rollbacks), 2)
        
        # Get all rollbacks
        all_rollbacks = self.controller.get_rollback_history(days_back=10)
        self.assertEqual(len(all_rollbacks), 3)
    
    def test_risk_assessment(self):
        """Test adaptation risk assessment."""
        risk_assessment = self.controller._assess_adaptation_risk(self.sample_adaptation)
        
        self.assertIn('risk_score', risk_assessment)
        self.assertIn('risk_factors', risk_assessment)
        self.assertIn('risk_level', risk_assessment)
        self.assertIn('passed', risk_assessment)
        
        self.assertIsInstance(risk_assessment['risk_score'], float)
        self.assertIsInstance(risk_assessment['risk_factors'], list)
        self.assertIn(risk_assessment['risk_level'], ['low', 'medium', 'high'])
        self.assertIsInstance(risk_assessment['passed'], bool)
    
    def test_performance_simulation(self):
        """Test adaptation performance simulation."""
        simulation = self.controller._simulate_adaptation_performance(self.sample_adaptation)
        
        self.assertIn('estimated_impact', simulation)
        self.assertIn('confidence_interval', simulation)
        self.assertIn('base_impact', simulation)
        self.assertIn('adjustments', simulation)
        self.assertIn('passed', simulation)
        
        self.assertIsInstance(simulation['estimated_impact'], float)
        self.assertIsInstance(simulation['confidence_interval'], tuple)
        self.assertEqual(len(simulation['confidence_interval']), 2)
    
    def test_resource_impact_analysis(self):
        """Test resource impact analysis."""
        resource_impact = self.controller._analyze_resource_impact(self.sample_adaptation)
        
        self.assertIn('cpu_impact', resource_impact)
        self.assertIn('memory_impact', resource_impact)
        self.assertIn('total_impact', resource_impact)
        self.assertIn('passed', resource_impact)
        
        for key in ['cpu_impact', 'memory_impact', 'network_impact', 'storage_impact', 'total_impact']:
            self.assertIsInstance(resource_impact[key], float)
            self.assertGreaterEqual(resource_impact[key], 0.0)
    
    def test_conflict_detection(self):
        """Test adaptation conflict detection."""
        # Add a pending adaptation
        pending_adaptation = AdaptationEvent(
            event_id=str(uuid.uuid4()),
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason="Pending adaptation",
            changes_made={'parameters': {'stop_loss': 0.03}},
            expected_impact=0.02,
            affected_strategies=['momentum']  # Overlaps with sample_adaptation
        )
        self.controller.pending_adaptations[pending_adaptation.event_id] = pending_adaptation
        
        conflict_check = self.controller._check_adaptation_conflicts(self.sample_adaptation)
        
        self.assertIn('conflicts', conflict_check)
        self.assertIn('conflict_count', conflict_check)
        self.assertIn('conflict_severity', conflict_check)
        self.assertIn('passed', conflict_check)
        
        # Should detect strategy overlap
        self.assertGreater(conflict_check['conflict_count'], 0)
        self.assertGreater(len(conflict_check['conflicts']), 0)
    
    def test_market_condition_suitability(self):
        """Test market condition suitability assessment."""
        suitability = self.controller._assess_market_condition_suitability(self.sample_adaptation)
        
        self.assertIn('suitability_score', suitability)
        self.assertIn('suitability_factors', suitability)
        self.assertIn('market_conditions', suitability)
        self.assertIn('passed', suitability)
        
        self.assertIsInstance(suitability['suitability_score'], float)
        self.assertGreaterEqual(suitability['suitability_score'], 0.0)
        self.assertLessEqual(suitability['suitability_score'], 1.0)
    
    def test_historical_pattern_analysis(self):
        """Test historical pattern analysis."""
        # Add some historical adaptations
        for i in range(3):
            historical_adaptation = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                trigger_reason=f"Historical adaptation {i}",
                changes_made={'parameters': {'stop_loss': 0.02}},
                expected_impact=0.01,
                actual_impact=0.02 if i % 2 == 0 else -0.01,
                success=i % 2 == 0,
                affected_strategies=['momentum'],
                timestamp=datetime.now() - timedelta(days=i+1)
            )
            self.controller.adaptation_history.append(historical_adaptation)
        
        historical_analysis = self.controller._analyze_historical_patterns(self.sample_adaptation)
        
        self.assertIn('historical_success_rate', historical_analysis)
        self.assertIn('similar_adaptations_count', historical_analysis)
        self.assertIn('pattern_confidence', historical_analysis)
        self.assertIn('insights', historical_analysis)
        self.assertIn('passed', historical_analysis)
        
        self.assertGreater(historical_analysis['similar_adaptations_count'], 0)
    
    def test_validation_score_calculation(self):
        """Test validation score calculation."""
        # Create mock check results
        checks = {
            'risk_assessment': {'passed': True, 'risk_score': 0.2},
            'performance_simulation': {'passed': True, 'estimated_impact': 0.03},
            'resource_impact': {'passed': True, 'total_impact': 0.1},
            'conflict_detection': {'passed': True, 'conflict_count': 0},
            'market_suitability': {'passed': True, 'suitability_score': 0.8},
            'historical_analysis': {'passed': True, 'historical_success_rate': 0.7}
        }
        
        score = self.controller._calculate_validation_score(checks)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        
        # Should be high score since all checks passed
        self.assertGreater(score, 0.5)
    
    def test_validation_recommendation(self):
        """Test validation recommendation logic."""
        # Test high score recommendation
        validation_result = {
            'overall_score': 0.9,
            'risk_level': 'low',
            'checks': {
                'risk_assessment': {'passed': True},
                'performance_simulation': {'passed': True}
            }
        }
        
        recommendation = self.controller._make_validation_recommendation(validation_result)
        self.assertEqual(recommendation, 'approve')
        
        # Test low score recommendation
        validation_result['overall_score'] = 0.2
        validation_result['risk_level'] = 'high'
        recommendation = self.controller._make_validation_recommendation(validation_result)
        self.assertEqual(recommendation, 'reject')
        
        # Test medium score recommendation
        validation_result['overall_score'] = 0.6
        validation_result['risk_level'] = 'medium'
        recommendation = self.controller._make_validation_recommendation(validation_result)
        self.assertIn(recommendation, ['approve_with_monitoring', 'approve_with_ab_test'])
    
    def test_statistical_analysis(self):
        """Test statistical analysis of A/B test."""
        # Create mock A/B test data
        ab_test = {
            'test_id': 'test_123',
            'significance_threshold': 0.05,
            'control_group': {
                'trades': [{'return': 0.01}, {'return': 0.02}, {'return': -0.01}, {'return': 0.03}]
            },
            'treatment_group': {
                'trades': [{'return': 0.03}, {'return': 0.04}, {'return': 0.02}, {'return': 0.05}]
            }
        }
        
        results = self.controller._perform_statistical_analysis(ab_test)
        
        self.assertIn('statistical_significance', results)
        self.assertIn('p_value', results)
        self.assertIn('effect_size', results)
        self.assertIn('confidence_interval', results)
        self.assertIn('winner', results)
        self.assertIn('control_mean', results)
        self.assertIn('treatment_mean', results)
        
        # Treatment group should have higher mean
        self.assertGreater(results['treatment_mean'], results['control_mean'])
        self.assertGreater(results['effect_size'], 0)
    
    def test_ab_test_recommendation(self):
        """Test A/B test recommendation logic."""
        # Test treatment winner with significant effect
        ab_test = {
            'results': {
                'statistical_significance': True,
                'winner': 'treatment',
                'effect_size': 0.02  # 2% improvement
            }
        }
        
        recommendation = self.controller._make_ab_test_recommendation(ab_test)
        self.assertEqual(recommendation, 'deploy_treatment')
        
        # Test control winner
        ab_test['results']['winner'] = 'control'
        recommendation = self.controller._make_ab_test_recommendation(ab_test)
        self.assertEqual(recommendation, 'keep_control')
        
        # Test no significance
        ab_test['results']['statistical_significance'] = False
        recommendation = self.controller._make_ab_test_recommendation(ab_test)
        self.assertEqual(recommendation, 'no_significant_difference')
    
    def test_temporal_pattern_analysis(self):
        """Test temporal pattern analysis."""
        # Create adaptations at different times
        adaptations = []
        for i in range(10):
            adaptation = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                trigger_reason=f"Test adaptation {i}",
                changes_made={'parameters': {'test': i}},
                expected_impact=0.01,
                success=i % 3 == 0,  # Every third adaptation succeeds
                timestamp=datetime.now() - timedelta(hours=i)
            )
            adaptations.append(adaptation)
        
        patterns = self.controller._analyze_temporal_patterns(adaptations)
        
        self.assertIn('hourly_distribution', patterns)
        self.assertIn('daily_distribution', patterns)
        self.assertIn('success_by_hour', patterns)
        self.assertIn('success_by_day', patterns)
        
        # Should have data in hourly distribution
        self.assertGreater(len(patterns['hourly_distribution']), 0)
    
    def test_adaptation_insights_generation(self):
        """Test generation of adaptation insights."""
        analysis = {
            'total_adaptations': 10,
            'successful_adaptations': 8,
            'failed_adaptations': 2,
            'rollbacks': 1,
            'average_impact': 0.06,
            'success_rate_by_type': {
                'PARAMETER_OPTIMIZATION': 0.9,
                'STRATEGY_REBALANCING': 0.3
            }
        }
        
        insights = self.controller._generate_adaptation_insights(analysis, [])
        
        self.assertIsInstance(insights, list)
        self.assertGreater(len(insights), 0)
        
        # Should contain insights about high success rate and positive impact
        insight_text = ' '.join(insights).lower()
        self.assertIn('success', insight_text)
        self.assertIn('positive', insight_text)
    
    def test_adaptation_recommendations_generation(self):
        """Test generation of adaptation recommendations."""
        # Test low success rate scenario
        analysis = {
            'total_adaptations': 10,
            'successful_adaptations': 3,
            'failed_adaptations': 7,
            'rollbacks': 5,
            'average_impact': -0.02,
            'period_days': 30
        }
        
        recommendations = self.controller._generate_adaptation_recommendations(analysis)
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        # Should recommend improvements for low success rate
        recommendation_text = ' '.join(recommendations).lower()
        self.assertIn('validation', recommendation_text)


if __name__ == '__main__':
    unittest.main()