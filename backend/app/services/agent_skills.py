"""Agent skills: reusable procedures the agent authors from experience.

A skill is a named, parameterized sequence of tool calls stored as data — not executable code —
so it is safe to persist, inspect, and audit. When the agent solves a multi-step task, the
trajectory is generalized into a skill; on a later task a matching skill runs directly instead of
re-planning, and each execution updates usage and success statistics. A skill that repeatedly
fails is deprecated automatically. Storing procedures as data (rather than generated code) keeps
every reused action inspectable and consistent with the platform's governance model.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import ToolContext, ToolResult, build_tool_registry, keyword_tsquery
from app.models import AgentSkill
from app.services.embeddings import EmbeddingClient

# Any free-text content argument belongs here, not just the obvious "query"/"summary" —
# `notes` (meeting_summarize) and `text` (analyze_site_report) carry the actual substance of
# the request. Missing them here was a real, live-reproduced bug: the ORIGINAL meeting/report
# text got baked into the stored plan as a literal value instead of "$goal", so reusing the
# skill for a genuinely different meeting or report silently replayed the old, stale content
# instead of the new one the user actually asked about.
_GOAL_ARG_KEYS = {"query", "summary", "notes", "text"}
_ENTITY_ARG_KEYS = {"supplier_id", "pr_id", "entity_id"}
_MIN_KEYWORD_OVERLAP = 2
# A goal carrying pasted free text (e.g. meeting notes passed to meeting_summarize) can yield
# dozens of keywords; capping keeps a skill's fingerprint specific rather than diluted, so it
# does not later match unrelated goals that merely share a couple of generic words.
_MAX_TRIGGER_KEYWORDS = 10
# Overlap must also be a meaningful share of the smaller keyword set, not just meet the absolute
# floor above — otherwise 2 shared generic words ("project", "delivery") out of a skill's dozen
# keywords would wrongly match a goal for a completely different task.
_MIN_OVERLAP_RATIO = 0.5
_DEPRECATE_AFTER = 3
_DEPRECATE_BELOW_RATE = 0.34
_MAX_NAME_LENGTH = 120
# Keyword overlap alone fragments into a separate skill per phrasing of the same intent — a
# live audit test proved it directly ("how risky is supplier 12" never matched a skill built
# from "assess the risk of supplier 3"). Semantic similarity catches paraphrases keyword
# matching can't. But skill reuse replays a stored plan with NO further judgment — unlike
# document retrieval, where a merely-plausible result is harmless, a weak semantic match
# here would execute the wrong procedure. So it needs its own, higher confidence floor, not
# just "closest in the pool" the way document search works.
# 0.78 is empirically calibrated, not guessed: measured against the real e5-large embedder,
# genuine paraphrases of one skill ("how risky is supplier 12," "check for red flags," "how
# trustworthy has supplier X been") scored 0.798-0.914 cosine similarity against it, while
# unrelated tasks in the SAME construction domain ("review purchase request 11," "any
# overdue RFIs," "summarize the meeting") scored 0.712-0.764 — a clean gap. See
# scripts/debug_skill_similarity.py for the calibration data if this ever needs re-tuning.
_MIN_SEMANTIC_SIMILARITY = 0.78
_SEMANTIC_POOL = 5

# An observation that carries no usable finding. A skill run that produces only these has not
# actually helped, so it counts against the skill's success rate even though nothing errored.
_EMPTY_SIGNALS = (
    "no related", "no documents", "no prior", "no searchable", "not found",
    "no supplier found", "no project found", "no purchase request found",
    "tool call error", "unknown tool", "not authorized",
)


# Retrieval tools almost always return a nearest match, so they are not evidence that a skill
# achieved its goal — only the analysis/action steps are judged for productivity.
_GROUNDING_TOOLS = {"search_memory", "search_documents", "recall_past_sessions"}

# A trajectory built from grounding plus only `remember` reflects "the user asked me to note
# something," never a repeatable analytical procedure. Live testing found this exact shape —
# [search_memory, remember] — later keyword-matched and hijacked an unrelated risk-assessment
# request, silently writing the new question into memory instead of ever computing a risk
# score. `remember` always returns a non-empty confirmation, so such a skill also can never
# fail its own productivity check, meaning it could never self-correct via deprecation either.
# Excluding it from _NON_ANALYTICAL_TOOLS below closes the hijack at its source: it never
# becomes a skill in the first place.
_NON_ANALYTICAL_TOOLS = _GROUNDING_TOOLS | {"remember"}


def _is_productive(observation: str) -> bool:
    text = (observation or "").lower().strip()
    return bool(text) and not any(signal in text for signal in _EMPTY_SIGNALS)


def _run_is_productive(steps: list[dict]) -> bool:
    analysis = [s for s in steps if s["tool"] not in _GROUNDING_TOOLS] or steps
    return any(_is_productive(step["observation"]) for step in analysis)


def _has_analytical_step(steps: list[dict]) -> bool:
    """Whether the trajectory contains at least one real analytical or lookup action, not
    just memory grounding and/or a note taken with `remember`."""
    return any(step["tool"] not in _NON_ANALYTICAL_TOOLS for step in steps)


def _has_conflicting_entity_roles(steps: list[dict]) -> bool:
    """Whether the trajectory calls two DIFFERENT entity-typed tools (for example both
    review_purchase_request's pr_id and assess_supplier_risk's supplier_id). Every entity-typed
    argument templates onto the same single "$entity_id" placeholder (see _tokenize_args), so a
    trajectory using more than one is unsafe to memorialize: on reuse, one new number from the
    new goal would be applied to BOTH roles, even though they refer to unrelated real-world
    records. Live audit testing confirmed the actual failure: reusing such a skill for "purchase
    request 47" also silently assessed the risk of an unrelated "supplier 47" — the two numbers
    only coincided in the original trajectory, not in general. Refuse to create the skill rather
    than risk an id from one entity type being misapplied to another."""
    entity_keys = {
        key
        for step in steps
        for key in (step.get("args") or {})
        if key in _ENTITY_ARG_KEYS
    }
    return len(entity_keys) > 1


def _slug(goal: str) -> str:
    terms = [t for t in keyword_tsquery(goal).split(" | ") if t]
    return ("-".join(terms[:4]) or "agent-skill")[:_MAX_NAME_LENGTH]


def _trigger_keywords(goal: str) -> list[str]:
    terms = [t for t in keyword_tsquery(goal).split(" | ") if t]
    return terms[:_MAX_TRIGGER_KEYWORDS]


def _describe(goal: str) -> str:
    """A generic, reusable description: the goal with specific record numbers removed so it reads
    as a repeatable procedure rather than a one-off request."""
    cleaned = re.sub(r"\b\d+\b", "", goal)
    return re.sub(r"\s+", " ", cleaned).strip() or "Reusable agent procedure"


def _tokenize_args(args: dict) -> tuple[dict, set[str]]:
    templated: dict = {}
    params: set[str] = set()
    for key, value in args.items():
        if key in _GOAL_ARG_KEYS:
            templated[key] = "$goal"
        elif key == "project_id":
            if value is None:
                continue
            templated[key] = "$project_id"
            params.add("project_id")
        elif key in _ENTITY_ARG_KEYS:
            templated[key] = "$entity_id"
            params.add("entity_id")
        else:
            templated[key] = value
    return templated, params


def _resolve_args(
    templated: dict, *, goal: str, project_id: int | None, entity_id: int | None
) -> dict | None:
    out: dict = {}
    for key, value in templated.items():
        if value == "$goal":
            out[key] = goal
        elif value == "$project_id":
            if project_id is None:
                return None
            out[key] = project_id
        elif value == "$entity_id":
            if entity_id is None:
                return None
            out[key] = entity_id
        else:
            out[key] = value
    return out


def _resolve_params(skill: AgentSkill, goal: str, project_id: int | None) -> dict | None:
    ids = re.findall(r"\d+", goal)
    entity_id = int(ids[0]) if ids else None
    for param in skill.parameters or []:
        if param == "project_id" and project_id is None:
            return None
        if param == "entity_id" and entity_id is None:
            return None
    return {"project_id": project_id, "entity_id": entity_id}


def _success_rate(skill: AgentSkill) -> float:
    usage = skill.usage_count or 0
    # An unproven skill is given the benefit of the doubt so it can build a track record.
    return (skill.success_count or 0) / usage if usage else 1.0


async def _semantic_candidates(
    db: AsyncSession, embedder: EmbeddingClient, goal: str
) -> dict[int, float]:
    """Active skills whose stored embedding is close enough to the goal to be trusted as a
    match, keyed by id -> similarity (1 - cosine distance). Restricted to a small pool and
    gated by _MIN_SEMANTIC_SIMILARITY rather than "closest available," since an unqualified
    nearest-neighbour is always something — reuse must not fire on a merely-closest skill
    that isn't actually a good match."""
    query_vector = await embedder.embed_query(goal)
    distance = AgentSkill.embedding.cosine_distance(query_vector)
    stmt = (
        select(AgentSkill.id, distance)
        .where(AgentSkill.status == "active", AgentSkill.embedding.is_not(None))
        .order_by(distance)
        .limit(_SEMANTIC_POOL)
    )
    rows = list(await db.execute(stmt))
    return {
        skill_id: similarity
        for skill_id, dist in rows
        if (similarity := 1 - dist) >= _MIN_SEMANTIC_SIMILARITY
    }


