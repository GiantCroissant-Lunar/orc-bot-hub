Yes. I think this should change the bootstrap architecture slightly.

The key is that Orc Bot should be operable by another agent before the Godot UI exists. And I would distinguish two directions:

Direction	Best interface
Human/script/agent → Orc Bot	CLI + MCP
Orc Bot → coding agent	ACP, provider-native structured protocol, or JSONL
Editor/IDE → Orc Bot-as-an-agent	ACP server can be added if useful
Godot UI → Orc Bot	Same internal command/query surface

MCP is designed specifically for exposing resources and model-invokable tools, and the official C# SDK supports both clients and servers. The current MCP specification has also continued evolving, including support around longer-running task-style interactions, which aligns well with Orc Bot operations. ACP solves a somewhat different problem: standardized communication between coding agents and their clients/editors, including streaming session interaction.

So I would not choose MCP versus ACP globally. They belong on different sides of Orc Bot.

Bootstrap architecture

I would aim for this almost immediately:

                      external agent
                   ┌───────┴────────┐
                   │                │
                MCP client      shell / CLI
                   │                │
                   ▼                ▼
              ┌─────────────────────────┐
              │  Orc Bot ingress        │
              │                         │
              │  MCP adapter    CLI     │
              └───────────┬─────────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ Orc Application   │
                │                   │
                │ submit task       │
                │ inspect task      │
                │ inspect candidate │
                │ cancel            │
                │ accept / reject   │
                │ events / evidence │
                └─────────┬─────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │    Orc Core     │
                 │                 │
                 │ source layers   │
                 │ operations      │
                 │ candidates      │
                 │ persistence     │
                 │ permissions     │
                 └────────┬────────┘
                          │
                    provider gateway

The important part is that CLI, MCP and eventually Godot do not implement different workflows. They are adapters over the same application commands.

Something like:

SubmitTask
GetTask
ListTasks
CancelTask


GetCandidate
GetCandidateDelta
AcceptCandidate
RejectCandidate


GetEvidence
SubscribeEvents

That becomes Orc Bot's real API.

The current implementation was already moving toward transport-neutral command ingress and says MCP/ACP adapters could submit the same activation request, but the actual external MCP/ACP ingress endpoint had not yet landed. And the newer implementation already has ACP bridge/machine-channel code on the provider side. I would preserve that conceptual distinction in the restart rather than mixing the two.

CLI should probably come first

For dogfooding, the CLI is actually the most important initial interface.

Not a pretty interactive CLI initially. A boring, deterministic, machine-readable CLI:

orc task submit \
  --repo . \
  --goal "Add source-layer diagnostics" \
  --json

returns:

{
  "taskId": "task_01...",
  "operationId": "op_01...",
  "state": "submitted"
}

Then:

orc task get task_01... --json
orc candidate get candidate_01... --json
orc candidate diff candidate_01...
orc candidate accept candidate_01...
orc candidate reject candidate_01... --reason "wrong approach"
orc task cancel task_01...

I would establish very strict CLI rules:

stdout  = machine-readable result
stderr  = diagnostics
exit    = stable documented exit code


--json  = no decoration, no ANSI, no prompts

This means any existing coding agent that can execute shell commands can use Orc Bot immediately, even before MCP is implemented.

So the self-development bootstrap can already look like:

Codex / Claude / OpenCode
          │
          │ executes
          ▼
      orc task submit ...
          │
          ▼
        Orc Bot
          │
          │ delegates
          ▼
     another agent
          │
          ▼
       candidate
          │
          ▼
lead agent/human inspects it

That is genuine dogfooding extremely early.

Then MCP becomes a thin adapter

Once those application commands exist, MCP should be almost boring.

For example:

MCP tools


orc_task_submit
orc_task_cancel


orc_candidate_accept
orc_candidate_reject

and read-oriented state can naturally be exposed as resources such as:

