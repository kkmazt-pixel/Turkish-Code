"""Bounded graph-traversal SQL builders (doc 12 §8, PR-14).

Pure helpers that produce the recursive-CTE SQL + parameters for reachable-set
queries. ``UNION`` (not ``UNION ALL``) gives a visited-set so cycles terminate,
and the ``depth < ?`` guard caps every walk — no traversal is ever unbounded
(doc 12 §21). Kept separate from the repository so the SQL is unit-visible.
"""

from __future__ import annotations

from turkish_code.graf.depo import Direction

_RECURSIVE_STEP = {
    Direction.OUTGOING: (
        "JOIN graph_edge e ON e.source = reach.id",
        "e.target",
    ),
    Direction.INCOMING: (
        "JOIN graph_edge e ON e.target = reach.id",
        "e.source",
    ),
    Direction.BOTH: (
        "JOIN graph_edge e ON (e.source = reach.id OR e.target = reach.id)",
        "CASE WHEN e.source = reach.id THEN e.target ELSE e.source END",
    ),
}


def reachable_ids_query(
    seed_ids: list[str],
    *,
    depth: int,
    direction: Direction,
    edge_kinds: list[str] | None,
) -> tuple[str, list[object]]:
    """SQL + params selecting all ids reachable within ``depth`` (seeds included).

    Seeds enter the CTE at depth 0 via ``json_each`` so any number of seeds is
    supported; callers exclude the seeds themselves when they want strict
    neighbors (doc 12 §8).
    """
    join, next_expr = _RECURSIVE_STEP[direction]
    kind_filter = ""
    params: list[object] = [_json_array(seed_ids), depth]
    if edge_kinds:
        placeholders = ", ".join("?" * len(edge_kinds))
        kind_filter = f"AND e.kind IN ({placeholders})"
        params.extend(edge_kinds)
    sql = (
        "WITH RECURSIVE reach(id, depth) AS ("
        "  SELECT je.value, 0 FROM json_each(?) je"
        "  UNION"
        f"  SELECT {next_expr}, reach.depth + 1"
        f"  FROM reach {join}"
        f"  WHERE reach.depth < ? {kind_filter}"
        ") SELECT DISTINCT id FROM reach"
    )
    return sql, params


def _json_array(values: list[str]) -> str:
    import json

    return json.dumps(values)
