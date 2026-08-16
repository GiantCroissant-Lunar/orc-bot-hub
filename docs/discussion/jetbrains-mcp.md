Today 9:02 AM
There are many agent development editor(ADE) out there, codex, claude, air(jetbrains), zcode, scape, orca other agent orchestration tools, etc. Just wondering if they provide mcp/cli/acp to work with, so orc-bot can utilize them just like agent cli

Yes. In fact, after checking the current interfaces, I think Orc Bot should broaden the idea of “agent CLI provider” into “machine-controllable agent endpoint.” A CLI is only one possible transport.

Your current Orc Bot is already surprisingly close to this model: the provider registry distinguishes CodexJsonl and AcpStdio, and currently discovers Codex JSONL, Codex-via-ACP, Claude-via-ACP, OpenCode ACP, and Kilo ACP. The supervisor still owns the attempt while the provider-specific channel supplies the semantic agent stream.

The important part is that ACP, MCP, and CLI are not interchangeable concepts.

Product	Machine-facing surface today	How Orc Bot should treat it
Codex	codex app-server gives a bidirectional JSON-RPC/JSONL agent service; codex exec --json gives structured JSONL events; Codex can also run as an MCP server.	Excellent direct AgentEndpoint. I would eventually prefer app-server over scraping/one-shot CLI because it exposes sessionful semantics.
Claude Code	Agent SDK provides the Claude Code agent loop programmatically; CLI supports noninteractive/structured operation, including -p and JSON/streaming output. Claude Code also consumes MCP tools.	Excellent direct AgentEndpoint. Native SDK/structured CLI is preferable; ACP adapter can remain a compatibility route.
OpenCode	Native opencode acp is explicitly an ACP server over stdin/stdout nd-JSON. It also has opencode serve for headless HTTP API access and structured CLI/session commands.	Probably the cleanest reference provider for Orc Bot. Native ACP fits your existing channel almost directly.
JetBrains Air	Air is primarily an ACP client/host: its acp.json starts ACP-compatible agents.	Not really an AgentEndpoint itself. Orc Bot should normally talk to the agent Air launches, rather than automate Air.
JetBrains Junie	Junie CLI explicitly supports junie --acp true; local ACP uses JSON-RPC over stdio.	Excellent AgentEndpoint. This would be a very natural next Orc Bot provider.
JetBrains IDEs	IntelliJ-family IDEs now include an MCP server that lets external clients such as Claude Code and Codex access IDE capabilities.	Tool/IDE endpoint, not an agent. Very interesting for giving Orc Bot agents JetBrains indexing, navigation, refactoring, etc.
ZCode	Z.AI documents ZCode as an agentic coding tool and provides Anthropic/OpenAI-compatible coding endpoints, but its current official integration page does not document a ZCode ACP/server/structured automation interface.	Unverified as a direct ADE endpoint. Use GLM through Claude/OpenCode/etc. for now rather than coupling Orc Bot to the ZCode UI.
Scape	Scape runs an MCP server with 100+ tools including create_session, create_worktree, list_sessions, and inter-session messaging. But calls are ownership-gated using Scape-session PID lineage.	Potential ExternalOrchestrator endpoint, but not automatically a generic external MCP API. Orc Bot needs an experiment to verify whether a non-Scape parent process can be admitted.
Orca	Very substantial JSON CLI: worktree create/list, launch agents, terminal create/read/send/wait/stop, etc. worktree create --agent codex --prompt ... --json is explicitly supported.	Excellent ExternalOrchestrator endpoint via CLI, but it should not be disguised as one agent.
This suggests three different Orc Bot boundaries

I would not make every one of these implement the same thing.

                         Orc Bot
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
    AgentEndpoint     OrchestratorEndpoint    ToolEndpoint
          │                 │                  │
     IAgentMachine       external fleet       MCP / IDE
       Channel           management           capabilities
          │                 │                  │
  ┌───────┼────────┐    ┌───┴────┐       ┌────┴─────────┐
 Codex Claude OpenCode  Orca   Scape    JetBrains IDE  ...
 Junie Kilo ...

That distinction becomes very useful.

AgentEndpoint means “perform this one Orc Bot-owned attempt.” Orc Bot owns the work item, source allocation, cancellation, permissions, completion, candidate publication, and durable identity. Codex, Claude Code, OpenCode, Junie, Kilo, etc. fit here.

