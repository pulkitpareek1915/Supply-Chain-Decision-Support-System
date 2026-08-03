import numpy as np
from scipy.stats import norm
from scipy.optimize import linprog


# ---------------------------------------------------------------------
# Stage 1: per-warehouse, per-SKU inventory position
# ---------------------------------------------------------------------

def compute_inventory_position(warehouse, service_level=0.95):
    """
    Given a single warehouse-SKU record, compute safety stock,
    reorder point, and surplus/deficit vs. current on-hand stock.

    warehouse: dict with keys
        daily_demand, demand_std, lead_time_days, on_hand,
        (optional) demand_std defaults to 20% of daily_demand
    """
    z = norm.ppf(service_level)
    mu = warehouse["daily_demand"]
    sig = warehouse.get("demand_std", mu * 0.2)
    lt = warehouse["lead_time_days"]
    on_hand = warehouse["on_hand"]

    safety_stock = z * sig * np.sqrt(lt)
    reorder_point = mu * lt + safety_stock
    # Target position: enough to cover one lead time of demand + safety stock
    target = reorder_point
    imbalance = on_hand - target  # positive = surplus, negative = deficit

    return {
        "warehouse": warehouse["name"],
        "sku": warehouse["sku"],
        "daily_demand": mu,
        "lead_time_days": lt,
        "safety_stock": round(safety_stock, 1),
        "reorder_point": round(reorder_point, 1),
        "on_hand": on_hand,
        "imbalance": round(imbalance, 1),  # surplus (+) or deficit (-)
    }


# ---------------------------------------------------------------------
# Stage 2: lateral transfer optimization (transportation problem)
# ---------------------------------------------------------------------

def optimize_transfers(positions, transfer_cost_matrix, external_cost_per_unit,
                        max_transfer_per_lane=None):
    """
    For a single SKU, decide lateral transfer quantities between
    warehouses that have surplus and warehouses that have a deficit.

    positions: list of dicts from compute_inventory_position, all for
        the SAME sku, one entry per warehouse.
    transfer_cost_matrix: dict {(from_wh, to_wh): cost_per_unit}
    external_cost_per_unit: cost to cover a unit of deficit by
        reordering from the supplier instead of transferring
        (used as the "do nothing" baseline and as an upper bound
        on what any transfer should cost).
    max_transfer_per_lane: optional cap on units per (from, to) lane.

    Returns dict with recommended transfers, cost breakdown, and the
    baseline cost of covering every deficit externally.
    """
    surplus_wh = [p for p in positions if p["imbalance"] > 0]
    deficit_wh = [p for p in positions if p["imbalance"] < 0]

    baseline_cost = sum(-p["imbalance"] for p in deficit_wh) * external_cost_per_unit

    if not surplus_wh or not deficit_wh:
        return {
            "sku": positions[0]["sku"],
            "transfers": [],
            "transfer_cost": 0.0,
            "unfulfilled_deficit": sum(-p["imbalance"] for p in deficit_wh),
            "external_cost_for_unfulfilled": baseline_cost,
            "baseline_cost_no_transfer": baseline_cost,
            "total_cost": baseline_cost,
            "savings_vs_baseline": 0.0,
        }

    n_s, n_d = len(surplus_wh), len(deficit_wh)
    n_vars = n_s * n_d

    # Decision variables x[i,j] = units moved from surplus_wh[i] to deficit_wh[j]
    #
    # Every unit of deficit gets covered one way or another: either by a
    # lateral transfer (lane_cost) or, if left unfulfilled, by external
    # replenishment (external_cost_per_unit). Since the external cost for
    # the *whole* deficit is a constant, minimizing total cost is
    # equivalent to minimizing sum(x_ij * (lane_cost_ij - external_cost)).
    # That difference is <= 0 (we cap lane_cost at external_cost), so the
    # solver is rewarded for transferring wherever it's cheaper than
    # reordering, and leaves x=0 on lanes that aren't worth it.
    lane_costs = np.zeros(n_vars)
    c = np.zeros(n_vars)
    for i, s in enumerate(surplus_wh):
        for j, d in enumerate(deficit_wh):
            lane_cost = transfer_cost_matrix.get((s["warehouse"], d["warehouse"]),
                                                   external_cost_per_unit)
            lane_cost = min(lane_cost, external_cost_per_unit)
            lane_costs[i * n_d + j] = lane_cost
            c[i * n_d + j] = lane_cost - external_cost_per_unit

    # Supply constraints: sum_j x[i,j] <= surplus_i
    A_ub = []
    b_ub = []
    for i, s in enumerate(surplus_wh):
        row = np.zeros(n_vars)
        for j in range(n_d):
            row[i * n_d + j] = 1
        A_ub.append(row)
        b_ub.append(s["imbalance"])

    # Demand constraints: sum_i x[i,j] <= deficit_j (can't over-fill a warehouse)
    for j, d in enumerate(deficit_wh):
        row = np.zeros(n_vars)
        for i in range(n_s):
            row[i * n_d + j] = 1
        A_ub.append(row)
        b_ub.append(-d["imbalance"])

    bounds = [(0, max_transfer_per_lane) for _ in range(n_vars)]

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

    transfers = []
    transfer_cost = 0.0
    fulfilled_per_deficit = [0.0] * n_d

    if res.success:
        x = res.x
        for i, s in enumerate(surplus_wh):
            for j, d in enumerate(deficit_wh):
                qty = x[i * n_d + j]
                if qty > 1e-6:
                    lane_cost = lane_costs[i * n_d + j]
                    transfers.append({
                        "from": s["warehouse"],
                        "to": d["warehouse"],
                        "sku": positions[0]["sku"],
                        "qty": round(qty, 1),
                        "cost_per_unit": lane_cost,
                        "lane_cost": round(qty * lane_cost, 2),
                    })
                    transfer_cost += qty * lane_cost
                    fulfilled_per_deficit[j] += qty

    unfulfilled = sum(
        max(-deficit_wh[j]["imbalance"] - fulfilled_per_deficit[j], 0)
        for j in range(n_d)
    )
    external_cost_for_unfulfilled = unfulfilled * external_cost_per_unit
    total_cost = transfer_cost + external_cost_for_unfulfilled

    return {
        "sku": positions[0]["sku"],
        "transfers": transfers,
        "transfer_cost": round(transfer_cost, 2),
        "unfulfilled_deficit": round(unfulfilled, 1),
        "external_cost_for_unfulfilled": round(external_cost_for_unfulfilled, 2),
        "baseline_cost_no_transfer": round(baseline_cost, 2),
        "total_cost": round(total_cost, 2),
        "savings_vs_baseline": round(baseline_cost - total_cost, 2),
    }