async def find_matching_skill(
    db: AsyncSession, embedder: EmbeddingClient, goal: str
) -> AgentSkill | None:
    """Hybrid match: keyword overlap (exact, cheap, the original mechanism) plus embedding
    similarity (catches paraphrases keyword overlap cannot — proven live to matter: "how
    risky is supplier 12" shares no words with "assess the risk of supplier 3" but means the
    same thing). Keyword matches are ranked first when present — exact lexical evidence is
    trusted over a semantic inference — semantic candidates fill in goals keyword matching
    would otherwise miss entirely."""
    keywords = {t for t in keyword_tsquery(goal).split(" | ") if t}
    skills = list(await db.scalars(select(AgentSkill).where(AgentSkill.status == "active")))
    if not skills:
        return None

    keyword_matches: dict[int, int] = {}
    if keywords:
        for skill in skills:
            trigger = set(skill.trigger_keywords or [])
            if not trigger:
                continue
            overlap = len(keywords & trigger)
            ratio = overlap / min(len(keywords), len(trigger))
            if overlap >= _MIN_KEYWORD_OVERLAP and ratio >= _MIN_OVERLAP_RATIO:
                keyword_matches[skill.id] = overlap

    semantic_matches = await _semantic_candidates(db, embedder, goal)

    candidate_ids = set(keyword_matches) | set(semantic_matches)
    if not candidate_ids:
        return None

    by_id = {skill.id: skill for skill in skills}
    ranked = sorted(
        candidate_ids,
        key=lambda i: (
            keyword_matches.get(i, 0),
            semantic_matches.get(i, 0.0),
            _success_rate(by_id[i]),
        ),
        reverse=True,
    )
    return by_id[ranked[0]]