OrchestratorEndpoint means “delegate a bounded sub-plan to another system that itself controls agents/worktrees/sessions.” Orca and Scape belong here. Orc Bot should record that delegation as a child orchestration authority and reconcile its results rather than pretending each child terminal is directly Orc Bot-owned.

ToolEndpoint provides capabilities to an agent without becoming the agent. JetBrains' MCP server is an excellent example: an Orc Bot-controlled Codex/OpenCode/Junie agent could gain IDE indexing/refactoring/navigation while Orc Bot still owns the actual attempt.

This also explains why MCP should not become another spelling of IAgentMachineChannel. MCP normally says “here are callable tools/resources.” ACP says “I am an agent; create a session, give me prompts, stream my updates, handle permissions/diffs/etc.” Junie's documentation explicitly describes ACP as decoupling coding agents from editors. Codex's MCP mode is an interesting exception because it intentionally exposes Codex conversations as MCP tools, but Codex's own app-server is the richer native agent-control surface.

This fits the current Orc Bot design very well

The existing implementation already says that the real provider executes through the typed machine channel, while Microsoft Agent Framework may prepare/contextualize/observe but must not become another execution/lifecycle authority. And the registry already abstracts concrete executables behind protocol identities such as codex-jsonl-v1 and acp-stdio-v1.

I would therefore evolve it roughly like this:

AgentProvider
  providerId
  endpointKind
  transports[]
  capabilities
  executable/server identity
  admission evidence


endpointKind:
  agent
  orchestrator
  tool-host


transport:
  acp-stdio
  native-jsonl
  native-jsonrpc
  http-api
  mcp
  structured-cli
  terminal-only

Then capability discovery matters more than product name:

session.create
session.resume
session.prompt
session.cancel
session.stream
permission.request
tool.event
file.diff
plan.update
usage.observe
artifact.observe
workspace.bind
process.identity

So a planner could say:

Need:
  session.create
  session.stream
  workspace.write
  permission.request
  cancellation


Candidates:
  opencode/acp          ✓
  junie/acp             ✓
  codex/app-server      ✓
  claude/structured     ✓
  zcode                 ? insufficient evidence

rather than hard-coding:

if provider == "codex" ...
else if provider == "claude" ...
What I would add next

My ordering would be:

OpenCode ACP and Junie ACP as the canonical portable agent path. OpenCode is already registered; Junie should be easy to add because its ACP server is explicit and officially documented.
Codex App Server as a native high-fidelity provider. Keep CodexJsonlMachineChannel, but introduce a CodexAppServerMachineChannel for richer persistent-session integration.
Claude native structured provider. The Agent SDK is Python/TypeScript, so for a C# Orc Bot the easiest boundary is still a supervised subprocess/bridge using Claude's structured CLI; you do not need to move Claude lifecycle authority into an SDK.
JetBrains IDE MCP as an optional tool capability. This is particularly interesting because an Orc Bot-controlled agent could use IntelliJ/Rider/ReSharper-class semantic information without making JetBrains Air the orchestrator.
Orca as the first ExternalOrchestratorProvider. Its JSON CLI is already extensive enough to create workspaces, launch agents, read/send terminal traffic and observe state.
Scape as a second external-orchestrator experiment, specifically testing its PID-lineage MCP ownership restriction before designing around it.
Leave ZCode pending until there is an official machine-facing ZCode contract; meanwhile GLM models can already sit behind one of the supported agent runtimes using Z.AI's Anthropic/OpenAI-compatible endpoints.

So the larger idea is: yes, Orc Bot can eventually orchestrate ADEs as well as agent CLIs—but “ADE” should not become one giant provider category. Codex/Claude/OpenCode/Junie are agent runtimes. Air/JetBrains IDE are agent hosts/tool hosts. Orca/Scape are orchestrators. Modeling those three roles separately would let Orc Bot exploit all of them without surrendering the authority boundaries you've been building.

Branched from Agent CLI and MCP

Could you do intensive research on jetbrains ide with mcp, how can it help orc-bot dogfood development and also orchestrate development other projects in general

Yes. After looking at JetBrains’ current 2026.2 MCP implementation in detail and comparing it with the current Orc Bot architecture, I think JetBrains IDE MCP is substantially more useful to Orc Bot than merely “another MCP server.”

The strongest fit is:

JetBrains IDE should become an Orc Bot development-tool / semantic-tool endpoint, and in some workflows a persistent semantic validation slot. It should not become another agent execution authority.

That distinction fits the architecture you already have unusually well.

1. What JetBrains MCP actually gives Orc Bot

Rider has shipped an integrated MCP server since 2025.2. In the current Rider 2026.2 documentation, external clients include Codex, Claude Code, Junie, Air, VS Code and others. The server supports SSE, stdio and HTTP Stream configuration, project-scoped client configuration, individually enabled tools, and a router-only mode that hides tools from the normal tool list to save agent context.

But the important part is the actual tool surface:

Capability	Current JetBrains MCP	Why Orc Bot cares
Semantic symbol lookup	search_symbol, get_symbol_info	Better context than grep for C#/Java/Kotlin/etc.
Dependency reasoning	analyze_calls	Uses IDE call hierarchy for incoming/outgoing calls rather than textual coincidence.
Static analysis	get_file_problems, lint_files	IDE inspections become machine-readable validation evidence.
Build	build_project	Build/compile with structured warnings/errors.
Project model	get_project_modules, get_project_dependencies	Agent can reason about real solution/module structure.
Refactoring	rename_refactoring	Semantic project-wide rename, not text replacement.
Source mutation	apply_patch, create_new_file, reformat_file	Potential IDE-aware authoring path.
Run configurations	discover/run configurations or runnable code locations	IDE-defined tests/apps/tools become callable capabilities.
Terminal	execute_terminal_command	Useful, but should largely be avoided by Orc Bot because you already have a better supervised execution path.
VCS	get_repositories, git_status	Good observational evidence, although it must not replace Orc Bot's source authority.
Database model	schema introspection, queries, data preview, connection inspection	Potentially useful for application/schema work. JetBrains explicitly recommends read-only DB credentials when an agent must be restricted.
Debugger	IntelliJ IDEA has an MCP debugger toolset controlling breakpoints, stepping, stacks, threads and values	Very interesting for JVM projects. Some event features are explicitly JVM-only.
Custom domain tools	IntelliJ Platform MCP server can be extended with McpToolset, @McpTool, @McpDescription	Orc Bot could eventually add narrowly tailored IDE operations instead of building a second code-analysis engine.

That last row is especially important.

JetBrains' July 2026 documentation describes the IntelliJ Platform MCP server as an extensible host: a plugin can depend on com.intellij.mcpServer, register an McpToolset, and expose annotated Kotlin methods as MCP tools. The framework handles transport, argument-schema derivation, project resolution and tool registration. The same documentation explicitly discusses project membership checks, structured error envelopes, cancellation, read/write locks and testing.

So this is not only:

Orc Bot -> JetBrains' predefined tools

It can eventually become:

Orc Bot -> JetBrains MCP
                  |
                  +-- standard JetBrains tools
                  |
                  +-- OrcBot-specific IDE toolset

without Orc Bot needing to embed Rider/ReSharper/IntelliJ internals into its C# runtime.

2. It fits Orc Bot best as a new plane, not a new agent provider

Your current architecture has a very important separation already.

AgentOperationSupervisor receives an ITerminalSessionProvider, an IAgentMachineChannel, a permission policy and persistent operation state. The machine channel—not terminal rendering—is what gives Orc Bot semantic agent completion.

And the current decision register says the same thing more broadly: permissions are typed/default-denied; agent loadouts freeze their tools and permissions; validation slots have stable identities and transactional fences; Microsoft Agent Framework surrounds the real CLI but does not take over lifecycle authority; and Orc Bot owns sessions it launches.

Therefore I would use three distinct planes:

                         ORC BOT
                           │
             lifecycle / policy / fences
                           │
          ┌────────────────┴─────────────────┐
          │                                  │
     AGENT PLANE                         TOOL PLANE
          │                                  │
 IAgentMachineChannel                DevelopmentToolEndpoint
          │                                  │
  ACP / Codex JSONL                         MCP
          │                                  │
 Codex / Claude /                      JetBrains Rider
 OpenCode / Junie                    IntelliJ / PyCharm...
          │                                  │
 semantic agent events            PSI / indexes / inspections
 completion / approval            refactoring / run configs
 usage / cancellation             debugger / project model

MCP calls must not become agent completion events.

For example:

Rider: lint_files -> 0 problems

does not mean:

Agent attempt = Completed

Likewise:

Rider: build_project -> success

