from balancer import run_network


def build_synthetic_data():
    # (warehouse, sku, daily_demand, demand_std, lead_time_days, on_hand)
    raw = [
        ("Bengaluru-FC1", "SKU-PHONE-CASE", 40, 8, 5, 900),   # big surplus
        ("Delhi-FC2",     "SKU-PHONE-CASE", 60, 12, 7, 150),  # heading to deficit
        ("Mumbai-FC3",    "SKU-PHONE-CASE", 35, 7, 6, 500),   # comfortable
        ("Hyderabad-FC4", "SKU-PHONE-CASE", 50, 10, 4, 80),   # deficit

        ("Bengaluru-FC1", "SKU-EARBUDS", 25, 6, 5, 60),   # deficit
        ("Delhi-FC2",     "SKU-EARBUDS", 30, 7, 7, 700),  # surplus
        ("Mumbai-FC3",    "SKU-EARBUDS", 20, 5, 6, 200),  # ok
        ("Hyderabad-FC4", "SKU-EARBUDS", 15, 4, 4, 90),   # slight deficit

        ("Bengaluru-FC1", "SKU-CHARGER", 45, 9, 5, 400),
        ("Delhi-FC2",     "SKU-CHARGER", 55, 11, 7, 380),
        ("Mumbai-FC3",    "SKU-CHARGER", 30, 6, 6, 60),   # deficit
        ("Hyderabad-FC4", "SKU-CHARGER", 40, 8, 4, 550),  # surplus
    ]
    return [
        {
            "name": name, "sku": sku, "daily_demand": dd, "demand_std": std,
            "lead_time_days": lt, "on_hand": oh,
        }
        for name, sku, dd, std, lt, oh in raw
    ]


def build_distances():
    # Approx inter-city road distances (km), symmetric
    d = {
        ("Bengaluru-FC1", "Delhi-FC2"): 2150,
        ("Bengaluru-FC1", "Mumbai-FC3"): 985,
        ("Bengaluru-FC1", "Hyderabad-FC4"): 570,
        ("Delhi-FC2", "Mumbai-FC3"): 1420,
        ("Delhi-FC2", "Hyderabad-FC4"): 1550,
        ("Mumbai-FC3", "Hyderabad-FC4"): 710,
    }
    # mirror both directions
    full = {}
    for (a, b), dist in d.items():
        full[(a, b)] = dist
        full[(b, a)] = dist
    return full


def print_report(network_result):
    for sku_result in network_result["per_sku"]:
        print(f"\n=== {sku_result['sku']} ===")
        print("Inventory positions:")
        for p in sku_result["positions"]:
            status = "SURPLUS" if p["imbalance"] > 0 else "DEFICIT"
            print(f"  {p['warehouse']:15s} on_hand={p['on_hand']:>5} "
                  f"reorder_pt={p['reorder_point']:>6} "
                  f"imbalance={p['imbalance']:>7} [{status}]")

        if sku_result["transfers"]:
            print("Recommended transfers:")
            for t in sku_result["transfers"]:
                print(f"  {t['qty']:>6} units: {t['from']} -> {t['to']} "
                      f"@ {t['cost_per_unit']:.2f}/unit "
                      f"(lane cost ${t['lane_cost']:.2f})")
        else:
            print("  No profitable transfers found.")

        print(f"Transfer cost: ${sku_result['transfer_cost']:.2f} | "
              f"Unfulfilled deficit: {sku_result['unfulfilled_deficit']} units "
              f"(${sku_result['external_cost_for_unfulfilled']:.2f}) | "
              f"Baseline (no transfer): ${sku_result['baseline_cost_no_transfer']:.2f} | "
              f"Savings: ${sku_result['savings_vs_baseline']:.2f}")

    print("\n=== NETWORK TOTALS ===")
    t = network_result["totals"]
    print(f"Total transfer cost:        ${t['total_transfer_cost']:.2f}")
    print(f"Total external reorder cost: ${t['total_external_cost']:.2f}")
    print(f"Total cost (with transfers): ${t['total_cost']:.2f}")
    print(f"Baseline cost (no transfers): ${t['total_baseline_cost']:.2f}")
    print(f"Total savings:               ${t['total_savings']:.2f}")


def sensitivity_analysis(warehouse_data, distances):
    """Sweep external replenishment cost to see how savings change."""
    print("\n=== SENSITIVITY: external cost per unit vs. savings ===")
    for ext_cost in [2, 5, 10, 20, 40]:
        result = run_network(
            warehouse_data, distances,
            cost_per_unit_per_km=0.004,
            external_cost_per_unit=ext_cost,
            service_level=0.95,
        )
        print(f"  external_cost=${ext_cost:>3} -> "
              f"total_savings=${result['totals']['total_savings']:.2f}")


if __name__ == "__main__":
    data = build_synthetic_data()
    distances = build_distances()

    result = run_network(
        data, distances,
        cost_per_unit_per_km=0.004,   # ₹/unit/km-equivalent transfer cost
        external_cost_per_unit=15,    # cost to reorder a unit from supplier
        service_level=0.95,
    )

    print_report(result)
    sensitivity_analysis(data, distances)
