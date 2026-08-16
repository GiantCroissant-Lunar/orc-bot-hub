Today 3:40 AM
‘
https://github.com/PrimeIntellect-ai/prime-agent/tree/main’ check it and compare to orc-bot

Yes. After looking through the current main of PrimeIntellect-ai/prime-agent and comparing it with the current fresh Orc Bot implementation, I think Prime Agent is unusually relevant—but it should not become the architectural model for Orc Bot as a whole.

The useful way to think about them is:

Prime Agent is primarily an advanced agent runtime.
Orc Bot is becoming a development-resource orchestrator.

Those are complementary layers.

Prime Agent is much further ahead in long-lived agent execution, daemon/session recovery, recursive subagents, agent-to-agent messaging, context continuity, skills, and client protocols. Orc Bot is much stronger in source authority, fenced workspaces, immutable candidates, work-item DAGs, validation/tool slots, explicit acceptance, provider-neutral orchestration, and game-development resource separation. Prime's own repository does not try to solve the Unity Library / Godot .godot / persistent-editor problem that motivated Orc Bot.

Architectural comparison
Area	Prime Agent	Current Orc Bot	My assessment
Fundamental object	AgentSession / root agent family	WorkflowRun → WorkItem → attempt/resource/candidate	Different layers
Concurrency	Recursive RLM child-agent tree	Work-item DAG with dependency candidates	Orc model is better for engineering orchestration
Runtime lifecycle	Detached daemon + one worker per root agent tree	Akka.NET supervision currently inside composed app/runtime	Prime has something Orc should borrow
UI boundary	AgentConnection → daemon transport → worker	Godot host → runtime/application boundaries	Prime boundary is more mature
Agent execution	Native Prime agent/model runtime	External real agent CLIs behind machine-channel adapters	Orc is more provider-neutral
Terminal	Own TUI; daemon owns execution	Zellij is presentation; machine channel owns semantic truth	Orc separation is better for heterogeneous CLIs
ACP	First-class ACP agent mode	ACP bridge/provider path	Prime has a very useful reference implementation
MCP	MCP services exposed through Python skills	Intended tool/capability interoperability	Different use; don't merge ACP and MCP concepts
Rich native protocol	Prime RPC + JSON modes + daemon protocol	Orc typed contracts/machine channels	Orc should similarly keep multiple protocol roles
Subagents	rlm() recursively creates child agents	agents assigned to DAG work items	Both are useful, but not equivalent
Memory	Continual Harness: prompt/memory/skill/subagent refinements	Mem0 scoped long-term memory + immutable loadouts	Orc governance is stronger; Prime refinement loop is useful
Skills	Agent Skills + executable Python-backed skills	Typed Skill/Rule/Tool/Context/Memory/Permission loadouts	Prime has stronger executable skill mechanics
Workspace	Runs in current directory; recommends clone/worktree	Fenced Git allocation + source generation + immutable candidate	Orc is substantially stronger
Parallel workspace policy	Repo rules explicitly allow multiple agents in one worktree	Allocation is owned/fenced per attempt/work item	Prime approach unsuitable for Orc's game-dev requirement
Candidate lifecycle	Mostly working-directory/session-oriented	Candidate is digest-addressed immutable handoff	Orc stronger
Validation	Quality gates inside autonomous agent loop	Separate validation authority/slot/receipts	Orc stronger
Human decision	Agent completion/quality gates	Completion ≠ candidate acceptance ≠ validation ≠ integration	Orc stronger
Tool/editor derived state	No generalized tool-slot model	Validation/tool authority and layered workspace model	Core Orc differentiator
Persistence	JSONL transcripts, artifacts, journals, harness files	SQLite operational truth + evidence artifacts	Different goals
Recovery	Very sophisticated session/supervisor recovery	Akka + SQLite/resource reconciliation	Prime has valuable patterns
Security	Explicitly not a sandbox	Process containment/fences/default-deny orchestration, also not necessarily OS sandbox	Orc should preserve its stricter authority model
Product UI	TUI	Godot GraphEdit, timeline, multi-window operator UI	Orc is aiming much broader

Prime's architecture is explicitly split into client → AgentConnection → daemon supervisor → session worker → AgentSessionRuntime → persistent kernel/subagents. The client owns rendering and input, while the worker owns actual execution.

That separation is probably the single most important idea for Orc Bot to absorb.

1. Prime Agent gives strong evidence that Orc Bot should move the runtime out of Godot

