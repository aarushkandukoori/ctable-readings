"""A toy conditional table (c-table) over finite domains.

This is a teaching-size version of the idea, not Pyotr. Pyotr stores c-tables in
PostgreSQL and checks conditions with Z3, BDDs or difference-of-cubes. Here every
c-variable has a small finite domain, so we can simply list every valuation.

Words used below:
  c-variable  - an unknown cell, here one setting the samples disagree on
  local cond  - the set of values a c-variable may take (what the samples proposed)
  global cond - a condition over all c-variables together. "tied" means the
                valuation must be one of the full readings some sample proposed.
                "independent" means any mix of the per-variable values.
  world       - one valuation of all c-variables, i.e. one concrete configuration
"""
from itertools import combinations, product


class CVar:
    def __init__(self, name, domain):
        self.name = name
        self.domain = sorted(set(domain), key=str)

    def __repr__(self):
        return f"^{self.name}"


class CTable:
    """One row of settings for a request: each cell is a constant or a CVar."""

    def __init__(self, slots, cells, readings, mode):
        assert mode in ("independent", "tied")
        self.slots = slots
        self.cells = cells
        self.readings = {tuple(r) for r in readings}
        self.mode = mode

    @property
    def cvars(self):
        return [c for c in self.cells if isinstance(c, CVar)]

    def global_condition(self, world):
        if self.mode == "independent":
            return True
        return tuple(world) in self.readings

    def worlds(self):
        """Every concrete reading this c-table stands for."""
        doms = [c.domain if isinstance(c, CVar) else [c] for c in self.cells]
        return [w for w in product(*doms) if self.global_condition(w)]


def build(slots, readings, mode):
    """Settings all samples agree on become constants; the rest become c-variables."""
    readings = [tuple(r) for r in readings]
    cells = []
    for i, name in enumerate(slots):
        vals = {r[i] for r in readings}
        cells.append(next(iter(vals)) if len(vals) == 1 else CVar(name, vals))
    return CTable(slots, cells, readings, mode)


def verdict(table, is_safe):
    """'safe_all', 'unsafe_all' or 'some' over the worlds of the table."""
    vs = [is_safe(w) for w in table.worlds()]
    if all(vs):
        return "safe_all"
    if not any(vs):
        return "unsafe_all"
    return "some"


def question(table, is_safe):
    """Smallest set of c-variables whose answer fixes the verdict.

    Returns [] when there is nothing to ask. One name means one clarifying question.
    """
    ws = table.worlds()
    if verdict(table, is_safe) != "some":
        return []
    idx = [i for i, c in enumerate(table.cells) if isinstance(c, CVar)]
    for size in range(1, len(idx) + 1):
        for S in combinations(idx, size):
            seen = {}
            ok = True
            for w in ws:
                key = tuple(w[i] for i in S)
                v = is_safe(w)
                if seen.setdefault(key, v) != v:
                    ok = False
                    break
            if ok:
                return [table.slots[i] for i in S]
    return [table.slots[i] for i in idx]


def violation_condition(table, is_safe):
    """The condition (as text) under which the property fails, over the asked variables.

    Example: "^alarm_hours=night_only". This is the c-table answer: it names the
    ambiguity that flips the verdict, instead of one counterexample.
    """
    q = question(table, is_safe)
    if not q:
        v = verdict(table, is_safe)
        return "false" if v == "safe_all" else "true"
    idx = [table.slots.index(n) for n in q]
    bad = sorted({tuple(w[i] for i in idx) for w in table.worlds() if not is_safe(w)}, key=str)
    terms = [" & ".join(f"^{q[j]}={val}" for j, val in enumerate(t)) for t in bad]
    return " | ".join(f"({t})" if len(bad) > 1 and "&" in t else t for t in terms)


def unproposed(table):
    """Worlds that no sample proposed (only possible in independent mode)."""
    return [w for w in table.worlds() if tuple(w) not in table.readings]