doesn't mean:

Candidate = accepted

It is evidence belonging to one development operation or validation phase.

That preserves exactly the authority separation Orc Bot already applies to Agent Framework, terminal state, memory and usage observations.

3. Rider is particularly attractive for Orc Bot dogfooding

Orc Bot itself is a C#/.NET + Godot codebase, so Rider is almost an ideal first experiment.

Your checked-in godot-csharp-change workflow currently deliberately separates authoring from validation: an agent works in its allocated repository, produces a real source delta, and is explicitly told not to restore, export or launch the application because the final workflow validation owns those operations. The parallel workflow similarly creates isolated implementation and verification candidates and composes them before final validation.

That suggests two quite different ways of using Rider MCP.

During authoring: Rider as semantic context

Suppose Codex receives:

Fix cancellation settlement when ACP permission negotiation fails.

Today it may use filesystem search, ripgrep, build, source reading and its own reasoning.

With Rider MCP it could first do:

search_symbol
  AgentOperationSupervisor


analyze_calls
  incoming AgentOperationSupervisor.RunAsync


get_symbol_info
  AgentOperationOutcomeConvergence...


search_symbol
  AgentPermissionDecision


get_file_problems
  affected file

This is a major qualitative improvement because analyze_calls is using the IDE's call hierarchy rather than textual matches, and get_symbol_info uses IDE semantic information similar to Quick Documentation.

For architecture-heavy Orc Bot changes this could be extremely valuable. An agent could ask:

Who actually calls this method?
What implementation satisfies this interface?
Is this type coming from our project or a package?
Which project/module owns it?
What does Rider think is broken in this candidate?

rather than spending tokens reconstructing all of that from text.

4. But the more interesting use is Rider as a persistent semantic ValidationSlot

This is where I think the idea gets significantly more powerful.

Your current D-22 already defines a validation slot as a stable authority associated with a physical slot root; claims are transactional and fence-checked, concurrent claims return busy, quarantined slots stay non-claimable, and run identity cannot bypass that exclusivity.

A Rider project is exactly the sort of thing that benefits from this model:

Rider Semantic Slot
────────────────────────────────────────


stable project root
stable Rider solution/project
warm IDE index
warm code model
warm package/project metadata
run configurations
inspection configuration
optional debugger state


             ↑
             │ candidate materialization
             │
candidate A ─┤
candidate B ─┤  sequentially / fenced
candidate C ─┘

Instead of:

Agent A worktree -> Rider A
Agent B worktree -> Rider B
Agent C worktree -> Rider C
Agent D worktree -> Rider D

you can eventually do:

Agent A allocation ─┐
Agent B allocation ─┼─> immutable candidates
Agent C allocation ─┤
Agent D allocation ─┘
                           │
                           ▼
                  Rider semantic slot
                  warm index / one IDE

That is the same fundamental resource-separation insight behind the Godot/Unity design, but applied to an ordinary software IDE.

And that's important for the generalization of Orc Bot.

JetBrains actually gives you a non-game example demonstrating that:

source-authoring concurrency and expensive development-tool state are independent resources.

This could become one of the best proofs that the Orc Bot workspace/slot architecture is not merely a workaround for Unity Library or Godot .godot.

5. A concrete Orc Bot dogfood cycle

I would make a future Rider-backed validation phase look conceptually like this:

Agent attempt
    │
    │ ACP / Codex JSONL
    ▼
source allocation
    │
    │ fenced delta capture
    ▼
immutable candidate
    │
    │ candidate digest = ABC...
    ▼
claim RiderSemanticSlot
    │
    ├── verify fence
    ├── materialize candidate ABC
    ├── ensure Rider project points at expected root
    ├── wait for semantic readiness
    │
    ├── lint_files(changed files)
    ├── get_file_problems(changed files)
    ├── build_project
    ├── analyze_calls(selected boundary changes)
    └── maybe execute test run configuration
             │
             ▼
     IDE semantic receipt
             │
             ▼
    release Rider slot
             │
             ▼
Godot exported-window validation
             │
             ▼
human candidate disposition

The existing Orc Bot workflow still requires the final real exported-window acceptance for UI/end-to-end claims; a successful Rider build or inspection is supporting evidence, not a replacement for that acceptance boundary.

This separation would be excellent dogfooding.

6. What should go into the Rider receipt

I would not persist arbitrary MCP transcripts as the domain model.