Current Orc Bot deliberately keeps its application/runtime boundary framework-neutral, with Godot being presentation/composition rather than durable authority. But the current fresh line still composes the live orchestration runtime close to the Godot application, while its ADR leaves a future daemon as a later decision.

Prime Agent demonstrates a mature version of exactly that future boundary.

Its daemon has:

stable client and command identities;
worker processes independent of the TUI;
reconnect/reattach;
worker adoption after supervisor replacement;
generation-aware event cursors;
snapshots as the recovery baseline;
mutation journals and idempotency;
explicit uncertain outcomes rather than blindly replaying a possibly-executed mutation;
attachment-local backpressure;
per-session scheduling;
process recovery;
coordinated two-phase update/checkpoint handling.

The particularly good concept is:

{ generation, sequence }

rather than a naked event sequence.

When a worker generation changes, an old sequence cannot be accidentally compared to the new worker's sequence. The client either catches up or receives a coherent replacement snapshot.

I would now seriously consider changing Orc Bot toward:

                    ┌──────────────────────┐
                    │      Godot UI        │
                    │ Graph / Timeline /   │
                    │ Terminal / Windows   │
                    └──────────┬───────────┘
                               │
                        OrcConnection
                               │
                  versioned local protocol
                               │
                    ┌──────────▼───────────┐
                    │   orc-runtime daemon │
                    │                      │
                    │ Akka.NET             │
                    │ SQLite               │
                    │ WorkItem DAG         │
                    │ Resource authorities │
                    │ Candidate authority  │
                    │ Validation slots     │
                    └──────────┬───────────┘
                               │
                    Agent Provider Gateway
             ┌─────────────────┼──────────────────┐
             │                 │                  │
           Codex             Claude          Prime Agent
           ACP/JSONL          ACP/...            ACP/RPC
             │                 │                  │
             └─────────────────┼──────────────────┘
                               │
                    optional Zellij views

Akka.NET does not get replaced by Prime's daemon design.

Akka remains Orc Bot's domain/lifecycle supervisor. The daemon is a process and client boundary around the actor system.

That is a much cleaner combination.

2. Prime's RLM tree should complement, not replace, Orc Bot's DAG

Prime Agent's headline feature is its RLM architecture. Every root session can have a persistent IPython kernel and recursively launch subagents using:

handle = await rlm("inspect the API", name="api-reviewer")

Importantly, the returned handle means the child was admitted, not that it completed. Results come later through explicit agent messaging or artifacts.

That is a very good lifecycle distinction.

But Prime models something like:

Root Agent
├── Child A
├── Child B
│   └── Child B.1
└── Child C

Orc Bot models:

Work A ─────────┐
                ├──> Work D
Work B ──> Work C

with each node potentially carrying:

source generation
workspace allocation
fence
loadout
agent session
candidate
candidate dependencies
validation requirements
resource claims

These should not be collapsed.

The clean conceptual distinction is:

RLM/subagent tree = cognitive delegation.
Orc WorkItem DAG = resource-owning engineering work.

A Prime child asking another agent to “research this API” might remain entirely inside one Orc work-item.

But if the child says effectively:

“I need to modify another repository.”

or:

“I need my own candidate, Unity slot, writable source allocation, different permissions, or different agent loadout.”

then it should cross an Orc Bot boundary.

Something like:

provider internal delegation
        │
        │ resource requirement exceeds current attempt
        ▼
work.spawn.request
        │
        ▼
Orc Bot planner / Akka
        │
        ├─ new WorkItem
        ├─ resource claims
        ├─ AgentLoadout
        ├─ SourceWorkspaceAllocation
        └─ candidate dependency

That could become an extremely powerful distinction.

It lets an agent recursively reason without turning every thought into heavyweight orchestration, while Orc Bot remains in authority whenever delegation acquires real engineering resources.

3. Prime Agent itself should probably become an Orc Bot provider

This is the most immediately practical conclusion.

Prime Agent already implements ACP:

prime-agent --mode acp

with standard JSON-RPC semantics for initialize, session creation, prompt, cancellation, and close.

So instead of merely borrowing its ideas, Orc Bot could eventually have:

AgentProvider
 ├─ codex
 ├─ claude-code
 ├─ opencode
 ├─ ...
 └─ prime-agent

and launch Prime in exactly the same fenced Orc Bot source allocation that another CLI receives.

The semantic ownership would remain:

Orc Bot
    owns work item
    owns source allocation
    owns fence
    owns loadout
    owns candidate publication
    owns validation
    owns acceptance/integration


Prime Agent
    owns its internal agent turn
    owns RLM children
    owns its IPython runtime
    owns its model interaction

