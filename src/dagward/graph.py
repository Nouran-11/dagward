import networkx as nx

from dagward.models import Workflow


def build_graph(workflow: Workflow) -> nx.DiGraph:
    """Build prerequisite-to-dependent edges after dependency validation.

    The caller must first reject duplicate IDs and missing references so
    NetworkX cannot silently merge or add invalid tasks. Self-dependency edges
    remain available for the separate self-dependency diagnostic.
    """
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(task.id for task in workflow.tasks))
    graph.add_edges_from(
        sorted(
            (prerequisite, task.id)
            for task in workflow.tasks
            for prerequisite in task.depends_on
        )
    )
    return graph


def find_cycles(graph: nx.DiGraph) -> tuple[tuple[str, ...], ...]:
    """Return one deterministic closed cycle per multi-task cyclic component.

    Singleton self-loops belong to the separate self-dependency diagnostic.
    Sorting a copy makes NetworkX traversal independent of input insertion
    order. Finding one cycle per component avoids enumerating all cycles.
    """
    ordered = nx.DiGraph()
    ordered.add_nodes_from(sorted(graph.nodes))
    ordered.add_edges_from(sorted((u, v) for u, v in graph.edges if u != v))
    components = sorted(
        tuple(sorted(component))
        for component in nx.strongly_connected_components(ordered)
        if len(component) > 1
    )

    cycles = []
    for component in components:
        edges = nx.find_cycle(ordered.subgraph(component), source=component[0])
        path = [edge[0] for edge in edges]
        start = path.index(min(path))
        path = path[start:] + path[:start]
        cycles.append(tuple([*path, path[0]]))

    return tuple(sorted(cycles))