orc://tasks/<task-id>
orc://operations/<operation-id>
orc://candidates/<candidate-id>
orc://candidates/<candidate-id>/delta
orc://evidence/<operation-id>

This matches MCP's distinction between Resources for contextual data and Tools for model-invoked actions.

But crucially:

MCP tool
     │
     ▼
authorization
     │
     ▼
same SubmitTask handler

not:

MCP implementation
     │
     └── directly edits database/workspace/git

So an external agent doesn't obtain more authority simply because it came through MCP.

For example, the default external-agent profile could allow:

task.submit
task.inspect
candidate.inspect
candidate.comment

while withholding:

candidate.accept
candidate.integrate
slot.force-reset
authority.release

Those can require a stronger capability or human decision.

ACP belongs mainly on the other side

This is where I think the distinction becomes especially useful.

ACP describes a standardized relationship between an agent and an agent client, much like LSP standardized editor/language-server integration.

So when Orc Bot launches a coding agent:

Orc Bot
   │
 ACP client
   │
   ▼
Codex / Gemini / Claude adapter / etc.

ACP can carry session lifecycle, prompts, streamed updates and other agent/client interaction.

This is much cleaner than Orc Bot trying to infer semantics from PTY output.

And the existing Orc Bot line had already converged toward exactly that idea: Zellij/terminal output is presentation, while ACP or another typed machine channel supplies semantic agent events.

If later we want this:

Zed / JetBrains / another ACP client
                │
                ▼
             Orc Bot

then Orc Bot can additionally implement the ACP agent side and present itself as an orchestration agent. ACP now has standardized session-related facilities and an evolving ecosystem of agent/client implementations, so that could become valuable.

But I would not require that for bootstrap.

Therefore my proposed v0 is very specific

I would make the first fresh implementation only:

Orc.Core
Orc.Application
Orc.Persistence.Sqlite
Orc.Source
Orc.Agent
Orc.Agent.Acp
Orc.Cli
Orc.Mcp

with dependency direction roughly:

                 Orc.Cli
                    │
                 Orc.Mcp
                    │
                    ▼
             Orc.Application
                    │
             ┌──────┴──────┐
             ▼             ▼
          Orc.Core      contracts
             │
      ┌──────┼────────┐
      ▼      ▼        ▼
 Persistence Source   Agent
                       │
                    Agent.Acp

Orc.Cli and Orc.Mcp contain zero orchestration policy.

ACP contains zero workflow policy.

SQLite contains zero workflow policy.

They implement ports.

That keeps the restart much smaller than the current architecture.

And I think this gives us an even better definition of the first self-hosting milestone:

External development agent
          │
     CLI or MCP
          │
          ▼
       Orc Bot
          │
    ACP / typed CLI
          │
          ▼
    worker agent
          │
          ▼
 immutable candidate

Then the external development agent can inspect that candidate through the same Orc Bot interface and continue developing Orc Bot.

That is substantially stronger dogfooding than merely having Orc Bot launch an agent internally.

So for the fresh attempt, I would make CLI + MCP server part of the bootstrap, and ACP client/provider support part of the first real-agent execution path. Godot becomes another client after those boundaries work.

Yesterday 5:21 PM
I think memory mem0 is also important in initial attempt

Yes. I would revise the proposed bootstrap again: Mem0 should be in the initial dogfood-capable Orc Bot, not added several milestones later.

The current attempt actually reached a fairly good conceptual model for memory: Mem0 is long-term recall, not operational truth; retrieved memory is untrusted context; agent writes are memory candidates; and permissions/lifecycle cannot be granted by memory. The existing contracts even model IMemorySource separately from promotion policy and explicitly state that retrieved memory cannot settle attempts, grant permissions, or mutate source.

What I would change is when we introduce it. The current staged plan puts scoped Mem0 after profiles, UI, Agent Framework and the first provider integration. For a dogfood-first restart, that is too late.

