import os
import json
from typing import List, Optional
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types
from schemas import DirectiveInterpretation, DirectiveType

class LLMStructuredAdjustment(BaseModel):
    hours: Optional[List[int]] = None
    factor: Optional[float] = None
    minimum_energy_kwh: Optional[float] = None
    max_grid_kwh: Optional[float] = None

class LLMDirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: Optional[LLMStructuredAdjustment] = None
    explanation: str

class LLMResponse(BaseModel):
    interpretations: List[LLMDirectiveInterpretation]

def _to_app_directive(item: LLMDirectiveInterpretation) -> DirectiveInterpretation:
    sa = item.structured_adjustment
    structured_adjustment = None
    if item.directive_type != "no_op" and sa is not None:
        if item.directive_type == "solar_reduction":
            structured_adjustment = {"hours": sa.hours, "factor": sa.factor}
        elif item.directive_type == "minimum_battery_reserve":
            structured_adjustment = {"hours": sa.hours, "minimum_energy_kwh": sa.minimum_energy_kwh}
        elif item.directive_type == "max_grid_window":
            structured_adjustment = {"hours": sa.hours, "max_grid_kwh": sa.max_grid_kwh}
        elif item.directive_type in ("no_charge_window", "no_discharge_window"):
            structured_adjustment = {"hours": sa.hours}
    return DirectiveInterpretation(
        note_index=item.note_index,
        applies=item.applies,
        directive_type=item.directive_type,
        structured_adjustment=structured_adjustment,
        explanation=item.explanation,
    )

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    return genai.Client(api_key=api_key)

def interpret_operator_notes(operator_notes: List[str], battery_capacity: float) -> List[DirectiveInterpretation]:
    """
    Connects to the LLM to interpret a list of human operator notes into actionable directives.
    Uses Structured Outputs for strict adherence to schemas.
    """
    if not operator_notes:
        return []

    client = get_gemini_client()

    prompt = f"""You are an AI assistant for a smart campus energy management system.
Your job is to interpret notes left by a human operator and translate them into strict operational directives.
The campus has a battery with a capacity of {battery_capacity} kWh.

Here are the notes:
"""
    for i, note in enumerate(operator_notes):
        prompt += f"Note {i}: {note}\n"

    prompt += """
For each note, output a structured interpretation. You must determine if it contains an operational directive.
Supported directive_types, and which structured_adjustment fields to fill for each (leave all other fields null):
1. "solar_reduction": e.g., "panel washing from 12 to 2 PM reduces solar by 75%" -> hours=[12, 13] (start inclusive, end exclusive), factor=0.25 (the fraction of solar efficiency that remains). Fill only `hours` and `factor`.
2. "minimum_battery_reserve": e.g., "keep at least 50 kWh reserve from 6 PM to 10 PM" -> hours=[18, 19, 20, 21], minimum_energy_kwh=50. Fill only `hours` and `minimum_energy_kwh`.
3. "no_charge_window": e.g., "do not charge battery between 8 AM and 10 AM" -> hours=[8, 9]. Fill only `hours`.
4. "no_discharge_window": e.g., "preserve battery, no discharge from 17:00 to 19:00" -> hours=[17, 18]. Fill only `hours`.
5. "max_grid_window": e.g., "limit grid usage to 100 kWh from 2 PM to 4 PM" -> hours=[14, 15], max_grid_kwh=100. Fill only `hours` and `max_grid_kwh`.
6. "no_op": Unrelated notes, e.g., "lunch was great today" -> applies=False, directive_type="no_op", structured_adjustment=None.

The `structured_adjustment` object has four optional fields: `hours`, `factor`, `minimum_energy_kwh`, `max_grid_kwh`. Only set the fields relevant to the chosen directive_type as described above; leave the rest null.

IMPORTANT:
- `hours` inside `structured_adjustment` must be a sorted list of unique integers between 0 and 23.
- If the note is irrelevant or you can't parse it, use "no_op" with applies=False and structured_adjustment=None.
- For all directive_types other than "no_op", applies must be True and structured_adjustment must be provided with the fields described above.
- Ensure note_index matches the index of the note.
"""

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMResponse,
                temperature=0.0
            ),
        )

        # Parse the JSON response manually in case response.parsed isn't auto-populated
        response_text = response.text
        parsed_data = LLMResponse.model_validate_json(response_text)
        return [_to_app_directive(item) for item in parsed_data.interpretations]
    except Exception as e:
        print(f"Error during LLM interpretation: {e}")
        # In case of any LLM failure (e.g. timeout, malformed JSON), fallback to no_op for all notes
        return [
            DirectiveInterpretation(
                note_index=i,
                applies=False,
                directive_type="no_op",
                structured_adjustment=None,
                explanation=f"Fallback due to LLM error: {str(e)}"
            )
            for i in range(len(operator_notes))
        ]
