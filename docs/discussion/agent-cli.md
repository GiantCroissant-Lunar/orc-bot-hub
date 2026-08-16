could you evaluate "https://google.github.io/agents-cli/", what does it do and how does it help orc-bot?

Yes. After looking at the current Agents CLI documentation/repository and comparing it with the current Orc Bot implementation, I think it is quite useful for Orc Bot, but in a different role than Codex, Claude Code, OpenCode, Kilo, etc.

The key distinction is:

Google Agents CLI is primarily a lifecycle/tooling system for building agent applications, plus a portable skill pack that teaches coding agents how to use that lifecycle. It is not itself another coding-agent provider.

Google explicitly positions it as something used by coding agents such as Codex and Claude Code. Its current workflow covers understanding an agent project, scaffolding it, implementing it, evaluating it, deploying it, publishing it, and observing it.

That actually makes it more interesting for Orc Bot than simply adding one more CLI to AgentProviderRegistry.

What Agents CLI actually does

At the current 1.3.x line, Agents CLI provides roughly these layers. The latest release notes I found are 1.3.1 from August 4, 2026.

Layer	Agents CLI provides	Meaning for Orc Bot
Coding-agent knowledge	Seven installable Agent Skills	Very relevant to Orc Bot AgentLoadout
Project creation	scaffold / project templates	Development capability
Local execution	run, persistent local server, session support	Tool/runtime capability
Evaluation	dataset generation, execution traces, grading	Very valuable evidence source
Regression analysis	baseline/candidate comparison	Candidate quality gate
Failure analysis	clustering/analysis	Agent feedback/planning input
Optimization	GEPA-based optimization	Candidate-producing operation
Deployment	Agent Runtime, Cloud Run, GKE	External mutation/deployment authority
Publication	Gemini Enterprise publishing	External publication authority
Observability	tracing/analytics guidance and tooling	Projection/evidence source
Service interoperability	A2A support in scaffolded ADK agents	Future Orc Bot runtime adapter

Its default ADK scaffold is currently a Python ADK/ReAct-style agent. Scaffolded Python ADK agents expose A2A support, including an agent card and A2A routes, so the resulting agent application can participate in a distributed multi-agent system.

The evaluation side is particularly substantial. eval generate runs evaluation cases and produces JSON traces containing responses and tool calls; eval grade scores them; eval compare compares candidate versus baseline; eval analyze groups failures; and eval optimize can create improved agent configurations/prompts.

So I would describe Agents CLI less as:

"another agent CLI"

and more as:

agent-application engineering toolchain
+
portable knowledge/skills for coding agents
+
evaluation/quality pipeline
+
Google deployment/publishing adapters
Where it fits into Orc Bot

Orc Bot currently has a clean separation that we should preserve. Its provider registry represents the coding agents that actually author work through Codex JSONL or ACP stdio; currently that includes Codex, Codex ACP, Claude Code ACP, OpenCode ACP, and Kilo ACP.

Meanwhile, an Orc Bot AgentLoadout freezes the provider plus skills, rules, tools, context, memory and permissions for one attempt, and deliberately materializes that loadout into an attempt-private control root rather than modifying global agent configuration. Orc Bot also deliberately keeps Microsoft Agent Framework outside execution/lifecycle authority: the real CLI executes, while MAF contextualizes and observes; Akka.NET and SQLite retain lifecycle and durable authority. This is consistent with the broader architecture in the current repository.

So I would place Agents CLI here:

                         ORC BOT
                            │
             ┌──────────────┴───────────────┐
             │                              │
       orchestration                  AgentLoadout
 Akka / SQLite / fences                   │
 candidate / evidence                     │
             │                    ┌────────┴────────┐
             │                    │                 │
             │               Codex/Claude/...   Google
             │                ACP / JSONL       Agent Skills
             │                    │                 │
             │                    └────────┬────────┘
             │                             │
             │                     coding-agent attempt
             │                             │
             │                      calls agents-cli
             │                             │
             │        ┌────────────────────┼──────────────────┐
             │        │                    │                  │
             │     scaffold              eval              deploy
             │        │                    │                  │
             │        ▼                    ▼                  ▼
             │    source delta      evidence artifacts   external target
             │        │                    │                  │
             └──── candidate ←─────────────┘            deployment receipt
                      │
                  review/accept

This placement is important. Agents CLI should not replace Akka.NET, Microsoft Agent Framework, ACP, Zellij, the candidate lifecycle, or SQLite.

It sits under Orc Bot as a tool used during a work item.

I would not add agents-cli to AgentProviderRegistry

This is the most important architectural conclusion.

Your current AgentProviderRegistry asks a very specific question:

“What interactive coding agent can Orc Bot launch, supervise, authorize and observe through a typed semantic channel?”

Today that answer is Codex JSONL or ACP.

Agents CLI answers another question:

“What engineering operations can a coding agent or workflow perform on an agent application?”

Those are different dimensions.

I would therefore eventually introduce something conceptually like:

AgentProvider
    codex
    claude
    opencode
    kilo


ToolchainProvider
    dotnet
    git
    godot
    unity
    cargo
    agents-cli
    comfyui
    ...


RuntimeProtocol
    ACP        ← coding-agent control
    A2A        ← service-agent interaction
    MCP        ← tool/resource exposure

The exact class names can wait. What matters is not conflating the axes.

That would also help Orc Bot with Unity, Godot, Cargo, JetBrains, ComfyUI and the other integrations you've been considering: they are capabilities/toolchains, not personalities that should be put into the coding-agent provider registry.

Agents CLI's Skills are an unusually good fit

Google distributes a set of skills such as workflow, ADK code, scaffolding, evaluation, deployment, publishing and observability. They are intentionally consumable by coding agents.

That is extremely close to what Orc Bot has already built around:

AgentProfile
    ↓
immutable AgentLoadout
    ├─ Skills
    ├─ Rules
    ├─ Tools
    ├─ Context
    ├─ Memory
    └─ Permissions

But there is one important incompatibility.

agents-cli setup normally detects installed coding agents and installs its skills globally; Google provides --workspace when workspace-local installation is desired.

Orc Bot explicitly says the opposite: the attempt loadout should be isolated outside the source worktree, global CLI configuration should not be modified, and provider-specific delivery must be recorded.

So I would not execute Google's default global setup from Orc Bot.

Instead, Orc Bot should treat Google Agents CLI as an external skill distribution.

Conceptually:

google/agents-cli
       │
       │ pinned release/commit
       ▼
ExternalSkillPack
       │
       ├── workflow
       ├── adk-code
       ├── eval
       ├── scaffold
       ├── deploy
       ├── publish
       └── observability
       │
       ▼
Orc Bot loadout resolver
       │
       ▼
attempt-private context

And Orc Bot should retain:

source = google/agents-cli
version = 1.3.1
source commit = ...
skill digest = SHA256(...)
delivery mechanism = ...

This is much more compatible with the provenance/digest model already present in AgentLoadoutResolver and Agent Framework receipts.

Don't translate Google skill prose into permissions

There is another subtle point.

Suppose Google's skill tells a coding agent:

run agents-cli deploy ...

That is guidance, not authorization.

Orc Bot's corresponding loadout would still need an explicit typed grant such as:

Skill:
  google-agents-cli-deploy


Tool:
  agents-cli


Permission:
  cloud.deploy.agent-runtime

The skill must not manufacture the last two.

That follows directly from Orc Bot's current design, where skills/rules/tools/context/memory/permissions remain distinct typed concepts.

This is actually a useful real-world test of whether the current ability architecture is sound.

The biggest contribution may be the evaluation model

This is where I think Agents CLI could materially improve Orc Bot's design.

At the moment, Orc Bot has a strong distinction between:

agent completed work
        ≠
candidate accepted
        ≠
validation passed
        ≠
integration approved

Agents CLI adds another very useful distinction:

code is technically valid
        ≠
agent behavior is good

Google's own workflow explicitly separates ordinary code correctness testing from behavioral agent evaluation.

So an Orc Bot agent-development workflow could become:

Author agent
     │
     ▼
candidate
     │
     ├── dotnet/python/static/unit tests
     │
     └── agents-cli eval generate
                  │
                  ▼
             trace artifact
                  │
                  ▼
             eval grade
                  │
          ┌───────┴────────┐
          │                │
       compare          analyze
          │                │
          └───────┬────────┘
                  ▼
          EvaluationReceipt
                  │
                  ▼
             human review

eval compare is almost tailor-made for Orc Bot's immutable-candidate model:

base candidate evaluation
           vs
new candidate evaluation

The result can become another piece of evidence attached to ComponentCandidate, rather than allowing an agent to say “my improvement is better.”

That is a much stronger loop.

eval optimize should create another candidate

I would be careful with Agents CLI's optimization capability.

It should not look like:

evaluate → optimize → automatically overwrite accepted candidate

Instead:

candidate A
    │
 evaluation
    │
 optimize
    │
    ▼
candidate B
    │
 review

In Orc Bot terms, optimization is another authoring operation.

This is also where your future GOAP/HTN/graph ideas become interesting. The optimizer or planner could decide that the next action is “modify instructions”, “add a tool”, “add examples”, or “generate a new evaluation set,” but each mutation still crosses the normal candidate boundary.

ACP, A2A, MCP and Agents CLI now form a cleaner picture

Agents CLI also helps clarify something we've repeatedly touched on.

Protocol/concept	Best Orc Bot interpretation
ACP	Orc Bot ↔ coding agent used to develop things
Agent Skills	Portable knowledge loaded into that coding agent
MCP	Tools/resources made available to an agent
A2A	Orc Bot/service ↔ running agent application
Agents CLI	Engineering lifecycle around an agent application

Agents CLI's run command can talk to remote agents using A2A or ADK streaming modes, while the ADK scaffold provides A2A endpoints.

