import math

# ============================================================
# Calibration constants — derived from NIST Room Data analysis
# (see Realistic_Fire_Curve_Parameters.md for source values)
# ============================================================
Tk = 47.0      # temp danger threshold (°C) — midpoint of 45-50°C anchor
Pk = 11.5      # smoke danger threshold (%/ft) — midpoint of 11-12%/ft anchor
alpha = 1.0    # temperature scaling weight
beta = 1.0     # smoke scaling weight
gamma = 20.0   # flame penalty multiplier (large, since flame should dominate)
delta = 0.15   # occupancy scaling weight


def calculate_cost(distance, T, ppm, flame, occupancy):
    """
    Returns the traversal cost of a hallway segment.
    Higher cost = more hazardous / less desirable path.

    distance   : base hallway length (from floor_graph.json)
    T          : temperature at node (deg C)
    ppm        : smoke obscuration (%/ft)
    flame      : 0 or 1 (flame detected)
    occupancy  : number of people at/near node
    """
    temp_factor = 1 + alpha * math.exp((T - Tk) / 10)
    smoke_factor = 1 + beta * math.exp((ppm - Pk) / 5)
    flame_factor = 1 + gamma * flame
    occupancy_factor = 1 + delta * occupancy

    cost = distance * temp_factor * smoke_factor * flame_factor * occupancy_factor
    return cost


def test_edge_cases():
    """Sanity checks for the cost formula. Prints result, does not raise on failure
    so you always get a full report of every test."""
    results = []

    baseline = calculate_cost(10, T=20, ppm=0, flame=0, occupancy=0)
    results.append(("Baseline cost is positive", baseline > 0))

    hazard = calculate_cost(10, T=48, ppm=11, flame=1, occupancy=5)
    results.append(("Hazard cost exceeds safe cost", hazard > baseline))

    flame_only = calculate_cost(10, T=20, ppm=0, flame=1, occupancy=0)
    hot_smoky_no_flame = calculate_cost(10, T=48, ppm=11, flame=0, occupancy=0)
    results.append(("Flame alone outweighs high temp+smoke without flame",
                     flame_only > hot_smoky_no_flame))

    slow_smolder = calculate_cost(10, T=25, ppm=6, flame=0, occupancy=2)
    results.append(("Slow smolder cost is modest (between baseline and hazard)",
                     baseline < slow_smolder < hazard))

    print("\n--- Edge case test results ---")
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"[{status}] {name}")

    if all_passed:
        print("All tests passed\n")
    else:
        print("Some tests FAILED — review the constants above\n")

    return all_passed


if __name__ == "__main__":
    # 1) Basic scenario printout
    print("Normal conditions:", calculate_cost(10, T=22, ppm=0, flame=0, occupancy=2))
    print("Flashover node:", calculate_cost(10, T=48, ppm=11, flame=1, occupancy=2))
    print("Slow smolder node:", calculate_cost(10, T=25, ppm=6, flame=0, occupancy=2))

    # 2) Edge case tests
    test_edge_cases()

    # 3) Plot cost vs temperature to visually confirm exponential (not linear) scaling
    import matplotlib.pyplot as plt
    import numpy as np

    temps = np.linspace(20, 55, 50)
    costs = [calculate_cost(10, T=t, ppm=0, flame=0, occupancy=0) for t in temps]

    plt.plot(temps, costs)
    plt.xlabel("Temperature (deg C)")
    plt.ylabel("Cost")
    plt.axvline(x=Tk, color='r', linestyle='--', label='Tk threshold')
    plt.legend()
    plt.title("Cost vs Temperature")
    plt.savefig("cost_vs_temp.png")
    print("Plot saved as cost_vs_temp.png")
    plt.show()