"""
Manual override and control system for the adaptive trading bot.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import threading
from pathlib import Path

from .enums import RegimeType, AdaptationType
from .data_models import AdaptationEvent, PerformanceMetrics


logger = logging.getLogger(__name__)


class OverrideType(Enum):
    """Types of manual overrides."""
    STRATEGY_SELECTION = "strategy_selection"
    PARAMETER_OVERRIDE = "parameter_override"
    ADAPTATION_PAUSE = "adaptation_pause"
    EMERGENCY_STOP = "emergency_stop"
    REGIME_OVERRIDE = "regime_override"
    RISK_OVERRIDE = "risk_override"


class ControlAction(Enum):
    """Control actions that can be performed."""
    ENABLE = "enable"
    DISABLE = "disable"
    PAUSE = "pause"
    RESUME = "resume"
    RESET = "reset"
    ROLLBACK = "rollback"


@dataclass
class ManualOverride:
    """Represents a manual override of system behavior."""
    override_id: str
    override_type: OverrideType
    action: ControlAction
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    
    # Status
    is_active: bool = False
    is_expired: bool = False
    
    # Metadata
    reason: str = ""
    created_by: str = "manual"
    affected_components: List[str] = field(default_factory=list)
    
    # Rollback information
    original_state: Optional[Dict[str, Any]] = None
    
    def is_valid(self) -> bool:
        """Check if the override is still valid."""
        if self.is_expired:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            self.is_expired = True
            return False
        return True
    
    def apply(self) -> bool:
        """Mark the override as applied."""
        if not self.is_valid():
            return False
        self.applied_at = datetime.now()
        self.is_active = True
        return True
    
    def deactivate(self):
        """Deactivate the override."""
        self.is_active = False


@dataclass
class EmergencyStop:
    """Emergency stop configuration and state."""
    is_active: bool = False
    triggered_at: Optional[datetime] = None
    trigger_reason: str = ""
    
    # Stop conditions
    max_drawdown_pct: float = 0.1  # 10%
    max_daily_loss_pct: float = 0.05  # 5%
    consecutive_losses: int = 5
    
    # Recovery conditions
    manual_reset_required: bool = True
    auto_reset_after_hours: Optional[int] = None
    
    def trigger(self, reason: str):
        """Trigger the emergency stop."""
        self.is_active = True
        self.triggered_at = datetime.now()
        self.trigger_reason = reason
        logger.critical(f"Emergency stop triggered: {reason}")
    
    def reset(self):
        """Reset the emergency stop."""
        self.is_active = False
        self.triggered_at = None
        self.trigger_reason = ""
        logger.info("Emergency stop reset")
    
    def should_auto_reset(self) -> bool:
        """Check if emergency stop should auto-reset."""
        if not self.is_active or not self.auto_reset_after_hours:
            return False
        if not self.triggered_at:
            return False
        
        reset_time = self.triggered_at + timedelta(hours=self.auto_reset_after_hours)
        return datetime.now() >= reset_time


@dataclass
class DiagnosticInfo:
    """System diagnostic information."""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # System health
    system_status: str = "unknown"
    component_status: Dict[str, str] = field(default_factory=dict)
    
    # Performance metrics
    current_performance: Optional[PerformanceMetrics] = None
    recent_adaptations: List[AdaptationEvent] = field(default_factory=list)
    
    # Resource usage
    memory_usage_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    
    # Trading state
    active_positions: int = 0
    pending_orders: int = 0
    daily_trades: int = 0
    
    # Errors and warnings
    recent_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ManualControlSystem:
    """Manual override and control system for the adaptive bot."""
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize the manual control system.
        
        Args:
            config_dir: Directory to store control state files
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.overrides_file = self.config_dir / "manual_overrides.json"
        self.emergency_stop_file = self.config_dir / "emergency_stop.json"
        
        # State
        self._active_overrides: Dict[str, ManualOverride] = {}
        self._override_history: List[ManualOverride] = []
        self._emergency_stop = EmergencyStop()
        
        # Control callbacks
        self._control_callbacks: Dict[str, List[Callable]] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load existing state
        self._load_state()
        
        logger.info("Initialized ManualControlSystem")
    
    def create_strategy_override(self, strategy_name: str, enabled: bool, 
                               duration_hours: Optional[int] = None, 
                               reason: str = "") -> str:
        """
        Create a manual strategy selection override.
        
        Args:
            strategy_name: Name of the strategy to override
            enabled: Whether to enable or disable the strategy
            duration_hours: How long the override should last
            reason: Reason for the override
            
        Returns:
            str: Override ID
        """
        override_id = f"strategy_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        override = ManualOverride(
            override_id=override_id,
            override_type=OverrideType.STRATEGY_SELECTION,
            action=ControlAction.ENABLE if enabled else ControlAction.DISABLE,
            parameters={"strategy_name": strategy_name, "enabled": enabled},
            expires_at=expires_at,
            reason=reason,
            affected_components=["adaptive_strategy_engine"]
        )
        
        return self._add_override(override)
    
    def create_parameter_override(self, component: str, parameters: Dict[str, Any],
                                duration_hours: Optional[int] = None,
                                reason: str = "") -> str:
        """
        Create a manual parameter override.
        
        Args:
            component: Component to override parameters for
            parameters: Parameters to override
            duration_hours: How long the override should last
            reason: Reason for the override
            
        Returns:
            str: Override ID
        """
        override_id = f"params_{component}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        override = ManualOverride(
            override_id=override_id,
            override_type=OverrideType.PARAMETER_OVERRIDE,
            action=ControlAction.ENABLE,
            parameters={"component": component, "parameters": parameters},
            expires_at=expires_at,
            reason=reason,
            affected_components=[component]
        )
        
        return self._add_override(override)
    
    def pause_adaptations(self, duration_hours: Optional[int] = None, 
                         reason: str = "") -> str:
        """
        Pause all system adaptations.
        
        Args:
            duration_hours: How long to pause adaptations
            reason: Reason for pausing
            
        Returns:
            str: Override ID
        """
        override_id = f"pause_adaptations_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        override = ManualOverride(
            override_id=override_id,
            override_type=OverrideType.ADAPTATION_PAUSE,
            action=ControlAction.PAUSE,
            expires_at=expires_at,
            reason=reason,
            affected_components=["adaptation_controller", "parameter_optimizer", "ml_engine"]
        )
        
        return self._add_override(override)
    
    def resume_adaptations(self, reason: str = "") -> bool:
        """
        Resume paused adaptations.
        
        Args:
            reason: Reason for resuming
            
        Returns:
            bool: True if successful
        """
        # Find and deactivate adaptation pause overrides
        with self._lock:
            paused_overrides = [
                override for override in self._active_overrides.values()
                if (override.override_type == OverrideType.ADAPTATION_PAUSE and 
                    override.action == ControlAction.PAUSE and override.is_active)
            ]
            
            for override in paused_overrides:
                override.deactivate()
                logger.info(f"Deactivated adaptation pause override: {override.override_id}")
            
            # Create resume override
            if paused_overrides:
                override_id = f"resume_adaptations_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                resume_override = ManualOverride(
                    override_id=override_id,
                    override_type=OverrideType.ADAPTATION_PAUSE,
                    action=ControlAction.RESUME,
                    reason=reason,
                    affected_components=["adaptation_controller", "parameter_optimizer", "ml_engine"]
                )
                
                self._add_override(resume_override)
                return True
            
            return False
    
    def trigger_emergency_stop(self, reason: str) -> bool:
        """
        Trigger emergency stop.
        
        Args:
            reason: Reason for emergency stop
            
        Returns:
            bool: True if successful
        """
        with self._lock:
            self._emergency_stop.trigger(reason)
            
            # Create emergency stop override
            override_id = f"emergency_stop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            override = ManualOverride(
                override_id=override_id,
                override_type=OverrideType.EMERGENCY_STOP,
                action=ControlAction.DISABLE,
                reason=reason,
                affected_components=["all"]
            )
            
            self._add_override(override)
            self._save_emergency_stop_state()
            
            # Notify callbacks
            self._notify_callbacks("emergency_stop", {"reason": reason})
            
            return True
    
    def reset_emergency_stop(self, reason: str = "") -> bool:
        """
        Reset emergency stop.
        
        Args:
            reason: Reason for reset
            
        Returns:
            bool: True if successful
        """
        with self._lock:
            if not self._emergency_stop.is_active:
                return False
            
            self._emergency_stop.reset()
            
            # Deactivate emergency stop overrides
            emergency_overrides = [
                override for override in self._active_overrides.values()
                if override.override_type == OverrideType.EMERGENCY_STOP and override.is_active
            ]
            
            for override in emergency_overrides:
                override.deactivate()
            
            self._save_emergency_stop_state()
            
            # Notify callbacks
            self._notify_callbacks("emergency_stop_reset", {"reason": reason})
            
            return True
    
    def rollback_adaptation(self, adaptation_id: str, reason: str = "") -> bool:
        """
        Rollback a specific adaptation.
        
        Args:
            adaptation_id: ID of the adaptation to rollback
            reason: Reason for rollback
            
        Returns:
            bool: True if successful
        """
        override_id = f"rollback_{adaptation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        override = ManualOverride(
            override_id=override_id,
            override_type=OverrideType.PARAMETER_OVERRIDE,
            action=ControlAction.ROLLBACK,
            parameters={"adaptation_id": adaptation_id},
            reason=reason,
            affected_components=["adaptation_controller"]
        )
        
        override_id = self._add_override(override)
        
        # Notify callbacks
        self._notify_callbacks("rollback_adaptation", {
            "adaptation_id": adaptation_id,
            "override_id": override_id,
            "reason": reason
        })
        
        return True
    
    def override_market_regime(self, regime: RegimeType, duration_hours: int,
                             reason: str = "") -> str:
        """
        Override the detected market regime.
        
        Args:
            regime: Market regime to force
            duration_hours: How long to maintain the override
            reason: Reason for override
            
        Returns:
            str: Override ID
        """
        override_id = f"regime_{regime.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        override = ManualOverride(
            override_id=override_id,
            override_type=OverrideType.REGIME_OVERRIDE,
            action=ControlAction.ENABLE,
            parameters={"regime": regime.value},
            expires_at=expires_at,
            reason=reason,
            affected_components=["market_regime_detector", "adaptive_strategy_engine"]
        )
        
        return self._add_override(override)
    
    def override_risk_parameters(self, risk_params: Dict[str, Any],
                               duration_hours: Optional[int] = None,
                               reason: str = "") -> str:
        """
        Override risk management parameters.
        
        Args:
            risk_params: Risk parameters to override
            duration_hours: How long to maintain the override
            reason: Reason for override
            
        Returns:
            str: Override ID
        """
        override_id = f"risk_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        override = ManualOverride(
            override_id=override_id,
            override_type=OverrideType.RISK_OVERRIDE,
            action=ControlAction.ENABLE,
            parameters={"risk_params": risk_params},
            expires_at=expires_at,
            reason=reason,
            affected_components=["risk_manager"]
        )
        
        return self._add_override(override)
    
    def get_active_overrides(self) -> List[ManualOverride]:
        """Get all active overrides."""
        with self._lock:
            # Clean up expired overrides
            self._cleanup_expired_overrides()
            return [override for override in self._active_overrides.values() if override.is_active]
    
    def get_override(self, override_id: str) -> Optional[ManualOverride]:
        """Get a specific override by ID."""
        with self._lock:
            return self._active_overrides.get(override_id)
    
    def deactivate_override(self, override_id: str, reason: str = "") -> bool:
        """
        Deactivate a specific override.
        
        Args:
            override_id: ID of the override to deactivate
            reason: Reason for deactivation
            
        Returns:
            bool: True if successful
        """
        with self._lock:
            override = self._active_overrides.get(override_id)
            if not override or not override.is_active:
                return False
            
            override.deactivate()
            logger.info(f"Deactivated override {override_id}: {reason}")
            
            # Notify callbacks
            self._notify_callbacks("override_deactivated", {
                "override_id": override_id,
                "reason": reason
            })
            
            return True
    
    def get_emergency_stop_status(self) -> EmergencyStop:
        """Get emergency stop status."""
        with self._lock:
            # Check for auto-reset
            if self._emergency_stop.should_auto_reset():
                self._emergency_stop.reset()
                self._save_emergency_stop_state()
            
            return self._emergency_stop
    
    def get_system_diagnostics(self) -> DiagnosticInfo:
        """Get comprehensive system diagnostic information."""
        with self._lock:
            diagnostics = DiagnosticInfo()
            
            # System status
            if self._emergency_stop.is_active:
                diagnostics.system_status = "emergency_stop"
            elif any(o.override_type == OverrideType.ADAPTATION_PAUSE and o.is_active 
                    for o in self._active_overrides.values()):
                diagnostics.system_status = "adaptations_paused"
            elif self._active_overrides:
                diagnostics.system_status = "manual_overrides_active"
            else:
                diagnostics.system_status = "normal"
            
            # Component status (would be populated by actual system components)
            diagnostics.component_status = {
                "ml_engine": "unknown",
                "regime_detector": "unknown",
                "strategy_engine": "unknown",
                "parameter_optimizer": "unknown",
                "adaptation_controller": "unknown"
            }
            
            return diagnostics
    
    def add_control_callback(self, event_type: str, callback: Callable):
        """Add a callback for control events."""
        if event_type not in self._control_callbacks:
            self._control_callbacks[event_type] = []
        self._control_callbacks[event_type].append(callback)
    
    def remove_control_callback(self, event_type: str, callback: Callable):
        """Remove a control event callback."""
        if event_type in self._control_callbacks:
            if callback in self._control_callbacks[event_type]:
                self._control_callbacks[event_type].remove(callback)
    
    def _add_override(self, override: ManualOverride) -> str:
        """Add an override to the active list."""
        with self._lock:
            override.apply()
            self._active_overrides[override.override_id] = override
            self._override_history.append(override)
            
            # Save state
            self._save_overrides_state()
            
            # Notify callbacks
            self._notify_callbacks("override_created", {
                "override_id": override.override_id,
                "override_type": override.override_type.value,
                "action": override.action.value
            })
            
            logger.info(f"Created override {override.override_id}: {override.reason}")
            return override.override_id
    
    def _cleanup_expired_overrides(self):
        """Clean up expired overrides."""
        expired_ids = []
        for override_id, override in self._active_overrides.items():
            if not override.is_valid() and override.is_active:
                override.deactivate()
                expired_ids.append(override_id)
        
        if expired_ids:
            logger.info(f"Deactivated {len(expired_ids)} expired overrides")
    
    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]):
        """Notify registered callbacks of control events."""
        if event_type in self._control_callbacks:
            for callback in self._control_callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in control callback: {str(e)}")
    
    def _save_overrides_state(self):
        """Save overrides state to file."""
        try:
            overrides_data = []
            for override in self._active_overrides.values():
                override_dict = {
                    "override_id": override.override_id,
                    "override_type": override.override_type.value,
                    "action": override.action.value,
                    "parameters": override.parameters,
                    "created_at": override.created_at.isoformat(),
                    "expires_at": override.expires_at.isoformat() if override.expires_at else None,
                    "applied_at": override.applied_at.isoformat() if override.applied_at else None,
                    "is_active": override.is_active,
                    "is_expired": override.is_expired,
                    "reason": override.reason,
                    "created_by": override.created_by,
                    "affected_components": override.affected_components,
                    "original_state": override.original_state
                }
                overrides_data.append(override_dict)
            
            with open(self.overrides_file, 'w') as f:
                json.dump(overrides_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving overrides state: {str(e)}")
    
    def _save_emergency_stop_state(self):
        """Save emergency stop state to file."""
        try:
            emergency_data = {
                "is_active": self._emergency_stop.is_active,
                "triggered_at": self._emergency_stop.triggered_at.isoformat() if self._emergency_stop.triggered_at else None,
                "trigger_reason": self._emergency_stop.trigger_reason,
                "max_drawdown_pct": self._emergency_stop.max_drawdown_pct,
                "max_daily_loss_pct": self._emergency_stop.max_daily_loss_pct,
                "consecutive_losses": self._emergency_stop.consecutive_losses,
                "manual_reset_required": self._emergency_stop.manual_reset_required,
                "auto_reset_after_hours": self._emergency_stop.auto_reset_after_hours
            }
            
            with open(self.emergency_stop_file, 'w') as f:
                json.dump(emergency_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving emergency stop state: {str(e)}")
    
    def _load_state(self):
        """Load saved state from files."""
        self._load_overrides_state()
        self._load_emergency_stop_state()
    
    def _load_overrides_state(self):
        """Load overrides state from file."""
        try:
            if not self.overrides_file.exists():
                return
            
            with open(self.overrides_file, 'r') as f:
                overrides_data = json.load(f)
            
            for override_dict in overrides_data:
                override = ManualOverride(
                    override_id=override_dict["override_id"],
                    override_type=OverrideType(override_dict["override_type"]),
                    action=ControlAction(override_dict["action"]),
                    parameters=override_dict["parameters"],
                    created_at=datetime.fromisoformat(override_dict["created_at"]),
                    expires_at=datetime.fromisoformat(override_dict["expires_at"]) if override_dict["expires_at"] else None,
                    applied_at=datetime.fromisoformat(override_dict["applied_at"]) if override_dict["applied_at"] else None,
                    is_active=override_dict["is_active"],
                    is_expired=override_dict["is_expired"],
                    reason=override_dict["reason"],
                    created_by=override_dict["created_by"],
                    affected_components=override_dict["affected_components"],
                    original_state=override_dict["original_state"]
                )
                
                self._active_overrides[override.override_id] = override
                self._override_history.append(override)
            
            logger.info(f"Loaded {len(self._active_overrides)} overrides from state file")
            
        except Exception as e:
            logger.error(f"Error loading overrides state: {str(e)}")
    
    def _load_emergency_stop_state(self):
        """Load emergency stop state from file."""
        try:
            if not self.emergency_stop_file.exists():
                return
            
            with open(self.emergency_stop_file, 'r') as f:
                emergency_data = json.load(f)
            
            self._emergency_stop = EmergencyStop(
                is_active=emergency_data["is_active"],
                triggered_at=datetime.fromisoformat(emergency_data["triggered_at"]) if emergency_data["triggered_at"] else None,
                trigger_reason=emergency_data["trigger_reason"],
                max_drawdown_pct=emergency_data["max_drawdown_pct"],
                max_daily_loss_pct=emergency_data["max_daily_loss_pct"],
                consecutive_losses=emergency_data["consecutive_losses"],
                manual_reset_required=emergency_data["manual_reset_required"],
                auto_reset_after_hours=emergency_data["auto_reset_after_hours"]
            )
            
            logger.info("Loaded emergency stop state from file")
            
        except Exception as e:
            logger.error(f"Error loading emergency stop state: {str(e)}")