That's a very good boundary.

Prime's ACP extension mechanism makes this especially attractive.

Rather than corrupting standard ACP with custom fields, it puts Prime-specific concepts such as RLM children, goals, gates, compaction, refinement, and heartbeats under a reverse-domain _meta namespace. Standard ACP clients simply ignore it.

Orc should imitate that pattern.

For example:

{
  "_meta": {
    "dev.orc-bot": {
      "operationId": "...",
      "workItemId": "...",
      "allocationId": "...",
      "candidatePolicy": "publish-on-semantic-completion"
    }
  }
}

while leaving ACP itself interoperable.

4. ACP, MCP and Orc-native protocol should remain three different things

Prime Agent actually clarifies something we've discussed before.

It does not try to turn every protocol into one universal protocol.

Prime has ACP, its own richer RPC/JSON surfaces, its internal daemon protocol, and MCP integration for external services.

That's a better way to think about Orc Bot too.

ACP
= control an agent session


MCP
= expose/use tools and external capabilities


Orc runtime protocol
= control Orc-specific orchestration:
  work items
  candidates
  resource leases
  validation
  decisions
  topology
  evidence

Trying to make one of those replace the other two would weaken the model.

Prime's MCP design is interesting in another way: MCP tools are not injected as dozens of separate model tools. They appear as Python skill APIs inside the persistent IPython environment.

That is elegant for Prime because its central model-facing abstraction is:

one programmable Python environment

I would not force that on Orc Bot globally, because Orc needs to support Codex, Claude Code, OpenCode, Prime Agent and others with their own tool models.

But it is an excellent provider capability.

5. Continual Harness contains an excellent idea for Orc Bot's Mem0 design

Prime's /refine mechanism is more interesting than ordinary “agent memory.”

Its harness can contain:

prompt
memory
skill
subagent specification

and refinement operations are explicit:

create
update
delete

with rationale, expected outcome, previous/new state and refinement history. The immutable base system prompt is deliberately not rewritten.

This should not replace Mem0 in Orc Bot.

Current Orc Bot has a more rigorous model:

installation
project
agent
work item
session

memory scopes, with retrieved memory treated as untrusted context rather than authority; tools and permissions remain explicit typed grants. The current code also freezes the exact profile/loadout/context/memory digests into an attempt.

I prefer the Orc design.

But Prime suggests how memory can improve safely.

Instead of letting an agent directly mutate global memory/profile/rules, Orc could introduce:

RefinementCandidate
    source attempt
    evidence
    target scope
    proposed type
        Memory
        Rule
        Skill
        SubagentProfile
        Context
    before digest
    proposed digest
    rationale
    validation evidence

then:

proposed
   ↓
reviewed
   ↓
accepted / rejected
   ↓
promoted

That turns “self-improvement” into the same candidate philosophy Orc already uses for source code.

I think this is much more Orc-like than copying /refine literally.

6. Prime's skills are worth studying very closely

Prime supports the Agent Skills format plus Python-backed executable skills.

It uses progressive disclosure:

system context
    → skill name + description


when needed
    → load SKILL.md


if Python-backed
    → import actual package
    → call actual function

Current Orc Bot already separates:

Skill
Rule
Tool
Context
Memory
Permission

inside an immutable AgentLoadout.

I would keep that model, but extend Skill into two distinguishable things:

SkillDefinition
    semantic instructions
    provenance
    digest


SkillImplementation
    kind:
       markdown
       python
       cli
       mcp
       csharp
       comfyui
       ...
    executable artifact
    dependency manifest
    permissions required
    admitted tools
    content digest

Prime has a very good lesson here:

An executable skill and a remembered description of a skill are not the same thing.

Its documentation explicitly distinguishes installed Python skills from Continual Harness skill descriptions.

That distinction fits Orc Bot extremely well.

7. Prime's long-running mechanisms may reduce the need to jump directly to GOAP/HTN

Prime already has four simple concepts:

persistent goal
heartbeat
schedule
bounded autonomous continuation

along with direct agent messaging.

These cover a surprising amount of behavior that people sometimes immediately model with a planner.

For example:

goal
    "get CI green"


autonomous continuation
    run → gate fails → continue


heartbeat
    periodically inspect external state


schedule
    retry/check later


agent message
    ask another worker to investigate

Orc Bot can then reserve:

DAG
GOAP
HTN

for cases that genuinely require planning/resource reasoning.

This fits the principle already present in Orc Bot: use the smallest planner appropriate to the work.

8. Where Orc Bot is fundamentally ahead of Prime Agent

