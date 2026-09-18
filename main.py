import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from schemas import OptimizationRequest, OptimizationResponse
from llm_interpreter import interpret_operator_notes
from guardrails import validate_interpretations
from optimizer import optimize_energy

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GridWise LLM Smart Campus Energy Optimization Challenge")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid JSON payload or schema mismatch", "errors": exc.errors()},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )

@app.post("/optimize-energy", response_model=OptimizationResponse)
def optimize_energy_endpoint(request: OptimizationRequest):
    try:
        # Step 1: Interpret operator notes using LLM
        raw_interpretations = interpret_operator_notes(
            request.operator_notes, 
            request.battery.capacity_kwh
        )
        
        # Step 2: Guardrails to validate interpretations deterministically
        validated_interpretations = validate_interpretations(
            raw_interpretations, 
            len(request.operator_notes),
            request.battery.capacity_kwh
        )
        
        # Step 3: Perform Linear Programming Optimization
        hourly_plan, total_grid, total_cost, peak_grid = optimize_energy(
            request, 
            validated_interpretations
        )
        
        # Step 4: Formatting Response
        summary = f"Optimization successful. Total Cost: {total_cost} BDT. Total Grid usage: {total_grid} kWh. Peak grid load: {peak_grid} kWh."
        
        response = OptimizationResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=validated_interpretations,
            hourly_plan=hourly_plan,
            total_grid_kwh=total_grid,
            total_cost_bdt=total_cost,
            peak_grid_kwh=peak_grid,
            plan_summary=summary
        )
        
        return response
    
    except ValueError as ve:
        logger.warning(f"Validation or Optimization Error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Internal Error in optimize_energy_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during optimization")