The initial Orc Bot should therefore have five essential capabilities
                    ┌───────────────┐
                    │ External agent│
                    └───────┬───────┘
                            │
                     CLI / MCP
                            │
                            ▼
                 ┌────────────────────┐
                 │      Orc Core      │
                 └────┬─────┬─────┬──┘
                      │     │     │
              source  │     │     │ memory
              layers  │     │     ▼
                      │     │   Mem0
                      │     │
                      │     ▼
                      │  agent execution
                      │   ACP / JSONL
                      │
                      ▼
                   candidate

So bootstrap is approximately:

1. CLI
2. MCP server
3. ACP/provider machine channel
4. Mem0 memory
5. source-layer + candidate loop

SQLite can remain the small operational store underneath these.

That is enough for Orc Bot to start helping develop itself.

Why memory matters especially for dogfooding

Without memory, every new Orc Bot agent invocation starts substantially from scratch.

Suppose the first five self-development tasks discover:

task 1:
"Godot validation needs this particular command"


task 2:
"Do not put .godot inside agent source layers"


task 3:
"ACP provider X reports completion this way"


task 4:
"This source projection approach failed because..."


task 5:
"These three Orc Bot contracts must remain independent"

If this information lives only in conversation transcripts, terminal logs or old agent sessions, the next worker has to rediscover it.

With Mem0:

                    Orc Bot development
                           │
             ┌─────────────┴─────────────┐
             │                           │
        current task                past experience
             │                           │
             │                        Mem0
             │                           │
             └────────────┬──────────────┘
                          ▼
                  Context Package
                          │
                          ▼
                     worker agent

Then Orc Bot is not merely dogfooding its execution machinery.

It is dogfooding its:

execution;
workspace model;
candidate model;
agent interface;
memory/context model.

That is much more valuable.

But I would make Mem0 subordinate to a tiny Orc.Memory domain

I would not have Orc Bot code directly use Mem0 identities everywhere.

Something closer to:

Orc.Memory
    │
    ├── MemoryScope
    ├── MemoryQuery
    ├── MemoryRecord
    ├── MemoryCandidate
    ├── MemoryPromotion
    └── IMemoryProvider
             │
             ▼
       Orc.Memory.Mem0

The current implementation already learned this lesson: MemoryScopeFilter operates on Orc Bot's own scope identities rather than treating Mem0's user_id, agent_id, etc. as Orc Bot identity.

That should definitely survive the restart.

So:

Orc identity                  Mem0 identity


project-abc ───────┐
agent-reviewer ────┼── scope mapping ──> provider metadata
workitem-123 ──────┘


Orc owns meaning.
Mem0 owns storage/search.

This also means Mem0 can theoretically be replaced later without changing the orchestration domain.

Memory should participate before every agent invocation

I would make the first real worker path:

task submitted
      │
      ▼
resolve source generation
      │
      ▼
resolve agent
      │
      ▼
resolve authorized memory scopes
      │
      ▼
query Mem0
      │
      ▼
assemble bounded context
      │
      ▼
launch agent through ACP
      │
      ▼
typed completion
      │
      ├───────────────┐
      ▼               ▼
source delta      memory candidates
      │               │
      ▼               ▼
candidate       review/promotion

This makes memory symmetrical with source changes.

I particularly like that symmetry:

AGENT OUTPUT
   │
   ├── source claim
   │       │
   │       ▼
   │   SourceCandidate
   │       │
   │   review/validate
   │       │
   │       ▼
   │   integrated source
   │
   └── knowledge claim
           │
           ▼
      MemoryCandidate
           │
      review/policy
           │
           ▼
      durable memory

An agent saying:

“This is a useful fact for future agents”

should have about the same authority as saying:

“This code should become canonical.”

Meaning: it can propose it, but it cannot unilaterally make it authoritative.

The current memory work already follows this idea: memory candidates cannot self-promote, and project/shared promotion requires independent authorization.

That is worth carrying directly into v0.

I would initially support only a few memory scopes