Normalize them into Orc Bot evidence such as:

IdeSemanticValidationReceipt
  operationId
  validationAttemptId


  candidateDigest
  sourceGenerationDigest


  slotId
  slotFence


  endpoint:
    family = jetbrains
    product = rider
    version = ...
    projectPath = ...
    capabilityDigest = ...


  observations:
    filesInspected = [...]
    errorCount
    warningCount
    buildOutcome
    runConfigurationOutcomes
    callAnalysisReferences[...]


  startedAt
  completedAt


  rawEvidenceReference
  rawEvidenceSha256

The raw MCP payload can remain evidence; the receipt carries only stable Orc Bot semantics.

That continues your existing pattern of keeping provider/framework details behind adapters rather than allowing concrete SDK types to escape into runtime contracts.

7. Do not expose all of Rider MCP directly to every agent

This is probably the most important implementation warning.

JetBrains lets users disable individual tools and place tools behind router-only mode, but those are principally IDE-server configuration controls. It also has Brave Mode, which lets external clients execute terminal commands or run configurations without confirmation.

For Orc Bot I would not enable Brave Mode as the fundamental security model.

There is another subtle issue: read_file supports project files, dependencies/source roots, archive/JRT content and even absolute or .. paths accepted by the IDE. projectPath helps route a call to the correct open project, but it should therefore not be mistaken for Orc Bot's security fence.

The production architecture should eventually be:

                 agent
                   │
                  MCP
                   │
                   ▼
        Orc Bot MCP Tool Gateway
                   │
          typed AgentLoadout
         permissions + slot fence
                   │
              allow/deny
                   │
                   ▼
          JetBrains MCP Server

rather than:

agent ──────────> unrestricted Rider MCP

This solves several things at once.

Your current agent model freezes tools and permissions into the immutable AgentLoadout; changing nested tool grants changes its digest and tampering is rejected. The JetBrains tools should therefore be represented as Orc Bot typed tools, for example:

ide.symbol.search
ide.symbol.describe
ide.calls.analyze
ide.inspection.read
ide.project.describe


ide.refactor.rename
ide.source.patch


ide.build
ide.run.configuration
ide.terminal.execute

Then a profile could receive only:

ide.symbol.search
ide.symbol.describe
ide.calls.analyze
ide.inspection.read

while another agent may additionally receive:

ide.refactor.rename

and none automatically receives:

ide.terminal.execute

This is much more consistent with D-23/D-24/D-28 than relying on whatever MCP tools happen to be visible.

8. It can also work in the opposite direction

There is a second integration path worth noticing.

JetBrains AI Assistant itself is an MCP client. It can connect to local MCP servers over stdio, to Streamable HTTP servers, and to legacy SSE servers. Servers can be global or project-specific.

That means Orc Bot could eventually expose an MCP server:

JetBrains AI Assistant / Junie / external IDE agent
                         │
                        MCP
                         ▼
                  Orc Bot MCP Server
                         │
                    normal commands
                         │
                         ▼
              Akka / SQLite authority

Possible tools might be:

orcbot_list_workflows
orcbot_get_workflow
orcbot_get_candidate
orcbot_get_validation_receipt
orcbot_get_run
orcbot_get_agent_session

and, with stronger permissions:

orcbot_start_workflow
orcbot_cancel_attempt
orcbot_request_validation

The MCP server would merely be an ingress adapter.

It would never mutate SQLite directly or advance an actor from inside the MCP handler:

MCP request
    ↓
typed Orc Bot command
    ↓
normal authorization/fence/version checks
    ↓
Akka/SQLite

This would make JetBrains a genuinely first-class Orc Bot frontend without making JetBrains an authority.

9. How ACP fits

JetBrains also supports ACP agents inside its AI Chat and can expose the IDE MCP server to such agents, including restricting the IDE MCP tools passed to an ACP agent.

That is useful experimentally, but I would distinguish two configurations.

JetBrains-hosted mode:

Rider
  └── ACP agent
       └── Rider MCP

This is excellent for a human developer using Rider, but JetBrains is now launching/hosting the agent session.

Orc Bot-owned mode:

Orc Bot
  ├── ACP / native machine channel -> agent
  └── MCP tool gateway -> Rider

The second should remain the canonical dogfood path because your current architecture explicitly says Orc Bot owns the sessions it launches.

So ACP and JetBrains MCP are complementary:

ACP = who/what the coding agent is
MCP = what IDE capabilities that agent may use

That is much cleaner than treating both as interchangeable protocols.

10. Generalizing beyond Orc Bot

This becomes even more interesting when Orc Bot orchestrates unrelated projects.

Instead of creating:

RiderProvider
IntelliJProvider
PyCharmProvider
WebStormProvider
GoLandProvider
...

at the domain level, define capabilities:

code.symbol.search
code.symbol.describe
code.calls.analyze


code.inspect.file
code.inspect.batch


project.modules.read
project.dependencies.read


project.build
project.run.configuration


source.refactor.rename
source.format
source.patch


debug.session.control
debug.breakpoints
debug.stack.read
debug.variables.read


database.schema.read
database.query.read

Then probe the actual IDE MCP server and map its tools into those capabilities.

The installed Rider might satisfy:

code.symbol.search          ✓
code.calls.analyze          ✓
code.inspect.batch          ✓
source.refactor.rename      ✓
project.build               ✓
project.run.configuration   ✓
debug.session.control       ?

while IntelliJ IDEA currently provides a documented debugger MCP toolset with breakpoint, stepping, stack/thread and value inspection capabilities.

That lets workflow requirements say:

requires:
  code.inspect.batch
  project.build

rather than:

requires:
  JetBrains Rider

That is precisely the kind of generalization Orc Bot needs.

11. It also works very well with the project-profile concept

Consider different projects:

C# / ASP.NET
    Rider semantic slot
    + dotnet CLI validation


Java / Kotlin
    IntelliJ semantic slot
    + Gradle/Maven CLI
    + optional debugger MCP


Python
    PyCharm semantic slot
    + Python environment capabilities


React / TypeScript
    WebStorm semantic slot
    + Node/Vite execution profile


Unreal C++
    Rider semantic slot
    + Unreal tool-authority slot


Unity
    Rider semantic slot
    + Unity editor slot


Godot C#
    Rider semantic slot
    + Godot validation slot

Notice the important property:

the IDE and engine do not have to be the same slot.

For Unity, for example:

                candidate
                /       \
               /         \
              ▼           ▼
       RiderSemantic    UnityEditor
            Slot           Slot
              │             │
        C# semantics    import/runtime
        refactoring     scene/prefab
        inspections     PlayMode tests
              │             │
              └──────┬──────┘
                     ▼
               validation set

For Orc Bot itself:

                candidate
                /       \
               ▼         ▼
        RiderSemantic   GodotGUI
             Slot         Slot
               │           │
          C# semantics   exported UX
          inspections    user journey
          build/tests    screenshots
               └─────┬─────┘
                     ▼
               review evidence

That is a very compelling extension of the Orc Bot resource model.

12. JetBrains MCP may be the right answer to a problem we've discussed before

Previously, the difficult question with engine projects was:

How do we avoid making each agent own a complete expensive development environment?

JetBrains gives another example of the same issue:

source tree
    ≠
IDE index
    ≠
IDE process
    ≠
run/debug process

So the generalized model increasingly looks like:

WorkItem
   │
   ▼
SourceWorkspaceAllocation
   │
   ▼
immutable candidate
   │
   ├──> semantic tool slot
   │       Rider / IntelliJ
   │
   ├──> engine tool slot
   │       Godot / Unity / Unreal
   │
   ├──> runtime slot
   │       Vite / ASP.NET / game
   │
   └──> validation operations
           tests / lint / packaging

This is considerably stronger than:

one worktree per agent

and also stronger than:

one generic virtual filesystem per agent

because it models the actual expensive authorities independently.

13. Custom JetBrains MCP tools could eventually make this extremely powerful

I would start with the built-in tools. But the plugin extension mechanism opens an interesting later stage.

JetBrains' own current guidance for custom MCP toolsets recommends narrow domain-specific toolsets, machine-readable success/error envelopes, proper cancellation, project-membership checks, read/write command boundaries and integration tests. It explicitly notes that a pure IntelliJ Platform toolset does not need MPS-specific dependencies.

So Orc Bot could eventually ship an optional Orc Bot JetBrains Integration plugin exposing things the stock MCP server doesn't express well:

orcbot_ide_probe
    product/version/project/index state


orcbot_wait_semantic_ready
    wait until project/index is usable


orcbot_analyze_candidate
    candidate-aware changed-file inspection