async def execute_skill(
    db: AsyncSession, ctx: ToolContext, skill: AgentSkill, *, goal: str, project_id: int | None
) -> tuple[list[dict], list[dict]] | None:
    resolved = _resolve_params(skill, goal, project_id)
    if resolved is None:
        return None
    registry = build_tool_registry()
    steps: list[dict] = []
    sources: list[dict] = []
    # Tracks whether the skill's own plan is intact and executable — a tool that no longer
    # exists, an argument that can't be resolved, or a real call error. This is distinct from
    # whether THIS particular request happened to reference a missing record or a role that
    # isn't authorized: those reflect the request, not a defect in the skill, and must not
    # erode its standing (live testing found two accidental nonexistent-id calls were enough
    # to deprecate a skill with a perfect track record).
    mechanically_broken = False
    for index, plan_step in enumerate(skill.plan or []):
        tool = registry.get(plan_step.get("tool", ""))
        if tool is None:
            mechanically_broken = True
            continue
        args = _resolve_args(
            plan_step.get("args", {}), goal=goal,
            project_id=resolved["project_id"], entity_id=resolved["entity_id"],
        )
        if args is None:
            mechanically_broken = True
            continue
        # A stored skill replays whatever tools it was built from; it must be re-authorized
        # against the CURRENT user's role on every reuse — a skill authored by one role must
        # never let a different, less-privileged role bypass that tool's own restriction.
        if not tool.allowed_for(ctx.user_role):
            steps.append({
                "index": index,
                "thought": f"Reusing skill '{skill.name}' (step {index + 1}).",
                "tool": tool.name, "args": args,
                "observation": tool.unauthorized_message(ctx.user_role),
                "sources": [],
            })
            continue
        try:
            result = await tool.run(ctx, **args)
        except TypeError as exc:
            result = ToolResult(summary=f"Tool call error: {exc}")
            mechanically_broken = True
        steps.append({
            "index": index,
            "thought": f"Reusing skill '{skill.name}' (step {index + 1}).",
            "tool": tool.name, "args": args,
            "observation": result.summary, "sources": result.sources,
        })
        sources.extend(result.sources)

    # A run only counts as a success if every planned step ran AND its analysis produced a real
    # finding — a skill that returns nothing useful should lose standing, not be rewarded.
    productive = _run_is_productive(steps)
    # Only update the skill's statistics when this run actually says something about the
    # skill's OWN quality: either it worked (productive), or its plan is genuinely broken
    # (mechanically_broken). A merely unauthorized or not-found outcome is neutral — it says
    # nothing about whether the skill itself is good, so it must not count toward usage or
    # success at all, in either direction.
    if productive or mechanically_broken:
        skill.usage_count = (skill.usage_count or 0) + 1
        if productive and not mechanically_broken:
            skill.success_count = (skill.success_count or 0) + 1
        if skill.usage_count >= _DEPRECATE_AFTER:
            rate = (skill.success_count or 0) / skill.usage_count
            if rate < _DEPRECATE_BELOW_RATE:
                skill.status = "deprecated"
    await db.flush()
    return steps, sources


