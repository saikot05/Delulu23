import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from schemas import OptimizationRequest, OptimizationResponse
from llm_interpreter import interpret_operator_notes
from guardrails import validate_interpretations
from optimizer import optimize_energy

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="GridWise API Shell")

# Custom exception for LLM provider failures
class ProviderUnavailableError(Exception):
    def __init__(self, message: str = "LLM Provider is currently unavailable"):
        self.message = message
        super().__init__(self.message)

@app.middleware("http")
async def latency_logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000

    # Structured log, explicitly avoiding payload and header logging for security
    logger.info(
        f"method={request.method} path={request.url.path} "
        f"status_code={response.status_code} latency_ms={process_time_ms:.2f}"
    )
    return response

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Strict Secure Error Handling: Clean 400
    return JSONResponse(
        status_code=400,
        content={"detail": "Validation error", "errors": exc.errors()},
    )

@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_exception_handler(request: Request, exc: ProviderUnavailableError):
    # Maps LLM failures cleanly
    logger.error(f"Provider error: {exc.message}")
    return JSONResponse(
        status_code=503,
        content={"detail": exc.message}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Strict Secure Error Handling: Safe 500 without leaking stack traces or secrets
    logger.error("An internal error occurred during request processing.", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
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
    except ValueError as ve:
        logger.warning(f"Infeasible constraints: {ve}")
        return JSONResponse(
            status_code=422,
            content={"detail": "Infeasible energy scenario: conflicting constraints."}
        )
    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute an optimization plan for this scenario.")
