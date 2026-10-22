import networkx as nx
import pytest

from dagward.graph import build_graph, find_cycles
from dagward.models import Task, Workflow


def test_build_graph_uses_prerequisite_to_dependent_edges() -> None:
    workflow = Workflow(
        tasks=[
            Task(id="report", depends_on=["transform", "extract"]),
            Task(id="transform", depends_on=["extract"]),
            Task(id="extract"),
            Task(id="isolated"),
        ]
    )

    graph = build_graph(workflow)

    assert list(graph.nodes) == ["extract", "isolated", "report", "transform"]
    assert list(graph.edges) == [
        ("extract", "report"),
        ("extract", "transform"),
        ("transform", "report"),
    ]
    assert graph.in_degree("extract") == 0
    assert graph.degree("isolated") == 0


def test_build_graph_is_independent_of_task_and_dependency_order() -> None:
    first = Workflow(
        tasks=[Task(id="c", depends_on=["b", "a"]), Task(id="b"), Task(id="a")]
    )
    second = Workflow(
        tasks=[Task(id="a"), Task(id="b"), Task(id="c", depends_on=["a", "b"])]
    )

    assert list(build_graph(first).nodes) == list(build_graph(second).nodes)
    assert list(build_graph(first).edges) == list(build_graph(second).edges)


def test_empty_workflow_produces_empty_graph() -> None:
    graph = build_graph(Workflow(tasks=[]))

    assert list(graph.nodes) == []
    assert list(graph.edges) == []
    assert find_cycles(graph) == ()


def test_build_graph_retains_self_dependency_edges() -> None:
    graph = build_graph(Workflow(tasks=[Task(id="self", depends_on=["self"])]))

    assert list(graph.edges) == [("self", "self")]


def test_disconnected_dag_has_no_cycles() -> None:
    graph = nx.DiGraph([("a", "b"), ("a", "c"), ("d", "e")])
    graph.add_node("isolated")

    assert find_cycles(graph) == ()


@pytest.mark.parametrize(
    ("edges", "expected"),
    [
        ([("b", "a"), ("a", "b")], (("a", "b", "a"),)),
        (
            [("c", "a"), ("a", "b"), ("b", "c")],
            (("a", "b", "c", "a"),),
        ),
        (
            [("a", "c"), ("c", "b"), ("b", "a")],
            (("a", "c", "b", "a"),),
        ),
    ],
)
def test_cycles_follow_actual_directed_edges(
    edges: list[tuple[str, str]], expected: tuple[tuple[str, ...], ...]
) -> None:
    graph = nx.DiGraph(edges)

    assert find_cycles(graph) == expected


def test_overlapping_cycles_yield_one_representative_for_component() -> None:
    graph = nx.DiGraph([("a", "b"), ("b", "a"), ("b", "c"), ("c", "d"), ("d", "b")])

    assert find_cycles(graph) == (("a", "b", "a"),)


def test_multiple_cyclic_components_are_sorted() -> None:
    graph = nx.DiGraph(
        [
            ("x", "y"),
            ("y", "x"),
            ("c", "a"),
            ("a", "b"),
            ("b", "c"),
            ("c", "x"),
            ("source", "sink"),
        ]
    )

    assert find_cycles(graph) == (("a", "b", "c", "a"), ("x", "y", "x"))


def test_cycle_results_do_not_depend_on_insertion_order() -> None:
    edges = [
        ("a", "c"),
        ("c", "b"),
        ("b", "a"),
        ("a", "d"),
        ("d", "a"),
        ("z", "y"),
        ("y", "z"),
    ]
    forward = nx.DiGraph(edges)
    reverse = nx.DiGraph(reversed(edges))

    assert find_cycles(forward) == find_cycles(reverse)
    assert find_cycles(forward) == (("a", "c", "b", "a"), ("y", "z", "y"))


def test_self_loops_are_left_to_self_dependency_validation() -> None:
    graph = nx.DiGraph([("a", "a"), ("b", "b")])

    assert find_cycles(graph) == ()


def test_self_loop_does_not_hide_a_multi_task_cycle() -> None:
    graph = nx.DiGraph([("a", "a"), ("a", "b"), ("b", "a")])

    assert find_cycles(graph) == (("a", "b", "a"),)


def test_cycle_search_handles_long_cycles_without_recursion() -> None:
    nodes = [f"task-{index:04}" for index in range(1500)]
    graph = nx.DiGraph(zip(nodes, [*nodes[1:], nodes[0]], strict=True))

    assert find_cycles(graph) == (tuple([*nodes, nodes[0]]),)


def test_cycle_search_does_not_mutate_input_graph() -> None:
    graph = nx.DiGraph([("b", "a"), ("a", "a"), ("a", "b")])
    original_nodes = list(graph.nodes)
    original_edges = list(graph.edges)

    find_cycles(graph)

    assert list(graph.nodes) == original_nodes
    assert list(graph.edges) == original_edges
