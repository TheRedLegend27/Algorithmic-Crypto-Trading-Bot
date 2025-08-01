"""
Unit tests for the manual controls system.
"""
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from bot.adaptive.manual_controls import (
    OverrideType, ControlAction, ManualOverride, EmergencyStop,
    DiagnosticInfo, ManualControlSystem
)
from bot.adaptive.enums import RegimeType


class TestManualOverride:
    """Test ManualOverride functionality."""
    
    def test_override_creation(self):
        """Test creating a manual override."""
        override = ManualOverride(
            override_id="test_override",
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE,
            parameters={"strategy_name": "momentum", "enabled": True},
            reason="Testing strategy override"
        )
        
        assert override.override_id == "test_override"
        assert override.override_type == OverrideType.STRATEGY_SELECTION
        assert override.action == ControlAction.ENABLE
        assert override.parameters["strategy_name"] == "momentum"
        assert override.reason == "Testing strategy override"
        assert not override.is_active
        assert not override.is_expired
    
    def test_override_validity(self):
        """Test override validity checking."""
        # Valid override without expiration
        override = ManualOverride(
            override_id="test_override",
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE
        )
        assert override.is_valid()
        
        # Valid override with future expiration
        future_time = datetime.now() + timedelta(hours=1)
        override = ManualOverride(
            override_id="test_override",
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE,
            expires_at=future_time
        )
        assert override.is_valid()
        
        # Invalid override with past expiration
        past_time = datetime.now() - timedelta(hours=1)
        override = ManualOverride(
            override_id="test_override",
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE,
            expires_at=past_time
        )
        assert not override.is_valid()
        assert override.is_expired
    
    def test_override_application(self):
        """Test applying an override."""
        override = ManualOverride(
            override_id="test_override",
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE
        )
        
        assert override.apply()
        assert override.is_active
        assert override.applied_at is not None
        
        # Cannot apply expired override
        override.is_expired = True
        override.is_active = False
        override.applied_at = None
        
        assert not override.apply()
        assert not override.is_active
        assert override.applied_at is None
    
    def test_override_deactivation(self):
        """Test deactivating an override."""
        override = ManualOverride(
            override_id="test_override",
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE
        )
        
        override.apply()
        assert override.is_active
        
        override.deactivate()
        assert not override.is_active


class TestEmergencyStop:
    """Test EmergencyStop functionality."""
    
    def test_emergency_stop_creation(self):
        """Test creating an emergency stop."""
        emergency_stop = EmergencyStop()
        
        assert not emergency_stop.is_active
        assert emergency_stop.triggered_at is None
        assert emergency_stop.trigger_reason == ""
        assert emergency_stop.manual_reset_required
    
    def test_emergency_stop_trigger(self):
        """Test triggering emergency stop."""
        emergency_stop = EmergencyStop()
        
        emergency_stop.trigger("Test emergency")
        
        assert emergency_stop.is_active
        assert emergency_stop.triggered_at is not None
        assert emergency_stop.trigger_reason == "Test emergency"
    
    def test_emergency_stop_reset(self):
        """Test resetting emergency stop."""
        emergency_stop = EmergencyStop()
        
        emergency_stop.trigger("Test emergency")
        assert emergency_stop.is_active
        
        emergency_stop.reset()
        assert not emergency_stop.is_active
        assert emergency_stop.triggered_at is None
        assert emergency_stop.trigger_reason == ""
    
    def test_auto_reset_logic(self):
        """Test auto-reset logic."""
        # Emergency stop without auto-reset
        emergency_stop = EmergencyStop(auto_reset_after_hours=None)
        emergency_stop.trigger("Test emergency")
        
        assert not emergency_stop.should_auto_reset()
        
        # Emergency stop with auto-reset in future
        emergency_stop = EmergencyStop(auto_reset_after_hours=1)
        emergency_stop.trigger("Test emergency")
        
        assert not emergency_stop.should_auto_reset()
        
        # Emergency stop with auto-reset in past
        emergency_stop = EmergencyStop(auto_reset_after_hours=1)
        emergency_stop.trigger("Test emergency")
        emergency_stop.triggered_at = datetime.now() - timedelta(hours=2)
        
        assert emergency_stop.should_auto_reset()


class TestDiagnosticInfo:
    """Test DiagnosticInfo functionality."""
    
    def test_diagnostic_info_creation(self):
        """Test creating diagnostic info."""
        diagnostics = DiagnosticInfo()
        
        assert diagnostics.timestamp is not None
        assert diagnostics.system_status == "unknown"
        assert isinstance(diagnostics.component_status, dict)
        assert diagnostics.memory_usage_mb == 0.0
        assert diagnostics.cpu_usage_pct == 0.0
        assert diagnostics.active_positions == 0
        assert isinstance(diagnostics.recent_errors, list)