Not a complicated hierarchy.

Something like:

Installation
Project
AgentProfile
WorkItem
Attempt/Session

The current implementation already has essentially these kinds and tests scope isolation, expiry and cross-scope refusal.

But I would avoid assuming they form one rigid tree.

For example an invocation could be authorized for:

MemoryContext
├── installation:orc-bot
├── project:orc-bot
├── agent-profile:csharp-worker
└── work-item:workspace-layering

Then retrieval becomes:

retrieve(scope A)
retrieve(scope B)
retrieve(scope C)
retrieve(scope D)


        ↓


rank + deduplicate + budget


        ↓


InvocationContext

Not:

find one "current memory namespace"

That becomes important once one agent participates across projects, categories and tool authorities.

And memory should be visible through CLI/MCP too

This connects directly to our previous point.

The bootstrap CLI should probably include:

orc memory search \
  --project orc-bot \
  --query "source workspace design"


orc memory inspect <memory-id>


orc memory candidates


orc memory approve <candidate-id>


orc memory reject <candidate-id>

The MCP equivalent can expose something like:

resources


orc://memory/scopes
orc://memory/<id>
orc://memory-candidates/<id>

and tools:

memory_search
memory_propose
memory_approve       # permission-gated
memory_reject        # permission-gated

Then another agent controlling Orc Bot can explicitly ask:

"What did previous Orc Bot development attempts learn
about source-layer materialization?"

rather than Orc Bot secretly stuffing arbitrary memories into every prompt.

That's important: implicit retrieval + explicit inspectability.

The invocation receipt should make memory reproducible

Every worker attempt should record something like:

AttemptReceipt
├── task id
├── source generation
├── provider / ACP identity
│
├── memory
│   ├── authorized scopes
│   ├── query digest
│   ├── retrieved memory ids
│   ├── retrieved memory digests
│   └── memory provider identity
│
├── context package digest
│
├── agent completion
├── source candidate
└── proposed memory candidates

We don't necessarily need to duplicate all memory text into SQLite.

Instead:

SQLite
   stores
     memory-id + digest + scope + provenance


Mem0
   stores/searches
     memory content

That preserves the clean authority boundary.

The current code already follows the related idea of retaining memory-scope/context digests with an invocation rather than treating context as invisible ephemeral prompt construction.

This changes my proposed v0 project list

Previously I suggested roughly:

Orc.Core
Orc.Application
Orc.Persistence.Sqlite
Orc.Source
Orc.Agent
Orc.Agent.Acp
Orc.Cli
Orc.Mcp

I would now make it:

Orc.Contracts


Orc.Core
Orc.Application


Orc.Persistence.Sqlite


Orc.Source
Orc.Source.Local          # first simple layered materializer


Orc.Memory
Orc.Memory.Mem0


Orc.Agent
Orc.Agent.Acp


Orc.Cli
Orc.Mcp

And potentially:

Orc.Context

although initially I would probably keep context assembly in Orc.Application until it becomes large enough to deserve its own component.

I would be a little more cautious about Microsoft Agent Framework

This is one place where I would modify the previous architecture rather than automatically carrying the current one over.

The current attempt puts Mem0 through Microsoft Agent Framework and very carefully prevents Agent Framework from becoming execution/lifecycle authority. That design is defensible.

But for the fresh bootstrap, I would first make this work:

Orc.Application
      │
      ├── IMemoryProvider → Mem0
      │
      └── IAgentProvider  → ACP

with Orc Bot itself assembling:

ContextPackage

If Microsoft Agent Framework substantially helps with context providers, middleware, skills, session handling and Mem0, introduce it behind that seam.

In other words:

                     Orc.Context contract
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
       Simple Orc assembler      Agent Framework adapter
            bootstrap                  later/early

rather than making:

Agent Framework
      ↓
the architectural definition of memory/context

That preserves our dogfood-first principle: adopt the framework when its benefit becomes concrete.