This is perhaps the most important part of the comparison.

Prime Agent's README effectively says:

run it inside the repository/directory you want it to work in; use a disposable clone or clean worktree if appropriate.

And its own AGENTS.md explicitly describes multiple parallel agents working on different files inside the same worktree, relying on rules such as “only stage files you changed” and “never reset/stash/add all.”

That is almost the exact problem Orc Bot was created to go beyond.

Prime does understand Git worktrees mechanically—its Git code detects normal repos and worktree .git indirection—but a worktree is environmental Git context, not a fenced orchestration resource.

Prime has no equivalent general model for:

SourceAuthority
SourceWorkspaceAllocation
source generation
allocation fence


ComponentCandidate
candidate composition


ToolAuthoritySlot
persistent Unity Library
persistent Godot .godot
persistent Unreal derived state


validation receipt
human candidate disposition
single integration authority

Current Orc Bot explicitly does.

So do not move Orc Bot toward Prime's workspace model.

That would throw away Orc Bot's most distinctive architectural advantage.

9. Prime's latest change actually reinforces Orc Bot's philosophy

I checked current main, not merely the docs.

The current head I inspected is 97b994c3 from August 14, 2026, and the latest major daemon work establishes a supervisor-owned RLM spawn ledger as the authority for agent-family topology. The implementation lives in rlm-ledger.ts.

This is interesting because Prime itself is moving from:

session says who its children are

toward:

higher-level supervisor owns durable family topology

That is directionally the same architectural lesson Orc Bot has been applying repeatedly:

A participant should not be authoritative for the topology that governs it.

For Orc Bot that principle goes further:

Agent does not own work topology.
Agent does not own source authority.
Agent does not own candidate acceptance.
Agent does not own validation truth.
Agent does not own integration.

Prime's latest change strengthens, rather than undermines, that architecture.

What I would change in Orc Bot after studying Prime Agent

I would make seven changes, in roughly this order:

Bring the daemon/runtime boundary forward. Make orc-runtime an independent local process containing Akka.NET + SQLite + authorities, and turn Godot into an OrcConnection client. Borrow Prime's generation cursors, snapshot recovery, idempotent command journal, uncertain-state semantics and attachment recovery.
Add Prime Agent as a real ACP provider rather than merely copying its architecture. This would immediately test whether Orc Bot's provider/loadout/session abstractions really are generic.
Introduce a formal provider-internal-subagent boundary. RLM children remain internal unless they request an independently governed resource; then Orc promotes the request to a WorkItem.
Use ACP _meta-style namespaced extensions. Keep standard ACP standard. Orc-specific and provider-specific metadata should be additive and ignorable.
Add refinement candidates around Mem0/loadouts. Borrow Prime's evidence-backed /refine concept, but route promotions through Orc Bot's candidate/review authority rather than allowing uncontrolled shared-state mutation.
Expand Skill from prose to admitted executable artifacts. Agent Skills-compatible Markdown can remain one frontend; Python/MCP/CLI/C#/ComfyUI implementations become separately digest-addressed capability implementations.
Add simple goal/heartbeat/schedule/continuation primitives before making GOAP/HTN responsible for routine persistence. DAG/GOAP/HTN should remain structural planners, not substitutes for “wake me up in ten minutes” or “keep going until this validation gate passes.”
Overall

If I position the projects on a stack, I would put them here:

                     Orc Bot
         ┌──────────────────────────────┐
         │ Work taxonomy / WorkItem DAG │
         │ GOAP / HTN / graph planning  │
         │ Resource claims              │
         │ Source allocations           │
         │ Candidate composition        │
         │ Tool/editor authority slots  │
         │ Validation / disposition     │
         │ Integration authority        │
         └──────────────┬───────────────┘
                        │
              Agent execution contract
                        │
        ┌───────────────┼────────────────┐
        │               │                │
      Codex          Claude/etc.     Prime Agent
                                        │
                              ┌─────────▼─────────┐
                              │ Agent session     │
                              │ RLM children      │
                              │ IPython           │
                              │ skills            │
                              │ goals/schedules   │
                              │ continual harness │
                              └───────────────────┘

So I would not choose Prime Agent instead of Orc Bot.

I would use Prime Agent as:

(a) a reference architecture for Orc Bot's missing durable daemon/client layer,
(b) a reference for recursive cognitive agents and long-running sessions, and
(c) eventually, one of the most sophisticated agent providers that Orc Bot can orchestrate.

And I would keep Orc Bot's current source/candidate/tool-authority design above it. That combination is substantially more interesting than either architecture by itself.