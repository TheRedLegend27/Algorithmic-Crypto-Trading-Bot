"""
Demo script showing how to use the manual controls system.
"""
import time
from datetime import datetime, timedelta
from bot.adaptive.manual_controls import ManualControlSystem
from bot.adaptive.enums import RegimeType


def main():
    """Demonstrate manual controls functionality."""
    print("=== Manual Controls System Demo ===\n")
    
    # Initialize the control system
    control_system = ManualControlSystem("demo_config")
    
    # 1. Strategy Override Demo
    print("1. Creating strategy override...")
    override_id = control_system.create_strategy_override(
        strategy_name="momentum",
        enabled=False,
        duration_hours=2,
        reason="Demo: Disabling momentum strategy for testing"
    )
    print(f"   Created override: {override_id}")
    
    # 2. Parameter Override Demo
    print("\n2. Creating parameter override...")
    risk_params = {
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04,
        "max_position_size_usd": 500.0
    }
    param_override_id = control_system.create_parameter_override(
        component="risk_manager",
        parameters=risk_params,
        duration_hours=1,
        reason="Demo: Testing conservative risk parameters"
    )
    print(f"   Created parameter override: {param_override_id}")
    
    # 3. Show active overrides
    print("\n3. Active overrides:")
    active_overrides = control_system.get_active_overrides()
    for override in active_overrides:
        print(f"   - {override.override_id}: {override.override_type.value} ({override.reason})")
    
    # 4. Pause adaptations demo
    print("\n4. Pausing adaptations...")
    pause_id = control_system.pause_adaptations(
        duration_hours=1,
        reason="Demo: Pausing adaptations for system maintenance"
    )
    print(f"   Paused adaptations: {pause_id}")
    
    # 5. Market regime override demo
    print("\n5. Overriding market regime...")
    regime_override_id = control_system.override_market_regime(
        regime=RegimeType.HIGH_VOLATILITY,
        duration_hours=2,
        reason="Demo: Forcing high volatility regime for testing"
    )
    print(f"   Regime override: {regime_override_id}")
    
    # 6. System diagnostics
    print("\n6. System diagnostics:")
    diagnostics = control_system.get_system_diagnostics()
    print(f"   System status: {diagnostics.system_status}")
    print(f"   Timestamp: {diagnostics.timestamp}")
    print("   Component status:")
    for component, status in diagnostics.component_status.items():
        print(f"     - {component}: {status}")
    
    # 7. Emergency stop demo
    print("\n7. Triggering emergency stop...")
    control_system.trigger_emergency_stop("Demo: Testing emergency stop functionality")
    
    emergency_status = control_system.get_emergency_stop_status()
    print(f"   Emergency stop active: {emergency_status.is_active}")
    print(f"   Trigger reason: {emergency_status.trigger_reason}")
    
    # 8. Show updated diagnostics
    print("\n8. Updated system diagnostics after emergency stop:")
    diagnostics = control_system.get_system_diagnostics()
    print(f"   System status: {diagnostics.system_status}")
    
    # 9. Reset emergency stop
    print("\n9. Resetting emergency stop...")
    control_system.reset_emergency_stop("Demo: Resetting emergency stop after testing")
    
    emergency_status = control_system.get_emergency_stop_status()
    print(f"   Emergency stop active: {emergency_status.is_active}")
    
    # 10. Resume adaptations
    print("\n10. Resuming adaptations...")
    success = control_system.resume_adaptations("Demo: Resuming adaptations after maintenance")
    print(f"    Resume successful: {success}")
    
    # 11. Rollback adaptation demo
    print("\n11. Rolling back an adaptation...")
    rollback_success = control_system.rollback_adaptation(
        adaptation_id="demo_adaptation_123",
        reason="Demo: Rolling back test adaptation"
    )
    print(f"    Rollback initiated: {rollback_success}")
    
    # 12. Deactivate specific override
    print("\n12. Deactivating specific override...")
    deactivate_success = control_system.deactivate_override(
        override_id=param_override_id,
        reason="Demo: Manual deactivation of parameter override"
    )
    print(f"    Deactivation successful: {deactivate_success}")
    
    # 13. Final active overrides
    print("\n13. Final active overrides:")
    active_overrides = control_system.get_active_overrides()
    for override in active_overrides:
        print(f"   - {override.override_id}: {override.override_type.value}")
        print(f"     Action: {override.action.value}")
        print(f"     Active: {override.is_active}")
        print(f"     Expires: {override.expires_at}")
        print(f"     Reason: {override.reason}")
        print()
    
    # 14. Callback demo
    print("14. Setting up control callbacks...")
    
    def on_override_created(data):
        print(f"    Callback: Override created - {data['override_id']} ({data['override_type']})")
    
    def on_emergency_stop(data):
        print(f"    Callback: Emergency stop triggered - {data['reason']}")
    
    control_system.add_control_callback("override_created", on_override_created)
    control_system.add_control_callback("emergency_stop", on_emergency_stop)
    
    # Create an override to trigger callback
    test_override_id = control_system.create_strategy_override(
        strategy_name="test_strategy",
        enabled=True,
        reason="Demo: Testing callback functionality"
    )
    
    print(f"\n15. Demo completed successfully!")
    print(f"    Total overrides created: {len(control_system._override_history)}")
    print(f"    Active overrides: {len(control_system.get_active_overrides())}")


if __name__ == "__main__":
    main()