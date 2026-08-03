"""
Streamlit dashboard for the Multi-Warehouse Inventory Balancer.

Run with:
    streamlit run app.py
"""

import itertools

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from balancer import run_network, compute_kpis


st.set_page_config(page_title="Multi-Warehouse Inventory Balancer", layout="wide")

DEFAULT_ROWS = [
    ("Bengaluru-FC1", "SKU-PHONE-CASE", 40, 8, 5, 900),
    ("Delhi-FC2",     "SKU-PHONE-CASE", 60, 12, 7, 150),
    ("Mumbai-FC3",    "SKU-PHONE-CASE", 35, 7, 6, 500),
    ("Hyderabad-FC4", "SKU-PHONE-CASE", 50, 10, 4, 80),
    ("Bengaluru-FC1", "SKU-EARBUDS", 25, 6, 5, 60),
    ("Delhi-FC2",     "SKU-EARBUDS", 30, 7, 7, 700),
    ("Mumbai-FC3",    "SKU-EARBUDS", 20, 5, 6, 200),
    ("Hyderabad-FC4", "SKU-EARBUDS", 15, 4, 4, 90),
    ("Bengaluru-FC1", "SKU-CHARGER", 45, 9, 5, 400),
    ("Delhi-FC2",     "SKU-CHARGER", 55, 11, 7, 380),
    ("Mumbai-FC3",    "SKU-CHARGER", 30, 6, 6, 60),
    ("Hyderabad-FC4", "SKU-CHARGER", 40, 8, 4, 550),
]

DEFAULT_DISTANCES = {
    ("Bengaluru-FC1", "Delhi-FC2"): 2150,
    ("Bengaluru-FC1", "Mumbai-FC3"): 985,
    ("Bengaluru-FC1", "Hyderabad-FC4"): 570,
    ("Delhi-FC2", "Mumbai-FC3"): 1420,
    ("Delhi-FC2", "Hyderabad-FC4"): 1550,
    ("Mumbai-FC3", "Hyderabad-FC4"): 710,
}

DEFAULT_CAPACITIES = {
    "Bengaluru-FC1": 2000,
    "Delhi-FC2": 1800,
    "Mumbai-FC3": 1200,
    "Hyderabad-FC4": 1000,
}


def default_dataframe():
    return pd.DataFrame(
        DEFAULT_ROWS,
        columns=["warehouse", "sku", "daily_demand", "demand_std",
                 "lead_time_days", "on_hand"],
    )


def distance_dataframe(warehouses):
    """Build an editable NxN distance table, pre-filled where we have
    real defaults, otherwise a placeholder the user can edit."""
    rows = []
    for a, b in itertools.combinations(sorted(warehouses), 2):
        dist = DEFAULT_DISTANCES.get((a, b)) or DEFAULT_DISTANCES.get((b, a)) or 800
        rows.append({"from": a, "to": b, "distance_km": dist})
    return pd.DataFrame(rows)


def to_distance_matrix(df):
    d = {}
    for _, row in df.iterrows():
        d[(row["from"], row["to"])] = row["distance_km"]
        d[(row["to"], row["from"])] = row["distance_km"]
    return d


def capacity_dataframe(warehouses):
    return pd.DataFrame([
        {"warehouse": wh, "capacity_units": DEFAULT_CAPACITIES.get(wh, 1500)}
        for wh in warehouses
    ])


def to_capacity_dict(df):
    return {row["warehouse"]: row["capacity_units"] for _, row in df.iterrows()}


def df_to_records(df):
    records = []
    for _, row in df.iterrows():
        records.append({
            "name": row["warehouse"],
            "sku": row["sku"],
            "daily_demand": float(row["daily_demand"]),
            "demand_std": float(row["demand_std"]),
            "lead_time_days": float(row["lead_time_days"]),
            "on_hand": float(row["on_hand"]),
        })
    return records


# ---------------------------------------------------------------------
# Sidebar: parameters
# ---------------------------------------------------------------------

st.sidebar.header("Parameters")
service_level = st.sidebar.slider("Target service level", 0.80, 0.999, 0.95, 0.005)
external_cost = st.sidebar.number_input(
    "External replenishment cost (₹/unit)", min_value=0.5, value=15.0, step=0.5,
    help="Cost of covering a unit of deficit by reordering from the supplier.")
cost_per_km = st.sidebar.number_input(
    "Transfer cost rate (₹/unit/km)", min_value=0.0001, value=0.004,
    step=0.001, format="%.4f",
    help="Used with lane distance to price lateral transfers.")
max_lane = st.sidebar.number_input(
    "Max units per transfer lane (0 = no cap)", min_value=0, value=0, step=50)
max_lane = None if max_lane == 0 else max_lane

st.sidebar.markdown("---")
st.sidebar.subheader("KPI assumptions")
st.sidebar.caption(
    "OTIF needs an on-time-delivery estimate, since this tool has no "
    "real order timestamps — treat it as a planning estimate."
)
on_time_transfer = st.sidebar.slider(
    "On-time probability: lateral transfers", 0.80, 1.0, 0.98, 0.01,
    help="Internal warehouse-to-warehouse moves are usually more reliable "
         "than supplier lead times.")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Edit the tables in the main panel to use your own warehouses, SKUs, "
    "and distances, then click **Run optimization**."
)


# ---------------------------------------------------------------------
# Main panel: editable inputs
# ---------------------------------------------------------------------

st.title("📦 Multi-Warehouse Inventory Balancer")
st.caption(
    "Decides whether to fix a warehouse's stock imbalance by transferring "
    "stock from another warehouse, or by reordering from the supplier — "
    "whichever is cheaper."
)

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Warehouse × SKU demand data")
    data_df = st.data_editor(
        default_dataframe(), num_rows="dynamic", use_container_width=True,
        key="data_editor",
    )

