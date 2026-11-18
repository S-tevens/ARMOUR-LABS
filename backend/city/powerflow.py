"""Linear (DC) power flow for the city network (owner: P2). Simple on purpose: 8 districts, one slack.

Nodes are districts plus the state grid ("GRID", the slack). Each line has a susceptance proportional to its
capacity, so equal loading percentages mean equal angle differences. Load is injected as negative power.
Parts of the network that are cut off from the grid are reported as de-energised.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SLACK = "GRID"
RAD_AT_CAPACITY = 0.3  # angle difference (radians) at which a line is at 100 % loading


@dataclass(frozen=True)
class Line:
    id: str
    a: str
    b: str
    capacity_mw: float


def solve(nodes: list[str], lines: list[Line], in_service: set[str], load_mw: dict[str, float]):
    """Returns (flows MW by line id, energised node ids).

    flows is positive from `a` to `b`. Lines not in service carry 0. Nodes not connected to the slack through
    in-service lines are not energised and their load is ignored.
    """
    # connected component of the slack
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for ln in lines:
        if ln.id in in_service:
            adj[ln.a].append(ln.b)
            adj[ln.b].append(ln.a)
    energised = {SLACK}
    stack = [SLACK]
    while stack:
        n = stack.pop()
        for m in adj[n]:
            if m not in energised:
                energised.add(m)
                stack.append(m)

    flows = {ln.id: 0.0 for ln in lines}
    free = [n for n in nodes if n != SLACK and n in energised]
    if not free:
        return flows, energised
    idx = {n: i for i, n in enumerate(free)}
    B = np.zeros((len(free), len(free)))
    for ln in lines:
        if ln.id not in in_service or ln.a not in energised or ln.b not in energised:
            continue
        b = ln.capacity_mw / RAD_AT_CAPACITY
        for x, y in ((ln.a, ln.b), (ln.b, ln.a)):
            if x in idx:
                B[idx[x], idx[x]] += b
                if y in idx:
                    B[idx[x], idx[y]] -= b
    p = np.array([-load_mw.get(n, 0.0) for n in free])
    theta = np.linalg.solve(B, p)
    ang = {n: float(theta[idx[n]]) for n in free}
    ang[SLACK] = 0.0
    for ln in lines:
        if ln.id in in_service and ln.a in energised and ln.b in energised:
            flows[ln.id] = ln.capacity_mw / RAD_AT_CAPACITY * (ang[ln.a] - ang[ln.b])
    return flows, energised