That suggests an elegant future architecture:

                 DEVELOPMENT TIME


Orc Bot ──ACP──► Codex
                   │
                   │ agents-cli
                   ▼
                ADK agent
                   │
                   ▼
               candidate
                   │
                 deploy
                   │
                   ▼


                  RUNTIME


Orc Bot ──A2A──► deployed ADK agent
                       │
                       └──MCP──► external tools

I would not use agents-cli run --url --mode a2a as Orc Bot's permanent A2A transport. It is useful for smoke tests and external verification. Once Orc Bot needs first-class runtime-agent orchestration, a direct A2A adapter gives you typed identities, cancellation, events and correlation without parsing another CLI.

It also gives Orc Bot a useful second domain to dogfood

This may be the most practical reason to adopt it early.

You've spent considerable effort making Orc Bot's workspace/candidate model applicable beyond Godot/game development. The current design already separates agent attempts, private source allocations, immutable candidates, tool validation and human acceptance.

An ADK agent project is an excellent non-game test case.

It has:

source code
agent-specific behavioral tests
runtime servers
generated evaluation artifacts
external tools
cloud deployment
distributed-agent protocols
observability

If Orc Bot handles that cleanly without changing its fundamental SourceWorkspace → Candidate → Evidence → Review contracts, that's strong evidence the abstraction is genuinely general.

A first integration I would actually implement

I would make this much smaller than “support Google Agents CLI.”

The first experiment should be:

AgentProfile: adk-agent-builder


Provider:
  codex-acp


Skills:
  google-agents-cli-workflow
  google-agents-cli-adk-code
  google-agents-cli-eval


Tools:
  agents-cli


Permissions:
  workspace.read
  workspace.write


Explicitly absent:
  cloud.deploy
  cloud.publish

Then let Orc Bot allocate its normal private authoring workspace, have Codex modify a tiny ADK agent using the Google skills, and run a pinned Agents CLI evaluation.

The result should produce two separately governed outputs:

source changes
    ↓
immutable Orc Bot candidate


eval traces/results
    ↓
immutable Orc Bot evidence

The Agents CLI evaluation commands already provide machine-readable trace/result artifacts suitable for this.

The proof should verify that no global Codex/Claude configuration was touched, Google's skill documents were digest-pinned in the loadout, agents-cli executable/version was recorded, generated eval/run state did not leak into the source candidate, typed ACP events still determined agent completion, and no Google Cloud deployment occurred.

That one experiment exercises AgentProfile + external skills + external toolchains + ACP + candidate separation + evaluation evidence + dogfooding against a non-game project all at once.

What I would adopt and what I would not
Agents CLI idea	Orc Bot decision
Agent Skills	Adopt strongly, through external skill-pack adapter
Workflow skill	Use as knowledge, not orchestration authority
Scaffold	Add as development capability
run	Use for development/smoke; don't make it lifecycle authority
Eval generate/grade	Adopt strongly as evidence provider
Eval compare	Excellent candidate regression gate
Eval analyze	Feed UI/planner/operator attention
Eval optimize	Candidate-producing operation only
Deploy	Optional explicit deployment capability
Publish	Optional explicit publication capability
A2A	Add later as independent runtime protocol
Google cloud targets	Optional provider-specific adapters
Global setup	Do not use from Orc Bot
Agents CLI as AgentProvider	No
Agents CLI replacing MAF	No
Agents CLI replacing Akka workflow	Definitely no
Agents CLI evaluation as lifecycle truth	No; evidence only

The deployment side is intentionally powerful—Agents CLI supports Agent Runtime, Cloud Run and GKE—so it should sit behind a much stronger authority boundary than ordinary authoring. Google's own workflow skill also explicitly requires human approval before deployment, which happens to line up very well with Orc Bot's candidate/validation/human-decision model.

Overall assessment

I would rate the fit as:

8.5/10 as an external agent-development toolchain and skill source.
9/10 as a reference implementation for agent evaluation/quality loops.
3/10 as an Orc Bot “agent provider.”
0/10 as a replacement for Orc Bot orchestration.

The most important idea it adds to Orc Bot is perhaps not Google ADK at all. It gives us a concrete reason to generalize Orc Bot from:

AgentProviderRegistry

toward something closer to:

Agent Providers       → who performs authoring
Ability/Skill Packs   → what they know how to do
Toolchain Providers   → what external engineering systems they can operate
Runtime Protocols     → ACP / A2A / ...
Evidence Providers    → tests / agents-cli eval / Godot validation / ...
Deployment Providers  → Cloud Run / GKE / future Unity build distribution / ...

That decomposition looks very consistent with the direction the current Orc Bot code has already taken, rather than requiring another architecture reset.

If we continue this thread, the next useful step would be to compare Google Agents CLI's skill/plugin model with Orc Bot's current AgentProfile / AgentLoadout / Markdig skill model, because I think there is enough overlap to define a general external skill-pack/admission contract that could also cover Codex skills, Claude skills, JetBrains skills and other future agent capability packs.