def run_network(warehouse_sku_data, distance_matrix, cost_per_unit_per_km,
                 external_cost_per_unit, service_level=0.95,
                 max_transfer_per_lane=None):
    """
    Full pipeline across multiple warehouses and multiple SKUs.

    warehouse_sku_data: list of raw warehouse-sku dicts (see
        compute_inventory_position for required keys)
    distance_matrix: dict {(wh_a, wh_b): distance_km}
    cost_per_unit_per_km: transfer cost rate
    external_cost_per_unit: cost to cover deficit via supplier reorder

    Returns per-SKU results and network-level totals.
    """
    # Group by SKU
    skus = sorted(set(w["sku"] for w in warehouse_sku_data))
    transfer_cost_matrix = {
        pair: dist * cost_per_unit_per_km
        for pair, dist in distance_matrix.items()
    }

    results = []
    for sku in skus:
        rows = [w for w in warehouse_sku_data if w["sku"] == sku]
        positions = [compute_inventory_position(r, service_level) for r in rows]
        result = optimize_transfers(
            positions, transfer_cost_matrix, external_cost_per_unit,
            max_transfer_per_lane=max_transfer_per_lane,
        )
        result["positions"] = positions
        results.append(result)

    totals = {
        "total_transfer_cost": round(sum(r["transfer_cost"] for r in results), 2),
        "total_external_cost": round(sum(r["external_cost_for_unfulfilled"] for r in results), 2),
        "total_baseline_cost": round(sum(r["baseline_cost_no_transfer"] for r in results), 2),
        "total_cost": round(sum(r["total_cost"] for r in results), 2),
        "total_savings": round(sum(r["savings_vs_baseline"] for r in results), 2),
    }
    return {"per_sku": results, "totals": totals}


# ---------------------------------------------------------------------
# Stage 3: operational KPIs
# ---------------------------------------------------------------------
#
# These are computed from the model's own outputs (post-transfer stock
# positions), NOT from historical transaction data — this tool has none.
# Two of them (OTIF, Warehouse Utilization) need an extra assumption
# each (an on-time-delivery estimate, and physical capacity) since the
# model has no delivery timestamps or storage footprint data. Those
# assumptions are passed in explicitly and should be treated as
# planning estimates, not measured history.

def _apply_transfers(positions, transfers):
    """Return positions with an added 'on_hand_after' field reflecting
    the recommended transfers (stock received minus stock shipped out).
    Pass transfers=[] to get the untouched "before optimization" state."""
    received = {}
    shipped = {}
    for t in transfers:
        received[t["to"]] = received.get(t["to"], 0) + t["qty"]
        shipped[t["from"]] = shipped.get(t["from"], 0) + t["qty"]

    updated = []
    for p in positions:
        wh = p["warehouse"]
        on_hand_after = p["on_hand"] + received.get(wh, 0) - shipped.get(wh, 0)
        transferred_in = wh in received
        updated.append({**p, "on_hand_after": round(on_hand_after, 1),
                         "was_transferred_in": transferred_in})
    return updated


