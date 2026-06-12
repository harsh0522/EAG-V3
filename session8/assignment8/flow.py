"""Session 8 — growing-graph orchestrator.

The agent's loop becomes a NetworkX DiGraph. Each node is a skill; edges
carry typed AgentResult payloads. The graph GROWS at runtime via five
actors: the Planner's seed plan, dynamic successors from any skill,
static `internal_successors` from the yaml, Critic auto-insertion on
edges out of `critic:true` skills, and Planner re-invocation on node
failure (gated by `recovery.plan_recovery`). Perception's tool-blindness
contract from S7 is preserved — Planner names skills, never tools.

Persistence lives in persistence.py; skill execution in skills.py;
failure-policy in recovery.py; sandbox in sandbox.py.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid

import networkx as nx

import memory as memory_svc
from gateway import ensure_gateway
from persistence import SessionStore
from recovery import handle_critic_verdict, plan_recovery
from schemas import AgentResult, NodeState
from skills import SkillRegistry, run_skill

MAX_NODES = 60  # hard cap so a Planner loop cannot grow forever


# ── Graph ────────────────────────────────────────────────────────────────────

class Graph:
    """NetworkX DiGraph wrapper. Nodes are str ids `n:<i>`; each node carries
    `skill`, `inputs` (list of str), and `status`."""

    def __init__(self):
        self.g = nx.DiGraph()
        self._counter = 0

    def add_node(self, skill: str, inputs: list[str], metadata: dict | None = None) -> str:
        self._counter += 1
        nid = f"n:{self._counter}"
        self.g.add_node(nid, skill=skill, inputs=list(inputs),
                        metadata=dict(metadata or {}), status="pending")
        for inp in inputs:
            if inp.startswith("n:") and inp in self.g.nodes:
                self.g.add_edge(inp, nid)
        return nid

    def mark(self, nid: str, status: str) -> None:
        self.g.nodes[nid]["status"] = status

    def ready_nodes(self) -> list[str]:
        # A predecessor counts as "satisfied" when it is either complete or
        # skipped (the latter is how a Critic-fail removes a child from the
        # critical path without blocking unrelated branches downstream).
        out = []
        for nid, d in self.g.nodes(data=True):
            if d["status"] != "pending":
                continue
            preds = list(self.g.predecessors(nid))
            if all(self.g.nodes[p]["status"] in ("complete", "skipped") for p in preds):
                out.append(nid)
        return out

    def has_running(self) -> bool:
        return any(d["status"] == "running" for _, d in self.g.nodes(data=True))

    def extend_from(self, src_nid: str, result: AgentResult,
                    *, registry: SkillRegistry) -> list[str]:
        """Splice in dynamic successors, static internal_successors, and
        critic auto-insertion. Returns the list of new node ids.

        Resolves label-based input references (`n:<label>`) against the
        `metadata.label` of nodes added in the same batch. The Planner is
        encouraged to name its nodes by label so it can reference them
        without knowing the integer ids the orchestrator will hand out."""
        added: list[str] = []
        src_def = registry.get(self.g.nodes[src_nid]["skill"])

        # Pass 1: add the new nodes; build a label → assigned-id map.
        label_to_id: dict[str, str] = {}
        pending: list[tuple[str, list[str]]] = []
        for spec in result.successors:
            label = (spec.metadata or {}).get("label")
            new_id = self.add_node(spec.skill, inputs=[],
                                   metadata=spec.metadata)
            added.append(new_id)
            if isinstance(label, str) and label:
                label_to_id[label] = new_id
            pending.append((new_id, list(spec.inputs)))

        # Pass 2: resolve inputs now that every sibling has an id. Translate
        # `n:<label>` to `n:<assigned-id>` if the label matches; pass numeric
        # `n:<i>` references through; pass anything else through unchanged.
        # NOTE: an empty `raw_inputs` is now a legitimate Planner signal for
        # a fan-out worker scoped via `metadata.question` (see planner.md).
        # We do NOT substitute the parent in that case — doing so would dump
        # the parent's full output (which for the Planner contains every
        # sibling's question) back into the worker's INPUTS block and undo
        # the scoping. The structural parent edge is preserved separately
        # below so the graph topology is still correct.
        for new_id, raw_inputs in pending:
            resolved: list[str] = []
            for inp in raw_inputs:
                # `n:<label>` or `n:<int>` form (preferred).
                if inp.startswith("n:"):
                    suffix = inp[2:]
                    if suffix in label_to_id:
                        resolved.append(label_to_id[suffix])
                        continue
                    if suffix.isdigit() and inp in self.g.nodes:
                        resolved.append(inp)
                        continue
                # Bare label form — the Planner sometimes drops the n: prefix.
                if inp in label_to_id:
                    resolved.append(label_to_id[inp])
                    continue
                # Special literal — the user query is always available.
                if inp == "USER_QUERY":
                    resolved.append(inp)
                    continue
                # Artifact handle — pass through, the input renderer handles it.
                if inp.startswith("art:"):
                    resolved.append(inp)
                    continue
                # Unresolvable input — fall back to the parent so the child
                # has at least one upstream dependency to wait on. This still
                # leaks the parent's output into INPUTS, but only when the
                # Planner emitted a bad input name; it is not the fan-out
                # path. A future round may want to fail loudly here instead.
                resolved.append(src_nid)
            self.g.nodes[new_id]["inputs"] = resolved
            for inp in resolved:
                if inp.startswith("n:") and inp in self.g.nodes:
                    self.g.add_edge(inp, new_id)
            # Fan-out worker case: planner emitted inputs=[] on purpose. No
            # data dependency, but we still record the structural parent
            # edge so the executor's `ready_nodes` ordering and replay
            # topology stay coherent.
            if not raw_inputs:
                self.g.add_edge(src_nid, new_id)

        for child_skill in src_def.internal_successors:
            nid = self.add_node(child_skill, inputs=[src_nid])
            added.append(nid)

        # Critic auto-insertion: per the yaml spec ("inserts a Critic node
        # on every outgoing edge from this skill"), splice a Critic in
        # front of every child of this skill — whether that edge was just
        # added dynamically above, or already existed as a Planner-pre-wired
        # static edge (e.g. the Planner's own `distiller -> formatter` edge
        # in its initial plan, which is the normal case for this DAG).
        if src_def.critic:
            for child_nid in list(self.g.successors(src_nid)):
                if self.g.nodes[child_nid]["skill"] == "critic":
                    continue  # already has one (e.g. spliced just above)
                self.g.remove_edge(src_nid, child_nid)
                critic_nid = self.add_node(
                    "critic", inputs=[src_nid],
                    metadata={"target": src_nid, "child": child_nid},
                )
                self.g.add_edge(critic_nid, child_nid)
                added.append(critic_nid)

        return added


_STATUS_ICON = {"complete": "✓", "failed": "✗", "skipped": "⊘",
                "pending": "·", "running": "…"}


def render_dag_ascii(g: nx.DiGraph) -> str:
    """Leveled ASCII view of an executed DAG: one row per topological
    generation, each node tagged with its status icon, skill, and the
    ids of its predecessors. Failed nodes are called out in a summary
    line at the end so a `grep` over the log finds them immediately."""
    lines = [f"┌─ DAG ({g.number_of_nodes()} nodes, {g.number_of_edges()} edges) "
             + "─" * 30]
    failed: list[str] = []
    for level, gen in enumerate(nx.topological_generations(g)):
        for nid in sorted(gen, key=lambda n: int(n.split(":")[1])):
            d = g.nodes[nid]
            icon = _STATUS_ICON.get(d["status"], "?")
            preds = sorted(g.predecessors(nid), key=lambda n: int(n.split(":")[1]))
            arrow = f"  ← {', '.join(preds)}" if preds else ""
            lines.append(f"│ L{level}  {icon}  {nid:6s} {d['skill']:14s}{arrow}")
            if d["status"] == "failed":
                failed.append(nid)
    lines.append("└" + "─" * 58)
    if failed:
        lines.append(f"  ✗ failed node(s): {', '.join(failed)}")
    return "\n".join(lines)


_BOX_CHAR_PRIO = {" ": 0, "─": 1, "│": 1, "┌": 2, "┐": 2, "└": 2, "┘": 2, "►": 3}


def render_dag_box_ascii(g: nx.DiGraph) -> str:
    """Box-and-arrow ASCII view of an executed DAG: nodes are drawn as
    boxes laid out in topological-generation columns, with each edge
    routed through its own vertical lane in the gutter between columns
    (so parallel fan-out/fan-in edges never collide). Line crossings
    render as `┼`. Status icons (see `_STATUS_ICON`) make failed/
    skipped nodes visible at a glance, same as `render_dag_ascii`."""
    gens = list(nx.topological_generations(g))
    col_of: dict[str, int] = {}
    columns: list[list[str]] = []
    for c, gen in enumerate(gens):
        nodes = sorted(gen, key=lambda x: int(x.split(":")[1]))
        columns.append(nodes)
        for n in nodes:
            col_of[n] = c

    def label(n: str) -> str:
        d = g.nodes[n]
        return f"{_STATUS_ICON.get(d['status'], '?')} {n} {d['skill']}"

    box_w = max(len(label(n)) for n in g.nodes) + 4
    box_h = 3
    slot_h = box_h + 2  # +2 row gap for arrow routing
    max_rows = max(len(col) for col in columns)
    grid_h = max_rows * slot_h

    # Size each column gap's gutter to the number of edges crossing it,
    # so every edge gets its own vertical lane.
    gap_edges: list[list[tuple[str, str]]] = []
    for c in range(len(columns) - 1):
        edges = [(u, v) for u in columns[c] for v in g.successors(u)
                 if col_of.get(v) == c + 1]
        gap_edges.append(edges)

    col_x = [0]
    for edges in gap_edges:
        col_x.append(col_x[-1] + box_w + len(edges) + 2)
    grid_w = col_x[-1] + box_w
    canvas = [[" "] * grid_w for _ in range(grid_h)]

    def put(r: int, c: int, ch: str) -> None:
        if not (0 <= r < grid_h and 0 <= c < grid_w):
            return
        cur = canvas[r][c]
        if cur in "─│" and ch in "─│" and cur != ch:
            canvas[r][c] = "┼"
        elif _BOX_CHAR_PRIO.get(ch, 0) >= _BOX_CHAR_PRIO.get(cur, 0):
            canvas[r][c] = ch

    def draw_box(top: int, left: int, text: str) -> None:
        put(top, left, "┌")
        put(top, left + box_w - 1, "┐")
        put(top + 2, left, "└")
        put(top + 2, left + box_w - 1, "┘")
        for i in range(1, box_w - 1):
            put(top, left + i, "─")
            put(top + 2, left + i, "─")
        put(top + 1, left, "│")
        put(top + 1, left + box_w - 1, "│")
        for i, ch in enumerate(text[:box_w - 2].center(box_w - 2)):
            put(top + 1, left + 1 + i, ch)

    pos: dict[str, tuple[int, int]] = {}
    for c, col in enumerate(columns):
        offset_rows = (max_rows - len(col)) / 2
        for i, n in enumerate(col):
            row_top = round((offset_rows + i) * slot_h)
            pos[n] = (row_top, col_x[c])
            draw_box(row_top, col_x[c], label(n))

    for c, edges in enumerate(gap_edges):
        u_right = col_x[c] + box_w - 1
        v_left = col_x[c + 1]
        lane_start = u_right + 2
        for idx, (u, v) in enumerate(edges):
            lane_x = lane_start + idx
            u_row, v_row = pos[u][0] + 1, pos[v][0] + 1
            for cc in range(u_right + 1, lane_x + 1):
                put(u_row, cc, "─")
            r0, r1 = sorted((u_row, v_row))
            for r in range(r0, r1 + 1):
                if canvas[r][lane_x] == " ":
                    put(r, lane_x, "│")
            if v_row > u_row:
                put(u_row, lane_x, "┐")
                put(v_row, lane_x, "└")
            elif v_row < u_row:
                put(u_row, lane_x, "┘")
                put(v_row, lane_x, "┌")
            for cc in range(lane_x, v_left - 1):
                put(v_row, cc, "─")
            put(v_row, v_left - 1, "►")

    return "\n".join("".join(row).rstrip() for row in canvas)


# ── Executor ─────────────────────────────────────────────────────────────────

class Executor:
    def __init__(self, registry: SkillRegistry | None = None):
        ensure_gateway()
        self.registry = registry or SkillRegistry()

    async def run(self, query: str, *, session_id: str | None = None,
                  resume: bool = False) -> str:
        sid = session_id or f"s8-{uuid.uuid4().hex[:8]}"
        store = SessionStore(sid)
        if resume:
            existing = store.read_graph()
            if existing is None:
                raise RuntimeError(f"cannot resume {sid}: no graph.pkl on disk")
            graph_obj = existing
            graph = Graph.__new__(Graph)
            graph.g = graph_obj
            graph._counter = max(
                [int(n.split(":")[1]) for n in graph.g.nodes if n.startswith("n:")] or [0]
            )
            for _, d in graph.g.nodes(data=True):
                if d["status"] == "running":
                    d["status"] = "pending"
            if not query:
                query = store.read_query()
        else:
            store.write_query(query)
            graph = Graph()
            graph.add_node("planner", inputs=["USER_QUERY"])

        print(f"\n{'═' * 78}\nsession {sid}  ─  query: {query}\n{'═' * 78}")
        # Read memory ONCE at session start; the same hits flow into every
        # skill's prompt. The S7 contract is that every cognitive role sees
        # memory; carrying that forward verbatim here is what makes S7's
        # indexing investment continue to pay off in S8.
        memory_hits = memory_svc.read(query) or []
        if memory_hits:
            print(f"[memory.read] {len(memory_hits)} hit(s) visible to every skill this run")
        try:
            memory_svc.remember(query, source="user_query", run_id=sid)
        except Exception as e:
            print(f"[memory.remember] skipped: {e!r}")

        formatter_answer: str | None = None
        executed_count = 0
        # Per-target cap for critic-fail recovery; see P1 #5 fix below.
        recovered_branches: dict[str, bool] = {}
        # NOTES_RUNS round-3 review #5: when the cap fires, the branch is
        # skipped silently and the final answer reflects missing data with
        # no flag. Track every second-or-later critic-fail here so the
        # final log can surface it.
        critic_fail_cap_hit: list[str] = []

        while True:
            ready = graph.ready_nodes()
            if not ready and not graph.has_running():
                break
            if executed_count + len(ready) > MAX_NODES:
                print(f"[flow] node cap {MAX_NODES} hit at {executed_count}; stopping")
                break

            for nid in ready:
                graph.mark(nid, "running")
            store.write_graph(graph.g)

            outcomes = await asyncio.gather(*[self._run_one(nid, graph, sid, query, store, memory_hits)
                                              for nid in ready])

            for nid, result, prompt in outcomes:
                executed_count += 1
                graph.g.nodes[nid]["result"] = result
                graph.mark(nid, "complete" if result.success else "failed")
                store.write_node(NodeState(
                    node_id=nid, skill=graph.g.nodes[nid]["skill"],
                    status=graph.g.nodes[nid]["status"],
                    inputs=graph.g.nodes[nid]["inputs"],
                    result=result, prompt_sent=prompt,
                    started_at=time.time() - result.elapsed_s,
                    completed_at=time.time(),
                ))
                print(f"[{nid}] {graph.g.nodes[nid]['skill']:18s} "
                      f"{graph.g.nodes[nid]['status']:8s} "
                      f"({result.elapsed_s:.1f}s)"
                      + (f"  err={result.error[:80]}" if result.error else ""))

                if result.success:
                    if graph.g.nodes[nid]["skill"] == "critic":
                        if handle_critic_verdict(nid, result, graph,
                                                 recovered_branches,
                                                 critic_fail_cap_hit):
                            continue
                        # verdict == pass: the child is now ready to run.
                    graph.extend_from(nid, result, registry=self.registry)
                    if graph.g.nodes[nid]["skill"] == "formatter":
                        fa = result.output.get("final_answer")
                        if isinstance(fa, str) and fa.strip():
                            formatter_answer = fa
                else:
                    failed_skill = graph.g.nodes[nid]["skill"]
                    decision = plan_recovery(
                        failed_skill=failed_skill,
                        error_text=result.error or "",
                        failed_node_id=nid,
                    )
                    if decision.action == "skip":
                        print(f"  ↪ {nid} failed ({decision.reason}, "
                              f"skill={failed_skill}): {decision.note}")
                        continue
                    # action == "replan"
                    rec_nid = graph.add_node(
                        "planner", inputs=["USER_QUERY"],
                        metadata={"failure_report": decision.failure_report,
                                  "recovers": nid,
                                  "recovery_reason": decision.reason},
                    )
                    print(f"  ↪ recovery ({decision.reason}): planner node "
                          f"{rec_nid} queued for {nid}")

            store.write_graph(graph.g)

        if formatter_answer is None:
            for nid in reversed(list(graph.g.nodes)):
                d = graph.g.nodes[nid]
                if d["status"] == "complete" and isinstance(d.get("result"), AgentResult):
                    formatter_answer = json.dumps(d["result"].output)[:2000]
                    break

        if critic_fail_cap_hit:
            # Loud surface — see review round-3 #5. Without this the cap
            # firing was invisible and the user would just see a thin
            # formatter answer with no explanation of why.
            print(f"\n[flow] WARNING: critic-fail cap hit on "
                  f"{len(critic_fail_cap_hit)} branch(es): "
                  f"{', '.join(critic_fail_cap_hit)}. "
                  f"The final answer reflects missing data from these "
                  f"branches because the Critic rejected the re-planned "
                  f"output too.")
        print(f"\n{render_dag_ascii(graph.g)}\n")
        print(f"\n{render_dag_box_ascii(graph.g)}\n")
        print(f"\n{'═' * 78}\nFINAL: {(formatter_answer or '')[:600]}\n{'═' * 78}\n")
        return formatter_answer or ""

    async def _run_one(self, nid: str, graph: Graph, sid: str, query: str,
                       store: SessionStore, memory_hits: list) -> tuple[str, AgentResult, str]:
        skill_name = graph.g.nodes[nid]["skill"]
        skill = self.registry.get(skill_name)
        fr = graph.g.nodes[nid].get("metadata", {}).get("failure_report")
        store.write_node(NodeState(node_id=nid, skill=skill_name, status="running",
                                   inputs=graph.g.nodes[nid]["inputs"],
                                   started_at=time.time()))
        try:
            result, prompt = await run_skill(skill, nid, graph.g.nodes, sid, query, fr,
                                             memory_hits=memory_hits)
        except Exception as e:  # pragma: no cover - dispatcher fault path
            result = AgentResult(success=False, agent_name=skill_name,
                                 error=f"exception: {type(e).__name__}: {e}")
            prompt = "(exception before prompt-render)"
        return nid, result, prompt


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    resume_sid: str | None = None
    if args and args[0] == "--resume":
        resume_sid = args[1] if len(args) > 1 else None
        query = " ".join(args[2:])
    else:
        query = " ".join(args) or "Say hello in one short sentence."
    asyncio.run(Executor().run(query, session_id=resume_sid, resume=bool(resume_sid)))


if __name__ == "__main__":
    main()