async def set_skill_status(db: AsyncSession, skill_id: int, status: str) -> AgentSkill | None:
    """Admin lever to deprecate a misbehaving skill (stops it from matching new goals in
    `find_matching_skill`, which only considers status=="active") or reactivate one, without
    needing raw SQL — the manual intervention audit testing has otherwise required."""
    skill = await db.get(AgentSkill, skill_id)
    if skill is None:
        return None
    skill.status = status
    await db.flush()
    return skill


async def delete_skill(db: AsyncSession, skill_id: int) -> bool:
    """Hard removal for a skill with no run history referencing it. A skill any agent_run has
    ever used or created cannot be removed this way (the FK raises, translated to 409 by the
    app's global IntegrityError handler, the same FK-safe pattern every other entity delete
    uses) — deprecating is the correct lever once a skill has real history."""
    skill = await db.get(AgentSkill, skill_id)
    if skill is None:
        return False
    await db.delete(skill)
    await db.flush()
    return True


async def synthesize_skill(
    db: AsyncSession,
    embedder: EmbeddingClient,
    *,
    goal: str,
    steps: list[dict],
    project_id: int | None,
) -> AgentSkill | None:
    # A trajectory that never actually found or produced anything useful (an empty search, a
    # "not found" lookup) should not be memorialized as a reusable procedure — the same bar
    # applied to a skill's success on reuse is applied here at the moment it would be born.
    # Nor should one that never did anything beyond grounding and taking a note — see
    # _NON_ANALYTICAL_TOOLS above for why that shape is actively unsafe to reuse. Nor one that
    # touched two different entity types (see _has_conflicting_entity_roles) — reuse would
    # apply a single new id to both, misapplying it to whichever one it doesn't belong to.
    if (
        len(steps) < 2
        or not _run_is_productive(steps)
        or not _has_analytical_step(steps)
        or _has_conflicting_entity_roles(steps)
    ):
        return None
    name = _slug(goal)
    plan: list[dict] = []
    params: set[str] = set()
    for step in steps:
        templated, needed = _tokenize_args(step.get("args", {}) or {})
        plan.append({"tool": step["tool"], "args": templated})
        params |= needed

    description = _describe(goal)
    (embedding,) = await embedder.embed_documents([description])

    existing = await db.scalar(select(AgentSkill).where(AgentSkill.name == name))
    if existing is not None:
        if existing.status != "deprecated":
            return None
        # The pattern recurred after this skill was retired: re-learn it from the fresh
        # trajectory, reactivate it, and reset its record as a new version.
        existing.plan = plan
        existing.parameters = sorted(params)
        existing.trigger_keywords = _trigger_keywords(goal)
        existing.description = description
        existing.embedding = embedding
        existing.status = "active"
        existing.version = (existing.version or 1) + 1
        existing.usage_count = 0
        existing.success_count = 0
        await db.flush()
        return existing

    skill = AgentSkill(
        name=name,
        description=description,
        trigger_keywords=_trigger_keywords(goal),
        plan=plan,
        parameters=sorted(params),
        embedding=embedding,
        created_by="agent",
        status="active",
        usage_count=0,
        success_count=0,
        version=1,
    )
    db.add(skill)
    await db.flush()
    return skill