def _row_metrics(rows):
    """Add days-of-inventory, turnover, fill-rate, and status to each row."""
    out = []
    for r in rows:
        r = dict(r)
        dd = max(r["daily_demand"], 1e-6)
        oh = r["on_hand_after"]
        lead_time_demand = r["daily_demand"] * r["lead_time_days"]

        r["days_of_inventory"] = round(oh / dd, 1)
        r["inventory_turnover"] = round((dd * 365) / max(oh, 1e-6), 2)
        # Fill rate proxy: how much of lead-time demand current stock covers
        r["fill_rate"] = round(min(1.0, oh / max(lead_time_demand, 1e-6)), 3)
        if oh <= 0:
            r["status"] = "stockout"
        elif oh < r["reorder_point"]:
            r["status"] = "at_risk"
        else:
            r["status"] = "healthy"
        out.append(r)
    return out


def _aggregate_network_kpis(rows, on_time_prob_transfer, on_time_prob_external):
    n = len(rows)
    if n == 0:
        return {k: 0 for k in [
            "inventory_turnover", "avg_fill_rate_pct", "avg_days_of_inventory",
            "order_fulfillment_rate_pct", "stockout_pct", "otif_pct",
            "blended_on_time_pct"]}

    total_demand = sum(r["daily_demand"] for r in rows)
    total_on_hand = sum(r["on_hand_after"] for r in rows)
    total_annual_demand = total_demand * 365

    stockout_rows = sum(1 for r in rows if r["status"] == "stockout")
    healthy_rows = sum(1 for r in rows if r["status"] == "healthy")

    weighted_fill_rate = (
        sum(r["fill_rate"] * r["daily_demand"] for r in rows) / total_demand
        if total_demand else 0
    )
    weighted_doi = (
        sum(r["days_of_inventory"] * r["daily_demand"] for r in rows) / total_demand
        if total_demand else 0
    )
    network_turnover = total_annual_demand / max(total_on_hand, 1e-6)
    stockout_pct = 100 * stockout_rows / n
    order_fulfillment_rate = 100 * healthy_rows / n

    on_time_weighted = sum(
        (on_time_prob_transfer if r.get("was_transferred_in") else on_time_prob_external)
        for r in rows
    ) / n
    otif = (order_fulfillment_rate / 100) * on_time_weighted * 100

    return {
        "inventory_turnover": round(network_turnover, 2),
        "avg_fill_rate_pct": round(weighted_fill_rate * 100, 1),
        "avg_days_of_inventory": round(weighted_doi, 1),
        "order_fulfillment_rate_pct": round(order_fulfillment_rate, 1),
        "stockout_pct": round(stockout_pct, 1),
        "otif_pct": round(otif, 1),
        "blended_on_time_pct": round(on_time_weighted * 100, 1),
    }


def _warehouse_utilization(rows, capacities):
    if not capacities:
        return {}
    by_wh = {}
    for r in rows:
        by_wh[r["warehouse"]] = by_wh.get(r["warehouse"], 0) + r["on_hand_after"]
    util = {}
    for wh, total in by_wh.items():
        cap = capacities.get(wh)
        if cap:
            util[wh] = {
                "total_on_hand": round(total, 1),
                "capacity": cap,
                "utilization_pct": round(100 * total / cap, 1),
            }
    return util


def compute_kpis(network_result, capacities=None,
                  on_time_prob_transfer=0.98, on_time_prob_external=None,
                  service_level=0.95):
    """
    network_result: output of run_network()
    capacities: optional dict {warehouse: capacity_units} for utilization.
        If omitted, utilization is skipped.
    on_time_prob_transfer: assumed probability a lateral transfer arrives
        on time (internal moves are usually more reliable than supplier
        lead times)
    on_time_prob_external: assumed on-time probability for external
        replenishment; defaults to `service_level`, since that's exactly
        the probability the safety-stock policy was designed to hit

    Returns KPIs computed BEFORE any transfer (current state) and AFTER
    the recommended transfers are executed, so the improvement from
    running the optimizer is visible. Warehouse utilization is only
    meaningful "after", since that's the state once transfers are made.

    NOTE: these are model-derived estimates from stock positions and
    assumptions, not measured KPIs from historical order data — this
    tool has none. Treat OTIF in particular as a planning estimate.
    """
    if on_time_prob_external is None:
        on_time_prob_external = service_level

    before_rows, after_rows = [], []
    for sku_result in network_result["per_sku"]:
        before_rows.extend(_apply_transfers(sku_result["positions"], []))
        after_rows.extend(_apply_transfers(sku_result["positions"], sku_result["transfers"]))

    before_rows = _row_metrics(before_rows)
    after_rows = _row_metrics(after_rows)

    # Before any transfer, nothing has moved yet, so everything is
    # subject to the external on-time assumption.
    before_kpis = _aggregate_network_kpis(before_rows, on_time_prob_external,
                                           on_time_prob_external)
    after_kpis = _aggregate_network_kpis(after_rows, on_time_prob_transfer,
                                          on_time_prob_external)

    return {
        "before": before_kpis,
        "after": after_kpis,
        "warehouse_utilization": _warehouse_utilization(after_rows, capacities),
        "rows_before": before_rows,
        "rows_after": after_rows,
    }