The bootstrap definition becomes better now

I'd define Orc Bot v0 as:

A headless, agent-addressable development coordinator that can remember previous development experience.

More concretely:

external agent
      │
   MCP / CLI
      │
      ▼
    Orc Bot
      │
      ├── recalls relevant Mem0 knowledge
      │
      ├── creates bounded context
      │
      ├── allocates private source layer
      │
      ├── launches worker through ACP
      │
      ├── observes typed completion
      │
      ├── freezes source candidate
      │
      └── freezes memory candidates
                │
                ▼
          human / policy
          accept/reject

And the very first Orc-Bot-develops-Orc-Bot task should already exercise memory.

For example:

Run 1
"Implement diagnostic X"


→ discovers useful repository fact
→ proposes memory
→ human promotes it to project memory

then:

Run 2
"Implement diagnostic Y"


→ retrieves that fact from Mem0
→ receipt proves it was included
→ agent uses it

If we can demonstrate that loop, then we have dogfooded not just orchestration, but cross-run learning from the beginning.

I think that's a considerably stronger foundation. It makes CLI + MCP + ACP + Mem0 + source candidates the true bootstrap set, while Godot, Zellij, Akka.NET, ECS, DAG/GOAP/HTN, tool slots and richer UI can grow around an Orc Bot that is already genuinely useful to the agents developing it.

Branched from 分支 · 分支 · Orc-bot Development Strategy

I think Zellij should be in initial attempt as well

Yes. I would now classify Zellij as part of the bootstrap set, alongside CLI/MCP/ACP and Mem0.

But I would be precise about why: Zellij is not needed because Orc Bot cannot launch a process without it. It is needed because an agent orchestrator without a durable, attachable human terminal is already missing one of its primary operating surfaces.

The previous experiments provide strong evidence for keeping that distinction. Zellij was successfully exercised on Windows for persistent sessions, panes, targeted input, viewport observation, reconnect, exit observation, and cleanup. The newer ADR correctly separates Zellij terminal/session functions from a typed IAgentMachineChannel; terminal text, pane state, and process exit cannot establish semantic completion or permission.

I would now describe the v0 architecture as five planes
                         OTHER AGENT / HUMAN
                                │
                    ┌───────────┴───────────┐
                    │                       │
                   MCP                     CLI
                    │                       │
                    └───────────┬───────────┘
                                │
                     ┌─────────────────────┐
                     │  CONTROL PLANE      │
                     │                     │
                     │ task / attempt      │
                     │ candidate           │
                     │ accept/reject       │
                     │ inspect/cancel      │
                     └─────────┬───────────┘
                               │
                 ┌─────────────┼──────────────┐
                 │             │              │
                 ▼             ▼              ▼
           CONTEXT PLANE   EXECUTION       PRESENTATION
                              PLANE            PLANE
              Mem0          ACP/JSONL         Zellij
                 │             │              │
                 └──────┐      │      ┌───────┘
                        ▼      ▼      ▼
                        worker agent
                             │
                             ▼
                     source candidate
                             │
                             ▼
                      review/disposition

With SQLite underneath as operational durability:

                    SQLite
                      │
     ┌────────────────┼────────────────┐
     │                │                │
 attempts         correlations      candidates
 lifecycle        sessions          decisions
 receipts         evidence          fences

This is already a useful Orc Bot.

Zellij actually improves the dogfood-first objective

Consider developing Orc Bot through Orc Bot:

orc task submit \
  --goal "Implement MCP task inspection"

Or an external coding agent does:

MCP:
orc_task_submit(...)

Orc Bot launches a worker.

Now immediately:

orc task inspect task-123
orc terminal attach task-123

and a human can enter the actual worker terminal.

That is enormously useful during development.

The bootstrap experience becomes:

external lead agent
       │
       │ MCP
       ▼
    Orc Bot
       │
       ├──────── ACP ──────── worker agent semantics
       │
       ├──────── Mem0 ─────── prior development knowledge
       │
       └──────── Zellij ───── human-visible live terminal
                                   │
                                   ▼
                             human can attach

So dogfooding doesn't mean watching logs after an autonomous task finishes.

We can actually live inside the orchestrator while developing the orchestrator.

And Zellij should be exposed through Orc CLI too

I wouldn't require users to memorize Zellij session names.

Instead:

orc task terminal task-123

or:

orc attempt attach attempt-456

would resolve:

Orc attempt identity
        │
        ▼
TerminalBinding
├── zellij session
├── pane id
├── provider
├── attempt id
└── workspace/source-layer id

and then execute the appropriate Zellij attachment.

Similarly:

orc terminal list
orc terminal inspect attempt-456
orc terminal attach attempt-456
orc terminal input attempt-456 "..."

But Orc Bot remains the identity authority.

Don't make:

zellij session name = Orc task identity

Instead:

TaskId
  │
AttemptId
  │
TerminalBinding
  │
  └── provider = zellij
      externalSessionId = ...
      externalPaneId = ...

That is similar to the better parts of the current native-session design: provider/terminal handles are observations correlated to Orc Bot's operation and attempt identities rather than product identities themselves.

There is an especially important architectural lesson from the old attempt

The 2026-08-11 archaeology concluded that terminal visibility should remain observational and warned against treating the terminal multiplexer as the trusted supervisor. It recommends that process containment and the semantic stream remain independently proven.

I think we should preserve that lesson while still making Zellij mandatory in v0.

There are therefore three different concerns:

                 Orc Attempt
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼


 Process ownership   Semantics    Presentation
 / containment


 Job Object /       ACP/JSONL       Zellij
 process group


        │            │            │
        └────────────┼────────────┘
                     │
              correlation only

In other words:

Zellij is mandatory bootstrap infrastructure, but it is never sufficient evidence that an agent operation exists, succeeded, failed, or terminated safely.

That is subtle but important.

The current ADR already captures much of this by defining one attempt as two correlated channels—Zellij plus the machine channel—and requiring typed semantic events separately.

I would keep that.

For the initial implementation, I'd actually make Zellij more prominent than Godot

Initially:

                 ┌───────────────┐
                 │   Orc Core    │
                 └───────┬───────┘
                         │
       ┌─────────────────┼──────────────────┐
       │                 │                  │
       ▼                 ▼                  ▼
      CLI               MCP               Zellij
   operations       agent access       human sessions
       │                 │                  │
       └─────────────────┼──────────────────┘
                         │
                         ▼
                      agents

Later:

                       Orc Core
                          │
        ┌─────────┬───────┼───────┬─────────┐
        ▼         ▼       ▼       ▼         ▼
       CLI       MCP    Godot   automation  ...
                          │
                          ▼
                    terminal surface
                          │
                          ▼
                       Zellij

So the Godot terminal UI eventually becomes another view over Zellij-bound terminal sessions.

It does not replace Zellij.

That gives us several useful operator paths:

direct shell
   ↓
zellij attach


Orc CLI
   ↓
orc attempt attach


Godot
   ↓
Terminal panel


remote/other agent
   ↓
MCP terminal inspection

All can point at the same running attempt.

This also clarifies MCP versus Zellij

An external agent should normally use:

MCP
 ↓
structured Orc API

not:

MCP
 ↓
type commands into Zellij pane

For example:

orc_task_get
orc_candidate_get
orc_memory_search
orc_attempt_cancel

are structured MCP operations.

Zellij only becomes relevant when the agent/human needs the interactive terminal surface.

That boundary prevents a very nasty future architecture:

everything
   ↓
terminal commands
   ↓
screen scraping

We absolutely don't want that.

Instead:

MCP/CLI              ACP
   │                  │
   │ structured       │ structured
   ▼                  ▼
Orc control       agent semantics


             Zellij
                │
                ▼
         terminal presentation
