import json
import heapq
from cost_formula import calculate_cost


def load_graph(path="floor_graph.json"):
    with open(path, "r") as f:
        return json.load(f)


def build_adjacency(graph_data, hazard_state=None):
    """
    Builds an adjacency list: { node_id: [(neighbor_id, cost), ...] }
    hazard_state: optional dict { node_id: {"T":.., "ppm":.., "flame":.., "occupancy":..} }
                   defaults to safe/normal conditions if a node isn't in hazard_state.
    """
    if hazard_state is None:
        hazard_state = {}

    adjacency = {n["id"]: [] for n in graph_data["nodes"]}

    for edge in graph_data["edges"]:
        a, b = edge["from"], edge["to"]
        base_dist = edge["base_distance"]

        # cost is evaluated using the hazard state of the DESTINATION node
        # (the segment you'd be walking into)
        def edge_cost(target_node):
            hz = hazard_state.get(target_node, {"T": 22, "ppm": 0, "flame": 0, "occupancy": 0})
            return calculate_cost(base_dist, T=hz["T"], ppm=hz["ppm"],
                                   flame=hz["flame"], occupancy=hz["occupancy"])

        cost_a_to_b = edge_cost(b)
        cost_b_to_a = edge_cost(a)

        adjacency[a].append((b, cost_a_to_b))
        adjacency[b].append((a, cost_b_to_a))

    return adjacency


def dijkstra(adjacency, start, targets):
    """
    Standard Dijkstra from `start` to any node in `targets` (a set/list of exit node IDs).
    Returns (best_exit, total_cost, path_list).
    """
    dist = {node: float("inf") for node in adjacency}
    prev = {node: None for node in adjacency}
    dist[start] = 0

    pq = [(0, start)]
    visited = set()

    while pq:
        current_dist, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)

        if u in targets:
            # reached an exit — reconstruct path and return
            path = []
            node = u
            while node is not None:
                path.append(node)
                node = prev[node]
            path.reverse()
            return u, current_dist, path

        for v, weight in adjacency[u]:
            if v in visited:
                continue
            new_dist = current_dist + weight
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    return None, float("inf"), []  # no path found


def find_safest_exit(graph_data, start_node, hazard_state=None):
    adjacency = build_adjacency(graph_data, hazard_state)
    targets = set(graph_data["exits"])
    best_exit, cost, path = dijkstra(adjacency, start_node, targets)
    return best_exit, cost, path


if __name__ == "__main__":
    graph = load_graph("floor_graph.json")

    print("=== Scenario 1: No hazards ===")
    exit_id, cost, path = find_safest_exit(graph, start_node="N6")
    print(f"From N6 -> safest exit: {exit_id}, cost: {cost:.2f}")
    print("Path:", " -> ".join(path))

    print("\n=== Scenario 2: Flashover at N6's route via N2 ===")
    hazard = {
        "N2": {"T": 48, "ppm": 11, "flame": 1, "occupancy": 0}
    }
    exit_id, cost, path = find_safest_exit(graph, start_node="N6", hazard_state=hazard)
    print(f"From N6 -> safest exit: {exit_id}, cost: {cost:.2f}")
    print("Path:", " -> ".join(path))

    print("\n=== Scenario 3: Slow smolder at N11 ===")
    hazard = {
        "N11": {"T": 25, "ppm": 6, "flame": 0, "occupancy": 1}
    }
    exit_id, cost, path = find_safest_exit(graph, start_node="N7", hazard_state=hazard)
    print(f"From N7 -> safest exit: {exit_id}, cost: {cost:.2f}")
    print("Path:", " -> ".join(path))