import pulp
from typing import List, Tuple
from schemas import OptimizationRequest, DirectiveInterpretation, HourlyPlanEntry

def optimize_energy(
    request: OptimizationRequest, 
    directives: List[DirectiveInterpretation]
) -> Tuple[List[HourlyPlanEntry], float, float, float]:
    """
    Solves the 24-hour cost minimization problem using PuLP.
    Returns: (hourly_plan, total_grid_kwh, total_cost_bdt, peak_grid_kwh)
    """
    prob = pulp.LpProblem("GridWise_Energy_Optimization", pulp.LpMinimize)
    
    bat = request.battery
    capacity = bat.capacity_kwh
    initial_energy = bat.initial_energy_kwh
    min_energy = bat.minimum_energy_kwh
    max_charge = bat.max_charge_kwh_per_hour
    max_discharge = bat.max_discharge_kwh_per_hour
    
    # Process directives into hourly modifiers
    solar_factors = [1.0] * 24
    active_min_reserve = [min_energy] * 24
    charge_allowed = [True] * 24
    discharge_allowed = [True] * 24
    max_grid_limits = [float('inf')] * 24
    
    for d in directives:
        if d.directive_type == "no_op" or not d.applies or not d.structured_adjustment:
            continue

        sa = d.structured_adjustment
        hours = sa.get("hours", [])

        if d.directive_type == "solar_reduction":
            val = sa.get("factor")
            for h in hours:
                solar_factors[h] = val
        elif d.directive_type == "minimum_battery_reserve":
            val = sa.get("minimum_energy_kwh")
            for h in hours:
                active_min_reserve[h] = max(active_min_reserve[h], val)
        elif d.directive_type == "no_charge_window":
            for h in hours:
                charge_allowed[h] = False
        elif d.directive_type == "no_discharge_window":
            for h in hours:
                discharge_allowed[h] = False
        elif d.directive_type == "max_grid_window":
            val = sa.get("max_grid_kwh")
            for h in hours:
                max_grid_limits[h] = min(max_grid_limits[h], val)

    # Decision variables
    grid_kwh = [pulp.LpVariable(f"grid_{h}", lowBound=0) for h in range(24)]
    solar_used_kwh = [pulp.LpVariable(f"solar_used_{h}", lowBound=0) for h in range(24)]
    battery_charge = [pulp.LpVariable(f"charge_{h}", lowBound=0, upBound=max_charge) for h in range(24)]
    battery_discharge = [pulp.LpVariable(f"discharge_{h}", lowBound=0, upBound=max_discharge) for h in range(24)]
    battery_energy = [pulp.LpVariable(f"energy_{h}", lowBound=0, upBound=capacity) for h in range(24)]
    
    # Binary variables to prevent simultaneous charge and discharge
    is_charge = [pulp.LpVariable(f"is_charge_{h}", cat='Binary') for h in range(24)]
    is_discharge = [pulp.LpVariable(f"is_discharge_{h}", cat='Binary') for h in range(24)]
    
    # Objective function
    prob += pulp.lpSum([grid_kwh[h] * request.hours[h].tariff_bdt_per_kwh for h in range(24)])
    
    # Constraints
    for h in range(24):
        req_h = request.hours[h]
        
        # Energy balance
        prob += grid_kwh[h] + solar_used_kwh[h] + battery_discharge[h] == req_h.demand_kwh + battery_charge[h]
        
        # Effective solar
        eff_solar = req_h.solar_kwh * solar_factors[h]
        prob += solar_used_kwh[h] <= eff_solar
        
        # Battery transition
        if h == 0:
            prob += battery_energy[h] == initial_energy + battery_charge[h] - battery_discharge[h]
        else:
            prob += battery_energy[h] == battery_energy[h-1] + battery_charge[h] - battery_discharge[h]
            
        # Battery bounds
        prob += battery_energy[h] >= active_min_reserve[h]
        prob += battery_energy[h] <= capacity
        
        # Directive overrides
        if not charge_allowed[h]:
            prob += battery_charge[h] == 0
        if not discharge_allowed[h]:
            prob += battery_discharge[h] == 0
        if max_grid_limits[h] != float('inf'):
            prob += grid_kwh[h] <= max_grid_limits[h]
            
        # Simultaneous charge/discharge prevention
        prob += battery_charge[h] <= max_charge * is_charge[h]
        prob += battery_discharge[h] <= max_discharge * is_discharge[h]
        prob += is_charge[h] + is_discharge[h] <= 1
        
    # End-of-day neutrality
    prob += battery_energy[23] == initial_energy
    
    # Solve the problem
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    
    if pulp.LpStatus[prob.status] != 'Optimal':
        raise ValueError(f"Optimization failed: Model is {pulp.LpStatus[prob.status]}")
    
    hourly_plan = []
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0
    
    for h in range(24):
        g = pulp.value(grid_kwh[h]) or 0.0
        s = pulp.value(solar_used_kwh[h]) or 0.0
        c = pulp.value(battery_charge[h]) or 0.0
        d = pulp.value(battery_discharge[h]) or 0.0
        e = pulp.value(battery_energy[h]) or 0.0
        
        total_grid += g
        total_cost += g * request.hours[h].tariff_bdt_per_kwh
        peak_grid = max(peak_grid, g)
        
        action = "idle"
        bat_kwh = 0.0
        if c > 0.001:
            action = "charge"
            bat_kwh = c
        elif d > 0.001:
            action = "discharge"
            bat_kwh = d
            
        hourly_plan.append(HourlyPlanEntry(
            hour=h,
            grid_kwh=round(g, 3),
            solar_used_kwh=round(s, 3),
            battery_action=action,
            battery_kwh=round(bat_kwh, 3),
            battery_energy_after_kwh=round(e, 3)
        ))
        
    return hourly_plan, round(total_grid, 3), round(total_cost, 3), round(peak_grid, 3)
