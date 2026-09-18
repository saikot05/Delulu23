from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class HourEntry(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    demand: float = Field(..., ge=0)
    solar: float = Field(..., ge=0)
    tariff: float = Field(..., ge=0)

class Battery(BaseModel):
    capacity: float = Field(..., ge=0)
    initial: float = Field(..., ge=0)
    min: float = Field(..., ge=0)
    max_charge: float = Field(..., ge=0)
    max_discharge: float = Field(..., ge=0)

class OptimizationRequest(BaseModel):
    scenario_id: str
    operator_notes: List[str] = Field(..., min_length=1, max_length=3)
    hours: List[HourEntry] = Field(..., min_length=24, max_length=24)
    battery: Battery

class StructuredAdjustment(BaseModel):
    hours: List[int]
    value: Optional[float] = None

class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: Literal[
        "solar_reduction", 
        "minimum_battery_reserve", 
        "no_charge_window", 
        "no_discharge_window", 
        "max_grid_window", 
        "no_op"
    ]
    structured_adjustment: Optional[StructuredAdjustment] = None
    explanation: str

class HourlyPlan(BaseModel):
    hour: int
    grid_kwh: float
    solar_used_kwh: float
    battery_action: Literal["charge", "discharge", "idle"]
    battery_kwh: float
    battery_energy_after_kwh: float

class OptimizationResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlan]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
