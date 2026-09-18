import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from schemas import OptimizationRequest, OptimizationResponse
from llm_interpreter import interpret_operator_notes
from guardrails import validate_interpretations
from optimizer import optimize_energy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GridWise API Shell")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Validation error", "errors": exc.errors()},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )

@app.post("/optimize-energy", response_model=OptimizationResponse)
def optimize_energy_endpoint(request: OptimizationRequest):
    try:
        directives = interpret_operator_notes(request.operator_notes, request.battery.capacity_kwh)
        directives = validate_interpretations(directives, len(request.operator_notes), request.battery.capacity_kwh)
        hourly_plan, total_grid_kwh, total_cost_bdt, peak_grid_kwh = optimize_energy(request, directives)

        applied = sum(1 for d in directives if d.applies)
        plan_summary = (
            f"Optimized 24-hour schedule for scenario '{request.scenario_id}': "
            f"{applied} of {len(directives)} operator note(s) applied. "
            f"Total grid draw {total_grid_kwh} kWh, cost {total_cost_bdt} BDT, peak grid {peak_grid_kwh} kWh."
        )

        return OptimizationResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=directives,
            hourly_plan=hourly_plan,
            total_grid_kwh=total_grid_kwh,
            total_cost_bdt=total_cost_bdt,
            peak_grid_kwh=peak_grid_kwh,
            plan_summary=plan_summary
        )
    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute an optimization plan for this scenario.")
