from typing import List
from schemas import DirectiveInterpretation, DirectiveType

def validate_interpretations(
    interpretations: List[DirectiveInterpretation],
    num_notes: int,
    battery_capacity: float
) -> List[DirectiveInterpretation]:
    """
    Deterministically validate LLM output.
    - Check note_index bounds (0..N-1)
    - Enforce valid directive types
    - Validate hour ranges (0-23, strictly ascending, unique)
    - Validate numeric ranges (solar factor 0.0-1.0, reserve <= battery capacity, max_grid >= 0)
    - If validation fails, safely fall back to `no_op`.
    """
    validated = []
    for interp in interpretations:
        is_valid = True
        
        # 1. Check note_index bounds
        if not (0 <= interp.note_index < num_notes):
            is_valid = False

        if interp.directive_type != "no_op" and is_valid:
            # Check structured adjustment presence
            if interp.structured_adjustment is None:
                is_valid = False
            else:
                sa = interp.structured_adjustment
                try:
                    hours = sa.get("hours")
                    # 2. Validate hour ranges (0-23, strictly ascending, unique)
                    if not isinstance(hours, list):
                        is_valid = False
                    else:
                        hours = [int(h) for h in hours]
                        sa["hours"] = hours
                        if not all(0 <= h <= 23 for h in hours):
                            is_valid = False
                        if sorted(list(set(hours))) != hours:
                            is_valid = False

                    # 3. Validate numeric ranges based on directive_type
                    if interp.directive_type == "solar_reduction":
                        value = sa.get("factor")
                        if value is None:
                            is_valid = False
                        else:
                            value = float(value)
                            sa["factor"] = value
                            if not (0.0 <= value <= 1.0):
                                is_valid = False
                    elif interp.directive_type == "minimum_battery_reserve":
                        value = sa.get("minimum_energy_kwh")
                        if value is None:
                            is_valid = False
                        else:
                            value = float(value)
                            sa["minimum_energy_kwh"] = value
                            if not (0.0 <= value <= battery_capacity):
                                is_valid = False
                    elif interp.directive_type == "max_grid_window":
                        value = sa.get("max_grid_kwh")
                        if value is None:
                            is_valid = False
                        else:
                            value = float(value)
                            sa["max_grid_kwh"] = value
                            if value < 0:
                                is_valid = False
                    elif interp.directive_type in ("no_charge_window", "no_discharge_window"):
                        # These shouldn't necessarily need a value, or value can be anything (we ignore it)
                        pass
                except (TypeError, ValueError):
                    is_valid = False

        # Apply fallback if invalid
        if not is_valid:
            validated.append(
                DirectiveInterpretation(
                    note_index=interp.note_index if (0 <= interp.note_index < num_notes) else 0,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation="Guardrails validation failed, falling back to no_op."
                )
            )
        else:
            validated.append(interp)
            
    # Ensure exactly one interpretation per note if needed, 
    # but currently we just return the cleaned up list.
    return validated