class TestManualControlSystem:
    """Test ManualControlSystem functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.control_system = ManualControlSystem(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test control system initialization."""
        assert Path(self.temp_dir).exists()
        assert self.control_system.overrides_file.parent.exists()
        assert self.control_system.emergency_stop_file.parent.exists()
    
    def test_create_strategy_override(self):
        """Test creating strategy override."""
        override_id = self.control_system.create_strategy_override(
            strategy_name="momentum",
            enabled=False,
            duration_hours=2,
            reason="Testing strategy disable"
        )
        
        assert override_id is not None
        
        override = self.control_system.get_override(override_id)
        assert override is not None
        assert override.override_type == OverrideType.STRATEGY_SELECTION
        assert override.action == ControlAction.DISABLE
        assert override.parameters["strategy_name"] == "momentum"
        assert override.parameters["enabled"] is False
        assert override.is_active
        assert override.expires_at is not None
    
    def test_create_parameter_override(self):
        """Test creating parameter override."""
        parameters = {"stop_loss_pct": 0.02, "take_profit_pct": 0.04}
        
        override_id = self.control_system.create_parameter_override(
            component="risk_manager",
            parameters=parameters,
            duration_hours=1,
            reason="Testing parameter override"
        )
        
        assert override_id is not None
        
        override = self.control_system.get_override(override_id)
        assert override is not None
        assert override.override_type == OverrideType.PARAMETER_OVERRIDE
        assert override.parameters["component"] == "risk_manager"
        assert override.parameters["parameters"] == parameters
        assert override.is_active
    
    def test_pause_and_resume_adaptations(self):
        """Test pausing and resuming adaptations."""
        # Pause adaptations
        override_id = self.control_system.pause_adaptations(
            duration_hours=1,
            reason="Testing adaptation pause"
        )
        
        assert override_id is not None
        
        override = self.control_system.get_override(override_id)
        assert override is not None
        assert override.override_type == OverrideType.ADAPTATION_PAUSE
        assert override.action == ControlAction.PAUSE
        assert override.is_active
        
        # Resume adaptations
        success = self.control_system.resume_adaptations(
            reason="Testing adaptation resume"
        )
        
        assert success
        
        # Original pause override should be deactivated
        override = self.control_system.get_override(override_id)
        assert not override.is_active
        
        # Should have a resume override
        active_overrides = self.control_system.get_active_overrides()
        resume_overrides = [
            o for o in active_overrides 
            if o.override_type == OverrideType.ADAPTATION_PAUSE and o.action == ControlAction.RESUME
        ]
        assert len(resume_overrides) > 0
    
    def test_emergency_stop_trigger_and_reset(self):
        """Test emergency stop trigger and reset."""
        # Trigger emergency stop
        success = self.control_system.trigger_emergency_stop("Test emergency")
        assert success
        
        emergency_status = self.control_system.get_emergency_stop_status()
        assert emergency_status.is_active
        assert emergency_status.trigger_reason == "Test emergency"
        
        # Should have emergency stop override
        active_overrides = self.control_system.get_active_overrides()
        emergency_overrides = [
            o for o in active_overrides 
            if o.override_type == OverrideType.EMERGENCY_STOP
        ]
        assert len(emergency_overrides) > 0
        
        # Reset emergency stop
        success = self.control_system.reset_emergency_stop("Test reset")
        assert success
        
        emergency_status = self.control_system.get_emergency_stop_status()
        assert not emergency_status.is_active
        
        # Emergency stop overrides should be deactivated
        active_overrides = self.control_system.get_active_overrides()
        emergency_overrides = [
            o for o in active_overrides 
            if o.override_type == OverrideType.EMERGENCY_STOP and o.is_active
        ]
        assert len(emergency_overrides) == 0
    
    def test_rollback_adaptation(self):
        """Test rolling back an adaptation."""
        adaptation_id = "test_adaptation_123"
        
        success = self.control_system.rollback_adaptation(
            adaptation_id=adaptation_id,
            reason="Testing rollback"
        )
        
        assert success
        
        active_overrides = self.control_system.get_active_overrides()
        rollback_overrides = [
            o for o in active_overrides 
            if (o.override_type == OverrideType.PARAMETER_OVERRIDE and 
                o.action == ControlAction.ROLLBACK and
                o.parameters.get("adaptation_id") == adaptation_id)
        ]
        assert len(rollback_overrides) > 0
    
    def test_override_market_regime(self):
        """Test overriding market regime."""
        override_id = self.control_system.override_market_regime(
            regime=RegimeType.HIGH_VOLATILITY,
            duration_hours=2,
            reason="Testing regime override"
        )
        
        assert override_id is not None
        
        override = self.control_system.get_override(override_id)
        assert override is not None
        assert override.override_type == OverrideType.REGIME_OVERRIDE
        assert override.parameters["regime"] == RegimeType.HIGH_VOLATILITY.value
        assert override.is_active
        assert override.expires_at is not None
    
    def test_override_risk_parameters(self):
        """Test overriding risk parameters."""
        risk_params = {
            "max_position_size_usd": 500.0,
            "max_daily_loss_pct": 0.03
        }
        
        override_id = self.control_system.override_risk_parameters(
            risk_params=risk_params,
            duration_hours=1,
            reason="Testing risk override"
        )
        
        assert override_id is not None
        
        override = self.control_system.get_override(override_id)
        assert override is not None
        assert override.override_type == OverrideType.RISK_OVERRIDE
        assert override.parameters["risk_params"] == risk_params
        assert override.is_active
    
    def test_get_active_overrides(self):
        """Test getting active overrides."""
        # Create some overrides
        override_id1 = self.control_system.create_strategy_override(
            strategy_name="momentum",
            enabled=False,
            reason="Test 1"
        )
        
        override_id2 = self.control_system.create_parameter_override(
            component="risk_manager",
            parameters={"stop_loss_pct": 0.02},
            reason="Test 2"
        )
        
        active_overrides = self.control_system.get_active_overrides()
        assert len(active_overrides) == 2
        
        override_ids = [o.override_id for o in active_overrides]
        assert override_id1 in override_ids
        assert override_id2 in override_ids
    
    def test_deactivate_override(self):
        """Test deactivating an override."""
        override_id = self.control_system.create_strategy_override(
            strategy_name="momentum",
            enabled=False,
            reason="Test override"
        )
        
        # Verify override is active
        override = self.control_system.get_override(override_id)
        assert override.is_active
        
        # Deactivate override
        success = self.control_system.deactivate_override(
            override_id=override_id,
            reason="Test deactivation"
        )
        
        assert success
        
        # Verify override is deactivated
        override = self.control_system.get_override(override_id)
        assert not override.is_active
    
    def test_get_system_diagnostics(self):
        """Test getting system diagnostics."""
        diagnostics = self.control_system.get_system_diagnostics()
        
        assert isinstance(diagnostics, DiagnosticInfo)
        assert diagnostics.system_status == "normal"
        assert isinstance(diagnostics.component_status, dict)
        
        # Create an override and check status changes
        self.control_system.pause_adaptations(reason="Test")
        
        diagnostics = self.control_system.get_system_diagnostics()
        assert diagnostics.system_status == "adaptations_paused"
        
        # Trigger emergency stop and check status
        self.control_system.trigger_emergency_stop("Test emergency")
        
        diagnostics = self.control_system.get_system_diagnostics()
        assert diagnostics.system_status == "emergency_stop"
    
    def test_control_callbacks(self):
        """Test control event callbacks."""
        callback_called = False
        callback_data = None
        
        def test_callback(data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = data
        
        # Add callback
        self.control_system.add_control_callback("override_created", test_callback)
        
        # Create override to trigger callback
        override_id = self.control_system.create_strategy_override(
            strategy_name="momentum",
            enabled=False,
            reason="Test callback"
        )
        
        assert callback_called
        assert callback_data is not None
        assert callback_data["override_id"] == override_id
        
        # Remove callback
        self.control_system.remove_control_callback("override_created", test_callback)
        
        callback_called = False
        self.control_system.create_parameter_override(
            component="test",
            parameters={"test": "value"},
            reason="Test callback removal"
        )
        
        assert not callback_called
    
    def test_state_persistence(self):
        """Test that state is persisted and loaded correctly."""
        # Create some overrides
        override_id1 = self.control_system.create_strategy_override(
            strategy_name="momentum",
            enabled=False,
            reason="Test persistence"
        )
        
        self.control_system.trigger_emergency_stop("Test emergency persistence")
        
        # Create new control system instance
        new_control_system = ManualControlSystem(self.temp_dir)
        
        # Check that overrides were loaded
        loaded_override = new_control_system.get_override(override_id1)
        assert loaded_override is not None
        assert loaded_override.override_type == OverrideType.STRATEGY_SELECTION
        assert loaded_override.is_active
        
        # Check that emergency stop was loaded
        emergency_status = new_control_system.get_emergency_stop_status()
        assert emergency_status.is_active
        assert emergency_status.trigger_reason == "Test emergency persistence"
    
    def test_expired_override_cleanup(self):
        """Test that expired overrides are cleaned up."""
        # Create override with past expiration
        past_time = datetime.now() - timedelta(hours=1)
        
        override = ManualOverride(
            override_id="expired_override",
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE,
            expires_at=past_time
        )
        
        override.apply()
        self.control_system._active_overrides[override.override_id] = override
        
        # Get active overrides should clean up expired ones
        active_overrides = self.control_system.get_active_overrides()
        
        # Override should be deactivated
        assert not override.is_active
        assert override.is_expired
        
        # Should not be in active overrides
        active_ids = [o.override_id for o in active_overrides]
        assert "expired_override" not in active_ids
    
    @patch('json.load')
    def test_load_state_error_handling(self, mock_json_load):
        """Test error handling during state loading."""
        mock_json_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        # Create dummy state files
        overrides_file = Path(self.temp_dir) / "manual_overrides.json"
        overrides_file.write_text("invalid json")
        
        emergency_file = Path(self.temp_dir) / "emergency_stop.json"
        emergency_file.write_text("invalid json")
        
        # Should not crash on invalid JSON
        control_system = ManualControlSystem(self.temp_dir)
        assert len(control_system._active_overrides) == 0
        assert not control_system._emergency_stop.is_active


if __name__ == "__main__":
    pytest.main([__file__])