orcbot_project_fingerprint
    project model / SDK / configuration digest


orcbot_collect_semantic_receipt
    normalized inspection/build/code-model result

The plugin should not contain:

orcbot_accept_candidate
orcbot_merge
orcbot_advance_workflow
orcbot_write_control_plane

Those remain Orc Bot commands.

This custom plugin would be a semantic adapter, not an orchestration authority.

14. One area where I would currently be cautious: debugger automation in Rider

IntelliJ IDEA's current 2026.2 MCP documentation has a full “Debugger tools” section. It explicitly documents control of debug sessions, breakpoint operations, stack/thread/value inspection and expression evaluation, with some event streams limited to JVM debuggers.

The Rider MCP reference I inspected does not currently document the equivalent debugger toolset even though JetBrains' 2026.2 Rider release tracking indicates ongoing MCP work around debugger/process attachment and richer refactoring.

So I would make Orc Bot dynamically probe capabilities and not presently hard-code “Rider MCP debugger” as a required C# capability.

This is another argument for:

capability discovery

instead of product/version assumptions.

15. A sensible implementation sequence

I would approach this in one sequence:

Dogfood Rider MCP manually against Orc Bot first. Enable only semantic/read capabilities—symbol search, symbol information, call hierarchy, file inspections, project/module/dependency inspection. Let Codex or an ACP agent use those against the Orc Bot solution and measure whether context quality and token usage actually improve. Rider already supports project-level MCP client configuration, which is convenient for this experiment.
Add JetBrainsMcpToolEndpoint as an Orc Bot adapter, not an agent provider. Probe the server, product/project identity and advertised tools. Keep MCP SDK/types outside contracts, consistent with D-06.
Introduce an IDE semantic receipt. Run lint_files, get_file_problems, semantic queries and eventually build_project after materializing an immutable Orc Bot candidate. Store normalized results plus content-addressed raw MCP evidence.
Bind Rider to a ValidationSlot. Treat project root + validation profile as a stable slot authority using your existing D-22 fencing/busy/quarantine semantics.
Only then allow source-writing IDE tools. Add rename_refactoring, formatting and patch application one at a time, behind explicit typed loadout permissions. Never make all exposed MCP tools an implicit grant.
Add the Orc Bot MCP gateway. Agent CLIs receive an Orc Bot-controlled MCP endpoint; Orc Bot selectively proxies approved JetBrains capabilities and records every invocation against operation/attempt/loadout/slot/fence.
Expose Orc Bot itself as MCP. This enables Rider/IntelliJ AI Assistant and other IDE agents to inspect Orc Bot workflows, candidates, sessions and receipts and submit normal typed commands through the same authority boundary.
Use a second unrelated repository as the proof of generalization. A plain .NET/ASP.NET project would be ideal first; then a JVM or TypeScript project. The core contracts should remain unchanged—the JetBrains/product mapping belongs in the adapter/profile.

The key metric in the first dogfood experiment should not merely be “MCP calls worked.” Measure fewer source reads/searches, fewer incorrect dependency assumptions, fewer post-agent review corrections, inspection defects caught before final validation, latency/indexing cost, and how much resident IDE state costs relative to per-worktree Rider instances.

Bottom line

I would elevate JetBrains MCP from “interesting external tool” to a fairly important Orc Bot architectural target.

It gives Orc Bot something that Codex/Claude/OpenCode themselves do not inherently provide:

a long-lived, language-aware semantic development authority with indexes, inspections, project models, refactoring, run configurations, and—in some IDEs—debugger state.

But the clean integration is not:

JetBrains IDE = new agent

and not:

JetBrains MCP = new IAgentMachineChannel

It is:

AgentProfile
    │
    ├── AgentEndpoint
    │       Codex / Claude / OpenCode / Junie
    │
    └── Tool capabilities
            │
            ▼
       Orc Bot MCP Tool Gateway
            │
            ▼
     JetBrains Semantic Slot
            │
       PSI / index / inspection
       build / refactor / debug

That preserves Orc Bot ownership while giving every Orc Bot-controlled agent access to IDE-grade semantics.

And more broadly, Rider provides a very good non-game proof of the same resource architecture you've been developing for Unity/Godot: many concurrent source-authoring activities can feed a bounded number of expensive, persistent, stateful development-tool slots. That makes the workspace/candidate/slot concept much more general than an engine-specific workaround.
