# graph.py — a simple directed graph stored as an adjacency list.
# Idea: each exercise points to the next exercise in its progression.
# Space: O(V + E). Adding an edge takes O(1) amortised time.

class Graph:
    def __init__(self):
        self.adjacency_list = {}

    def add_node(self, name):
        if name not in self.adjacency_list:
            self.adjacency_list[name] = []

    def add_edge(self, start, end):
        self.add_node(start)
        self.add_node(end)
        self.adjacency_list[start].append(end)
