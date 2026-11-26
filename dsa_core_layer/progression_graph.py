# progression_graph.py — find the fewest progression steps to a target exercise.
# Idea: use Kahn's algorithm to check cycles and BFS to find the shortest path.
# Time: O(V + E). Space: O(V + E).

from dsa_core_layer.structures.graph import Graph


def build_graph(edges):
    graph = Graph()
    # Add each directed progression relationship to the adjacency list.
    for edge in edges:
        graph.add_edge(edge[0], edge[1])
    return graph


def find_roots(graph):
    adjacency_list = graph.adjacency_list
    has_parent = set()
    # Mark every exercise that appears as a next step.
    for node in adjacency_list:
        for next_node in adjacency_list[node]:
            has_parent.add(next_node)
    roots = []
    # A root has no incoming edge and can start a progression path.
    for node in adjacency_list:
        if node not in has_parent:
            roots.append(node)
    return roots


def has_cycle(graph):
    adjacency_list = graph.adjacency_list
    in_degree = {}
    # Start every node with zero incoming edges.
    for node in adjacency_list:
        in_degree[node] = 0
    # Count incoming edges for each node.
    for node in adjacency_list:
        for next_node in adjacency_list[node]:
            in_degree[next_node] += 1
    queue = []
    # Add all nodes that have no incoming edges.
    for node in adjacency_list:
        if in_degree[node] == 0:
            queue.append(node)
    head = 0
    removed = 0
    # Process the queue without deleting items from the front.
    while head < len(queue):
        node = queue[head]
        head += 1
        removed += 1
        for next_node in adjacency_list[node]:
            in_degree[next_node] -= 1
            if in_degree[next_node] == 0:
                queue.append(next_node)
    return removed != len(adjacency_list)


def build_path(parent, target):
    path = []
    # Follow parent links from the target back to a root.
    current = target
    while current is not None:
        path.append(current)
        current = parent[current]
    # Reverse the path with two indexes instead of a built-in reverse method.
    left = 0
    right = len(path) - 1
    while left < right:
        temporary = path[left]
        path[left] = path[right]
        path[right] = temporary
        left += 1
        right -= 1
    return path


def shortest_path(graph, target):
    adjacency_list = graph.adjacency_list
    if target not in adjacency_list:
        return []
    parent = {}
    queue = []
    # Start BFS from every root in the progression graph.
    for root in find_roots(graph):
        parent[root] = None
        queue.append(root)
    head = 0
    # BFS visits nodes in increasing path length.
    while head < len(queue):
        node = queue[head]
        head += 1
        if node == target:
            break
        for next_node in adjacency_list[node]:
            if next_node not in parent:
                parent[next_node] = node
                queue.append(next_node)
    if target not in parent:
        return []
    return build_path(parent, target)
