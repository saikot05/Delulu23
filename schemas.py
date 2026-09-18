from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal, Dict, Any

class HourEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    demand_kwh: float = Field(..., ge=0.0)
    solar_kwh: float = Field(..., ge=0.0)
    tariff_bdt_per_kwh: float = Field(..., ge=0.0)

class BatteryConfig(BaseModel):
    capacity_kwh: float = Field(..., ge=0.0)
    initial_energy_kwh: float = Field(..., ge=0.0)
    minimum_energy_kwh: float = Field(..., ge=0.0)
    max_charge_kwh_per_hour: float = Field(..., ge=0.0)
    max_discharge_kwh_per_hour: float = Field(..., ge=0.0)

class OptimizationRequest(BaseModel):
    scenario_id: str
    operator_notes: List[str] = Field(..., min_length=1, max_length=3, description="List of operator notes, max 3 items.")
    hours: List[HourEntry] = Field(..., min_length=24, max_length=24, description="Exactly 24 hour entries.")
    battery: BatteryConfig

DirectiveType = Literal[
    "solar_reduction", 
    "minimum_battery_reserve", 
    "no_charge_window", 
    "no_discharge_window", 
    "max_grid_window", 
    "no_op"
]

class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: Optional[Dict[str, Any]] = None
    explanation: str

    @model_validator(mode='after')
    def validate_no_op(self) -> 'DirectiveInterpretation':
        if self.directive_type == "no_op":
            if self.applies is not False:
                raise ValueError("If directive_type is no_op, applies must be False.")
            if self.structured_adjustment is not None:
                raise ValueError("If directive_type is no_op, structured_adjustment must be None.")
        else:
            if self.applies is not True:
                raise ValueError("If directive_type is not no_op, applies must be True.")
            if self.structured_adjustment is None:
                raise ValueError("If directive_type is not no_op, structured_adjustment must be provided.")
        return self

class HourlyPlanEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    grid_kwh: float
    solar_used_kwh: float
    battery_action: Literal["charge", "discharge", "idle"]
    battery_kwh: float = Field(..., description="Absolute energy (charge/discharge amount) for the hour")
    battery_energy_after_kwh: float = Field(..., description="Battery energy state at the end of the hour")

class OptimizationResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlanEntry]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