Zellij + ACP together are particularly strong

This is why I wouldn't choose between them.

Consider an agent performing a long-running change:

                    Worker Agent
                   /            \
                  /              \
             ACP events        PTY UI
                │                │
                ▼                ▼
            Orc Core          Zellij
                │                │
                ▼                ▼
       structured timeline    terminal

ACP tells Orc Bot:

session started
tool requested
permission requested
usage
progress
artifact
end turn
failure

while Zellij shows:

prompts
TUI
shell output
compiler progress
interactive questions
provider-native interface

They are complementary.

The old implementation's decision register reached essentially this conclusion: Zellij should provide terminal presentation/session infrastructure while a separate typed channel provides semantic truth.

I think that decision is worth keeping even though we're resetting almost everything else.

Mem0 makes the combination more interesting

Now a worker can have four very different kinds of state:

Attempt
│
├── operational state
│      SQLite
│
├── historical knowledge
│      Mem0
│
├── semantic interaction
│      ACP
│
└── interactive presentation
       Zellij

These should never collapse into one another.

For example:

Zellij says:
"Build succeeded!"

does not become:

attempt = completed

And it certainly doesn't automatically become:

Mem0:
"Build succeeds with configuration X"

Instead:

Zellij
  │ presentation only
  X
  │
ACP typed completion
  │
  ▼
attempt settles

and separately:

agent proposes learned fact
        │
        ▼
MemoryCandidate
        │
   policy/review
        ▼
      Mem0

This is a very clean architecture.

I'd therefore revise the bootstrap projects again

Something around:

Orc.Contracts
Orc.Core
Orc.Application


Orc.Persistence.Sqlite


Orc.Source
Orc.Source.Local


Orc.Memory
Orc.Memory.Mem0


Orc.Agent
Orc.Agent.Acp


Orc.Terminal
Orc.Terminal.Zellij


Orc.Cli
Orc.Mcp

Possibly:

Orc.Process.Windows
Orc.Process.Unix

quite early, because we already discovered that process containment is not a trivial implementation detail. The prior live experiment specifically found child processes surviving terminal-pane closure; later work introduced Windows Job Object containment as a result.

What I would not initially add:

Orc.Godot
Orc.Graph
Orc.Timeline
Orc.Ecs
Orc.Akka
Orc.Planner
Orc.Htn
Orc.Goap
Orc.PluginSystem

unless actual dogfooding starts demanding them.

The first dogfood milestone is now much more compelling

Imagine the fresh repository has only the bootstrap above.

We launch:

orc task submit \
  --repo . \
  --agent codex \
  --goal "Add the MCP resource for candidate inspection"

Orc Bot does:

1. create attempt
2. retrieve scoped Mem0 context
3. establish private source layer
4. establish Zellij session/pane
5. establish ACP machine channel
6. launch real agent
7. persist correlations
8. expose live terminal
9. consume typed semantic events
10. capture source delta
11. freeze candidate
12. propose new memories

While it runs:

orc attempt attach <id>

opens Zellij.

Another agent can simultaneously do:

MCP → orc_attempt_get
MCP → orc_memory_search
MCP → orc_candidate_get

After completion:

orc candidate diff <id>
orc candidate accept <id>

And the next Orc Bot development task can retrieve the promoted lessons through Mem0.

That, to me, is the right self-hosting threshold.

So I would now describe the fresh-attempt minimum as:

CLI + MCP for controlling Orc Bot, ACP for structured worker-agent interaction, Zellij for persistent interactive terminal sessions, Mem0 for cross-attempt knowledge, SQLite for operational truth, and the source-layer/candidate loop for safe development.

Everything else should have to justify itself against this already-usable dogfood system.

That set is larger than the tiny bootstrap I initially suggested, but unlike the current large first slice, every component in this set directly improves our ability to use Orc Bot to develop Orc Bot. That is the distinction I think we should use when deciding what belongs in the initial attempt.