with col2:
    st.subheader("Inter-warehouse distances (km)")
    warehouses = sorted(data_df["warehouse"].dropna().unique().tolist())
    dist_df = st.data_editor(
        distance_dataframe(warehouses), num_rows="dynamic",
        use_container_width=True, key="dist_editor",
    )

run = st.button("▶️ Run optimization", type="primary")

if "result" not in st.session_state:
    st.session_state["result"] = None

if run:
    try:
        warehouse_data = df_to_records(data_df)
        distance_matrix = to_distance_matrix(dist_df)
        result = run_network(
            warehouse_data, distance_matrix,
            cost_per_unit_per_km=cost_per_km,
            external_cost_per_unit=external_cost,
            service_level=service_level,
            max_transfer_per_lane=max_lane,
        )
        st.session_state["result"] = result
    except Exception as e:
        st.error(f"Optimization failed: {e}")


# ---------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------

result = st.session_state["result"]

if result is None:
    st.info("Set your parameters and data above, then click **Run optimization**.")
    st.stop()

totals = result["totals"]

st.markdown("---")
st.subheader("Network summary")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Baseline cost (no transfers)", f"₹{totals['total_baseline_cost']:,.0f}")
m2.metric("Cost with transfers", f"₹{totals['total_cost']:,.0f}")
pct = (totals["total_savings"] / totals["total_baseline_cost"] * 100
       if totals["total_baseline_cost"] else 0)
m3.metric("Total savings", f"₹{totals['total_savings']:,.0f}", f"{pct:.1f}%")
m4.metric("External reorder cost remaining", f"₹{totals['total_external_cost']:,.0f}")

# Cost comparison chart
cost_fig = go.Figure(data=[
    go.Bar(name="Baseline (no transfer)",
           x=["Network cost"], y=[totals["total_baseline_cost"]]),
    go.Bar(name="With lateral transfers",
           x=["Network cost"], y=[totals["total_cost"]]),
])
cost_fig.update_layout(barmode="group", height=300,
                        title="Total network cost: baseline vs. optimized")
st.plotly_chart(cost_fig, use_container_width=True)

st.markdown("---")
st.subheader("Per-SKU detail")

for sku_result in result["per_sku"]:
    with st.expander(f"{sku_result['sku']}  —  "
                      f"savings ₹{sku_result['savings_vs_baseline']:,.0f}",
                      expanded=True):
        pos_df = pd.DataFrame(sku_result["positions"])
        pos_df["status"] = pos_df["imbalance"].apply(
            lambda x: "Surplus" if x > 0 else ("Deficit" if x < 0 else "Balanced"))

        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown("**Inventory position**")
            st.dataframe(
                pos_df[["warehouse", "on_hand", "reorder_point",
                        "safety_stock", "imbalance", "status"]],
                use_container_width=True, hide_index=True,
            )

            bar_fig = px.bar(
                pos_df, x="warehouse", y="imbalance", color="status",
                color_discrete_map={"Surplus": "#2E7D32", "Deficit": "#C62828",
                                     "Balanced": "#9E9E9E"},
                title="Surplus / deficit by warehouse",
            )
            bar_fig.update_layout(height=320)
            st.plotly_chart(bar_fig, use_container_width=True)

        with c2:
            st.markdown("**Recommended transfers**")
            if sku_result["transfers"]:
                t_df = pd.DataFrame(sku_result["transfers"])
                st.dataframe(
                    t_df[["from", "to", "qty", "cost_per_unit", "lane_cost"]],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.write("No profitable transfers — cheaper to reorder externally.")

            st.markdown("**Cost breakdown**")
            st.write(f"- Transfer cost: ₹{sku_result['transfer_cost']:,.0f}")
            st.write(f"- Unfulfilled deficit: {sku_result['unfulfilled_deficit']:.0f} units "
                      f"(₹{sku_result['external_cost_for_unfulfilled']:,.0f})")
            st.write(f"- Baseline cost: ₹{sku_result['baseline_cost_no_transfer']:,.0f}")
            st.write(f"- **Savings: ₹{sku_result['savings_vs_baseline']:,.0f}**")

st.markdown("---")
st.subheader("Sensitivity: savings vs. external replenishment cost")
st.caption(
    "As reordering from the supplier gets more expensive, lateral transfers "
    "become relatively more attractive — this shows how total network "
    "savings respond."
)

sweep_costs = [max(1, external_cost * f) for f in [0.2, 0.5, 1, 1.5, 2, 3]]
sweep_results = []
warehouse_data = df_to_records(data_df)
distance_matrix = to_distance_matrix(dist_df)
for ec in sweep_costs:
    r = run_network(
        warehouse_data, distance_matrix,
        cost_per_unit_per_km=cost_per_km,
        external_cost_per_unit=ec,
        service_level=service_level,
        max_transfer_per_lane=max_lane,
    )
    sweep_results.append({"external_cost": ec, "total_savings": r["totals"]["total_savings"]})

sweep_df = pd.DataFrame(sweep_results)
sens_fig = px.line(sweep_df, x="external_cost", y="total_savings", markers=True,
                    title="Total network savings vs. external replenishment cost (₹/unit)")
sens_fig.update_layout(height=350)
st.plotly_chart(sens_fig, use_container_width=True)

st.markdown("---")
transfers_all = []
for sku_result in result["per_sku"]:
    transfers_all.extend(sku_result["transfers"])
if transfers_all:
    csv = pd.DataFrame(transfers_all).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download recommended transfers (CSV)", csv,
                        "recommended_transfers.csv", "text/csv")