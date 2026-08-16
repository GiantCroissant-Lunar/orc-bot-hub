Yes. I think that makes the architecture cleaner, with one important refinement:

Use MPS as the canonical semantic model for UI behavior, but keep Godot TSCN/theme as the canonical visual/layout representation. Then generate C# or GDScript presenter/behavior code from the same MPS model.

For Web, I agree with your earlier point: requiring hot code reload is unnecessary. A browser refresh gives you a fresh Godot/Wasm instance, so the Web backend can simply generate GDScript and rely on normal deployment + refresh. Desktop can generate C# and retain Orc Bot's current collectible-ALC development experience.

MPS is particularly suitable for this because its programs are stored as AST models, and its generator is explicitly model-to-model; the resulting model can then go through TextGen to produce ordinary source files. MPS also supports multi-stage generation pipelines, which is exactly what we want here.

I'd shape it roughly like this:

                 JetBrains MPS
          ┌────────────────────────┐
          │      Orc.UI DSL        │
          │                        │
          │ Surface               │
          │ State<T>              │
          │ Computed<T>           │
          │ Collection<T>         │
          │ Binding               │
          │ Intent<T>             │
          │ Validation            │
          │ AsyncOperation        │
          │ Visibility            │
          │ Selection             │
          │ Formatting            │
          └───────────┬────────────┘
                      │
                      │ lowering
                      ▼
          ┌────────────────────────┐
          │      Orc.UI.IR         │
          │ canonical semantics    │
          │ no C#/GDScript/Godot   │
          └───────┬────────┬───────┘
                  │        │
            Desktop│        │Web
                  ▼        ▼
         C# backend      GDScript backend
             │                │
             ▼                ▼
       *.generated.cs     *.generated.gd
             │                │
             ▼                ▼
      collectible ALC       Godot Web
       desktop bundle      refresh/restart

The critical part is the middle Orc.UI.IR. I would not generate C# and GDScript directly from the high-level MPS surface model.

MPS explicitly supports transformations through intermediate models before final text generation, and generation plans can control which generator pipeline runs. Recent MPS documentation also notes that multiple generators for a language need explicit selection through generation plans, so for your two-backend case I would make the target plan explicit rather than rely on implicit generator discovery.

So conceptually:

Plan: OrcUiDesktop


Orc.UI
   ↓
Orc.UI.IR
   ↓
Orc.CSharp.UI
   ↓ TextGen
*.cs

and:

Plan: OrcUiWeb


Orc.UI
   ↓
Orc.UI.IR
   ↓
Orc.GDScript.UI
   ↓ TextGen
*.gd

This gives you one place where semantics are defined.

What I would put in the UI IR

I'd deliberately make it much closer to a reactive/presentation language than a general programming language:

surface AgentSessions {
    input snapshot : AgentSessionsSnapshot


    state selectedSession : SessionId?


    derived sessions =
        snapshot.sessions
            .sortByDescending(lastActivity)


    derived selected =
        sessions.find(id == selectedSession)


    intent refresh
        -> runtime.agentSessions.refresh()


    intent select(sessionId)
        -> selectedSession = sessionId


    collection sessionRows {
        source = sessions
        key = id
        text = name
        secondaryText = agentName
        tone = status
    }


    property detailText =
        selected?.preview ?? "No session selected"
}

That is a good MPS language.

This is not:

if target == CSharp:
    ObservableCollection<...>
else:
    Array[Dictionary]...

Target details should not exist in the model.

The C# generator can translate state, derived, and intent into whatever shape your collectible presenter expects. The GDScript generator translates exactly the same concepts into a RefCounted/Resource-like presentation object or whatever small runtime interface you define.

That actually strengthens the architecture you already have. ADR-0023/RFC-0008 are already moving toward resident generic surface hosting + bundle-owned presenter logic + TSCN/theme-first UI, while explicitly keeping collectible logic from owning Godot nodes.

I would retain that rule:

                VISUAL AUTHORITY


Godot editor
    │
    ├── panel.tscn
    ├── row.tscn
    ├── theme.tres
    └── GraphEdit/etc.
             │
             ▼
      resident generic binder
             ▲
             │
             │ presentation contract
             │
        generated behavior
             ▲
             │
          MPS model

That is much better than using MPS to generate imperative code that creates VBoxContainer, Label, GraphEdit, etc.

You still get the Godot editor for what it is good at: layout, anchors, containers, themes, GraphEdit, AnimationPlayer, resources and visual inspection.

MPS owns what it is good at: structure, semantic constraints, type checking, transformations and code generation.

C# becomes a backend rather than part of the architecture

This is one of the biggest benefits.

Currently something like:

public sealed class UnitsViewPresenter : IViewPresenterService
{
    public ViewPresenterResult Present(ViewPresenterRequest request)
    {
        ...
    }
}

looks somewhat architectural because the presenter happens to be written in C#.

With MPS, it becomes merely:

Orc.UI semantic model
          ↓
CSharpPresenterGenerator
          ↓
UnitsViewPresenter.generated.cs

C# ALC is then just the desktop execution backend.

Likewise:

Orc.UI semantic model
          ↓
GDScriptPresenterGenerator
          ↓
units_view_presenter.generated.gd

is the Web backend.

That means concepts such as:

Surface
Presenter
Snapshot
Intent
Binding
Collection
Selection
Command
Validation

belong to Orc Bot.

Concepts such as:

INotifyPropertyChanged
AssemblyLoadContext
Callable
Signal
RefCounted
Variant

belong to backends.

That's a very healthy boundary.

And this gives you something even more valuable than cross-platform code generation

You can generate semantic conformance tests from the same model.

For example MPS knows:

input:
    sessions = [A running, B failed]
    selected = B


expected:
    rowCount = 2
    selectedDetail = B
    selectedTone = bad

Generate:

                   Orc.UI.IR
                  /    |     \
                 /     |      \
                v      v       v
          C# presenter GD presenter Test vectors
                |      |          |
                └──┬───┘          |
                   v              v
                 compare semantic output

So the requirement is no longer:

Hopefully C# and GDScript implementations behave the same.

It becomes mechanically testable:

evaluate(CSharpBackend, fixture)
==
evaluate(GDScriptBackend, fixture)
==
expected IR result

That is important because otherwise dual-generation inevitably develops subtle differences around nullability, collection mutation, async operations, numeric conversions, string formatting, enum representation, etc.

I would even avoid generating code when code isn't necessary

There is another layer I'd consider.

A surprising amount of UI behavior may be representable directly as declarative IR:

property
binding
expression
selection
collection mapping
visibility
formatting
intent routing

For those, MPS could emit something like:

surface.orcui

or:

{
  "surface": "...",
  "bindings": [...],
  "computed": [...],
  "intents": [...]
}

and your resident Rust/C#/GDScript binder could interpret it.

Then only genuinely procedural behavior gets compiled to C#/GDScript.

So the eventual stack might be:

                  MPS
                   │
                   ▼
              Orc.UI.IR
                   │
       ┌───────────┴────────────┐
       │                        │
       ▼                        ▼
declarative UI bytecode     procedural IR
       │                    /          \
       ▼                   ▼            ▼
generic binder         generated C# generated GDScript

That could dramatically reduce the amount of generated source.

For things such as:

text = "${selected.name} · ${selected.status}"
visible = selected != null
tone = selected.status

generating a C# class and a GDScript class is unnecessary.

But something like:

transform a complex graph projection
aggregate timeline events
perform custom incremental computation

may justify compiled backend code.

One concern specifically for Orc Bot: MPS and agent editing

There is one area I'd test very early before committing to MPS as the source of truth.

MPS is projectional: the program is an AST rather than ordinary textual source. MPS has its own Git integration, model-aware diff/merge, and supports file-per-root persistence, but JetBrains explicitly notes that its concrete syntax isn't pure text and generic persistence is therefore needed.

That is great for human MPS users.

It is potentially awkward for:

Claude Code
Codex
OpenCode
Kiro
Kilo
other CLI agents

because their native environment is text files.

This matters a lot for Orc Bot.

I therefore wouldn't make agents edit raw .mps persistence files.

I'd expose an Orc Bot/MPS tool boundary:

agent
  │
  │ MCP/ACP/tool call
  ▼
MPS Model Service
  │
  ├── query surface
  ├── add state
  ├── add intent
  ├── modify expression
  ├── inspect references
  ├── validate model
  ├── generate
  └── produce semantic diff

Then an agent says conceptually:

surface.modify
  surface = "agent-sessions"
  property = "selectedSession"
  change = ...

rather than editing serialized MPS XML.

MPS has an Open API for accessing models programmatically, and even allows custom persistence implementations, so exposing a structured model service is compatible with its architecture.

That also works extremely well with the Orc Bot candidate model:

Agent branch/workspace
       │
       ▼
MPS semantic operations
       │
       ▼
UI model candidate
       │
       ├── semantic diff
       ├── validation
       ├── generated C#
       ├── generated GDScript
       └── generated conformance tests
             │
             ▼
      candidate review/integration

So I think your idea goes beyond merely solving Web vs desktop.

It suggests a cleaner architecture:

Godot becomes the UI runtime/rendering platform. Rust becomes the portable resident host. MPS becomes the source language/semantic compiler. C# and GDScript become replaceable execution backends. TSCN/theme remain native visual assets.

And the particularly nice result is:

Desktop development
MPS -> C# -> collectible ALC
               ↑
           fast behavior reload




Web
MPS -> GDScript -> exported Godot Web
                       ↑
                 page refresh




Visual UI
TSCN / Theme / GraphEdit / Animation
             ↑
      identical on both

That division feels considerably stronger than choosing one of C# vs Rust vs GDScript as the language that defines Orc Bot's UI architecture. They stop being the architecture at all; they're deployment backends.

How does a2-ui, ag-ui fit in this context
How does figma, pencil file fit in this context

Yes. Once A2UI/AG-UI and Figma/Pencil are added, I would not try to force all of them into MPS. They represent different kinds of information.

The architecture becomes much clearer if Orc Bot has two UI pipelines:

                    ORC BOT UI


       TRUSTED / PRODUCT UI          AGENT-GENERATED UI
       ====================          ==================


 Figma / .pen / Godot editor              Agent
          │                                 │
          ▼                                 ▼
     Visual Design IR                    AG-UI
          │                         runtime/event channel
          │                                 │
          │                                 ▼
          │                        Orc activity contracts
          │                                 │
          ▼                                 ▼
      TSCN / TRES                         A2UI
          │                        declarative UI description
          │                                 │
          └──────────────┐        ┌─────────┘
                         ▼        ▼
                       GODOT
                 resident SurfaceHost

And alongside that:

                     MPS
                      │
                semantic UI model
                      │
               ┌──────┴──────┐
               ▼             ▼
           generated C#   generated GDScript
             Desktop            Web

So MPS, Figma/Pencil, A2UI, and AG-UI are complementary rather than competitors.

This is also very close to what Orc Bot's current ADRs already say: A2UI is specifically the allowlisted Activity renderer, AG-UI is a translation adapter, while ordinary trusted UI remains TSCN/theme-first.

1. AG-UI is not a UI description language

This is the first distinction I'd lock down.

AG-UI is essentially:

Agent runtime
    │
    ├── RUN_STARTED
    ├── TEXT_MESSAGE_CONTENT
    ├── TOOL_CALL_START
    ├── TOOL_CALL_ARGS
    ├── STATE_SNAPSHOT
    ├── STATE_DELTA
    ├── RUN_FINISHED
    │
    ▼
Frontend

Its own documentation explicitly says AG-UI is not a generative-UI specification. It is the bidirectional runtime connection between an agent and an application; it can carry/support generative-UI specifications such as A2UI.

Therefore AG-UI belongs next to ACP/A2A, not next to MPS:

              EXTERNAL PROTOCOLS


 ACP              AG-UI               A2A
  │                 │                  │
  │ machine          │ agent/UI         │ remote agents
  │ channel          │ event stream     │
  └──────────┬───────┴──────────┬───────┘
             ▼                  ▼
             Orc T1 contracts
             / internal events

This is exactly the direction already recorded in Orc Bot: AG-UI translates external run/message/tool/state streams into Orc Bot's internal contracts and does not become authoritative state.

So I would not generate AG-UI from MPS, and I would not model AG-UI events as MPS UI concepts.

It is transport/runtime integration.

2. A2UI is the runtime-generated UI lane

A2UI is much closer to what its name suggests:

Agent:
    "show these controls"


        ↓


A2UI


createSurface
updateComponents
updateDataModel
deleteSurface


        ↓


trusted client renderer

The current A2UI specification defines a streamed declarative UI model where the agent sends component definitions and data, and the client decides how approved component types are actually rendered.

And A2UI explicitly supports AG-UI as a transport/binding.

Therefore this combination makes sense:

Agent
  │
  │ AG-UI
  ▼
Orc AG-UI adapter
  │
  ├── text
  ├── lifecycle
  ├── tool events
  ├── state
  │
  └── A2UI payload
          │
          ▼
    validation/security
          │
          ▼
    Orc A2UI catalog
          │
          ▼
   A2UI → Godot adapter
          │
          ▼
     native Controls

That is a very different use case from:

Control Center
Candidate Review
Workspace Manager
Graph Editor
Timeline
Settings
Terminal

Those are stable, trusted product surfaces.

I would not make them A2UI.

Your existing ADR made exactly this distinction by rejecting a "universal remote UI DSL for every panel" while retaining A2UI as the Activity boundary.

That decision becomes even stronger if MPS exists.

3. MPS is the behavior/semantic UI language

MPS answers things like:

What state does this surface expose?


What does selection mean?


What command does this button invoke?


What are the allowable intents?


How is this list projected?


What is derived state?


What validation applies?


What happens when the user confirms?

For example:

Surface CandidateReview


input:
    CandidateSnapshot candidate


state:
    selectedTab


derived:
    canAccept =
        candidate.status == UnderReview
        && candidate.validationPassed


intent accept:
    precondition canAccept
    command candidate.accept(candidate.id)


intent reject(reason):
    require reason.nonEmpty
    command candidate.reject(candidate.id, reason)

None of this says:

padding = 12
font = Inter
button width = 96
background = ...

And it also doesn't say:

RUN_STARTED
TOOL_CALL_ARGS
STATE_DELTA

Those belong elsewhere.

So:

MPS
 =
semantic interaction model
4. Figma/Pencil are the visual design side

Figma and Pencil primarily answer another class of questions:

What does it look like?


How is it laid out?


Which reusable visual component is this?


What spacing/token/theme is being used?


How does it respond to available size?

A Figma file exposes a document/node tree, components, component sets and styles through its API, while Figma Variables cover reusable design values.

Figma now also provides MCP and Code Connect specifically to bridge design elements with implementation components. Its documentation is quite explicit that MCP supplies structured design context, while the agent—not Figma itself—produces the final implementation.

That is very close to the compiler relationship we'd want for Orc Bot.

For example:

Figma component


    OrcButton
        variant = destructive
        size = medium
        label = Delete


             │
             │ mapping
             ▼


Godot component


    OrcButton.tscn
        tone = Danger
        size = Medium

Figma Code Connect already uses essentially this architectural idea for web/native codebases: map design components and their properties onto actual implementation components.

For Orc Bot we'd create our own analogous mapping:

Figma Component
      ↕
Orc.Visual.ComponentId
      ↕
Godot TSCN component
5. Pencil .pen is particularly interesting for Orc Bot

Pencil/pen.dev is potentially an even better architectural fit than Figma for agent-driven development.

A .pen file is JSON containing an object tree. It has IDs, frames, text, reusable components, component references, slots, variables/themes, and even an extensible metadata property.

More importantly, .pen is intentionally repo-oriented:

design.pen
    ↓
Git
branch
diff
merge
agent modification

Pencil explicitly describes .pen as text-based "design as code" that can be committed, diffed, branched and merged alongside source.

That's highly relevant to Orc Bot's source-workspace/candidate architecture.

You could literally have:

Agent workspace
│
├── ui/
│   ├── candidate-review.pen
│   ├── control-center.pen
│   └── theme.pen
│
├── ui-model/
│   └── CandidateReview.mps
│
└── src/

An agent candidate could then modify:

C#                  source candidate
GDScript            source candidate
MPS                  semantic candidate
.pen                 design candidate
.tres assets         content candidate

using exactly the same Orc Bot candidate lifecycle.

That's very attractive.

6. I would introduce one more IR: Orc.DesignIR

This is where I would revise our previous MPS architecture slightly.

Don't make MPS consume raw Figma or .pen.

And don't make your Godot compiler understand Figma, Pencil and MPS directly.

Use:

              Figma
                │
                │ importer
                ▼
           Orc.DesignIR
                ▲
                │ importer
              .pen
                │
                ▼
        Godot visual compiler
                │
         ┌──────┴──────┐
         ▼             ▼
       .tscn          .tres
                    theme/resources

So there are actually two orthogonal IRs:

              Orc.UI.IR
           semantic behavior
                 ↑
                MPS




             Orc.DesignIR
          visual presentation
             ↑       ↑
          Figma     .pen

Then they meet through stable IDs:

Orc.UI.IR                         Orc.DesignIR
─────────                         ────────────
Surface                           Surface
Intent                            Component
State                             Layout
Binding ───────── component id ── Control
Command                           Style
Collection                        Theme
Validation                        Token

For example:

MPS:


Binding
    id = "candidate.accept"
    command = AcceptCandidate




DesignIR:


Button
    id = "candidate.accept"
    component = OrcButton
    tone = Positive
    text = "Accept"

The compiler checks:

Does DesignIR reference a binding that exists?
Does UI.IR expose every required visual binding?
Does the button invoke an allowed intent?

Now you have genuine compile-time UI validation.

7. Then the final compiler becomes very elegant
                        UI PROJECT


                  ┌──────────────┐
                  │      MPS     │
                  │ semantic UI  │
                  └──────┬───────┘
                         │
                         ▼
                    Orc.UI.IR
                         │
                         │ binding IDs
                         │
                         ▼
 Figma ──────┐       validation       ┌────── .pen
             │           ▲            │
             ▼           │            ▼
              ───── Orc.DesignIR ─────
                         │
                         ▼
              Godot Visual Compiler
                         │
                 ┌───────┴────────┐
                 ▼                ▼
               TSCN             TRES
                 │
                 ▼
             SurfaceHost


Meanwhile:


Orc.UI.IR
   │
   ├──────────────► C# presenter
   │                   desktop / ALC
   │
   └──────────────► GDScript presenter

That is, I think, substantially stronger than:

Figma → C#

or:

MPS → complete UI code

because neither one has to understand the other's concerns.

8. A2UI should not go through DesignIR

This is an important boundary.

I wouldn't do this:

Agent
  ↓
A2UI
  ↓
Orc.DesignIR
  ↓
TSCN generator
  ↓
Godot

A2UI is intentionally dynamic.

Generating a TSCN every time an agent wants to show a confirmation card defeats the point.

Instead:

A2UI description
      │
      ▼
A2UI validator
      │
      ▼
component registry


"Button"
   ↓
Known OrcButton factory


"Text"
   ↓
Known Label factory


"Card"
   ↓
Known Panel factory

A2UI's model is explicitly based on the client rendering an approved declarative component catalog rather than executing arbitrary code.

So in Godot:

A2UI Button
     ↓
A2uiGodotRenderer
     ↓
res://resident/a2ui/components/button.tscn

This is where your security boundary lives.

9. But Figma/Pencil can design the A2UI catalog

There's an interesting connection here.

Suppose Orc Bot's allowlisted A2UI catalog is:

orc.text
orc.markdown
orc.button
orc.card
orc.form
orc.progress
orc.approval
orc.artifact
orc.tool-call
orc.agent-status

Those components themselves need a visual design.

So:

                  Figma / .pen
                       │
                       ▼
                  Orc.DesignIR
                       │
                       ▼
             Godot component scenes
                       │
                       ▼
             A2UI component catalog
                       ▲
                       │
                 agent A2UI

This means agents can dynamically compose UI, but they don't design the fundamental widgets.

Designers and trusted Orc Bot code determine:

what "approval" looks like
what "danger" looks like
how buttons behave
how themes work
what actions are possible

Agents merely say:

ApprovalCard {
    title: "Merge candidate 527?"
    candidate: "527"
    actions: [
        approve,
        reject
    ]
}

That's an excellent security architecture.

10. Figma versus Pencil becomes a tooling choice, not an architecture choice

If we normalize them into Orc.DesignIR, both can coexist.

Figma lane
Figma
  ↓ REST / MCP
Figma importer
  ↓
Orc.DesignIR

Best for:

design teams
collaboration
mature visual tooling
design systems
variables
component libraries

Figma itself recommends structured components, variables, semantic layer names, Auto Layout and Code Connect to make downstream code generation more reliable.

Pencil lane
*.pen
  ↓ direct parser
Pen importer
  ↓
Orc.DesignIR

Best for:

repo-native design
coding agents
Git candidates
offline/local work
branch/diff workflows
automated transforms

The .pen format is particularly compiler-friendly because it is already a JSON object tree with reusable components, flex-like layout, themes and metadata.

There is one caveat: Pencil explicitly warns that the .pen format may receive breaking changes.

Therefore Orc Bot should treat it exactly like every other external provider format:

.pen vX
   ↓
version-pinned adapter
   ↓
Orc.DesignIR v1

Never expose .pen types as Orc Bot contracts.

That is very much in line with your provider architecture.

11. I would probably favor Pencil for Orc Bot's own dogfooding

Not because Pencil is "better than Figma" generally, but because Orc Bot has an unusual requirement:

agents themselves are first-class developers working in isolated source workspaces and publishing reviewable candidates.

A repo-local .pen fits that exceptionally well:

agent A
  └── modifies candidate-review.pen


agent B
  └── modifies activity-card.pen


agent C
  └── modifies CandidateReview.mps

Each produces an immutable Orc candidate.

Then Orc Bot can show:

Candidate #318


Source changes
  + CandidateReview.mps


Design changes
  + candidate-review.pen


Generated changes
  ~ candidate_review.tscn
  ~ CandidateReviewPresenter.generated.cs
  ~ candidate_review_presenter.generated.gd

You could even make generated artifacts not part of the candidate source delta:

candidate source


   .pen
   MPS


      ↓ reproducible compiler


build artifacts


   .tscn
   .tres
   .cs
   .gd
   .pck

That is cleaner still.

12. Figma can remain an external DesignAuthority

This actually resembles the SourceAuthority work we've been discussing.

Figma doesn't need to live in Git to participate.

Conceptually:

DesignAuthority
    │
    ├── GitPenAuthority
    │       design.pen@digest
    │
    └── FigmaAuthority
            fileKey
            nodeId
            version
            exportedDigest

A candidate from Figma becomes something like:

DesignCandidate
{
    sourceAuthority = figma:orc-ui
    sourceRevision = figma-version-123
    node = CandidateReview
    normalizedDesignDigest = sha256:...
}

Then the build consumes the immutable normalized snapshot rather than "whatever Figma contains right now."

That fits Orc Bot's existing philosophy of immutable candidates very naturally.

13. There is one authority rule I'd make strict

Never let both .pen/Figma and .tscn be editable authorities for the same layout.

Otherwise:

Designer edits Figma
       ↓
generated TSCN


Developer edits TSCN
       ↓
???


Designer edits Figma again
       ↓
developer change disappears

Choose per surface.

For example:

surface.visualAuthority = pen

means:

*.pen         SOURCE
*.tscn        GENERATED

While:

surface.visualAuthority = godot

means:

*.tscn        SOURCE
Figma/Pen     prototype/reference only

And potentially:

surface.visualAuthority = figma

means:

Figma versioned node    SOURCE
DesignIR snapshot       candidate artifact
TSCN                    GENERATED

That's exactly analogous to Orc Bot's general principle of having one explicit writer authority rather than multiple competing truths.

14. So the complete model I would aim for is
                            ORC BOT UI SYSTEM


                               DOMAIN
                                 │
                       Orc T1 contracts
                                 │
             ┌───────────────────┴───────────────────┐
             │                                       │
             ▼                                       ▼
       TRUSTED SURFACES                         AGENT ACTIVITY
             │                                       │
             │                                  ACP / AG-UI
             │                                       │
             │                               internal Activity
             │                                       │
             │                                      A2UI
             │                                       │
             │                              allowlisted renderer
             │                                       │
             │                                       ▼
             │                                    Godot
             │
    ┌────────┴─────────┐
    │                  │
    ▼                  ▼
 MPS UI model      Visual design
    │             /             \
    │          Figma           .pen
    │             \             /
    ▼              Orc.DesignIR
 Orc.UI.IR              │
    │                   │
    │                   ▼
    │             TSCN / TRES
    │                   │
    ├── C#              │

And I would assign the responsibilities this way:

Layer	Responsibility
Figma / .pen	Visual design and design-system authoring
Orc.DesignIR	Stable normalized visual representation
MPS / Orc.UI.IR	Semantic presentation behavior, bindings, intents, validation
TSCN/TRES	Godot-native compiled visual artifact
C#	Desktop presentation execution backend, collectible when appropriate
GDScript	Web presentation execution backend
AG-UI	Agent ↔ frontend runtime/event protocol
A2UI	Constrained runtime-generated UI description
Godot SurfaceHost	Actual placement, lifecycle, node ownership, windows/tabs/docks

The most important consequence is that A2UI should not replace your MPS UI language, and MPS should not replace Figma/Pencil.

They're describing different axes:

Figma/Pencil = LOOK


MPS          = MEANING + BEHAVIOR


A2UI         = DYNAMIC AGENT COMPOSITION


AG-UI        = RUNTIME CONVERSATION

That division also preserves Orc Bot's current architectural direction instead of invalidating it: Activity remains A2UI/AG-UI, while graph, timeline, terminal, inspector and ordinary panels remain native specialized Godot surfaces.

I think Orc.DesignIR is the missing concept that makes your MPS + Figma/Pencil + Godot idea coherent. Without it, you'd eventually end up writing Figma→TSCN, Pen→TSCN, Figma→MPS, Pen→MPS, etc. With it, each external design system needs exactly one importer and Godot needs exactly one visual compiler.

Branched from 分支 · Rust GDExt Web Support

Tuesday 6:13 PM
While using Zellij, a2-ui, ag-ui, does that mean the terminal content could be shown verstile rather than just text?
Does pty content be parsed or extracing json to present?

Yes. But I would phrase it as “a rich agent-session UI around a terminal”, not “turn terminal text into rich UI.”

The architecture you already have is pointing in exactly this direction: Zellij owns the human/operator terminal, while a separate machine channel owns semantic events. Orc Bot explicitly says rendered terminal text must not become lifecycle/completion truth.

Conceptually:

                         Agent CLI
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
       PTY I/O        semantic events       artifacts
          │          ACP / JSONL / AG-UI    files/diffs/
          ▼                 │               images/etc.
       Zellij               ▼                  │
          │           Provider adapter          │
          │                 │                  │
          ▼                 ▼                  ▼
 TerminalViewport       Orc Activity       Artifact model
          │              contracts              │
          │                 │                  │
          │                 ├──── A2UI ─────────┤
          │                 │                  │
          ▼                 ▼                  ▼
   Terminal surface     rich Activity       specialized
                         cards/UI             viewers
          \                 |                  /
           \________________|_________________/
                            │
                         GODOT UI

So the same run could simultaneously look like this:

┌─────────────────────────────────────────────────────────┐
│ Claude Code · task #317                     ● Running   │
├─────────────────────────────────────────────────────────┤
│ Activity                                                │
│                                                         │
│ 🛠 Read file                                             │
│    project/scripts/Foo.cs                               │
│                                                         │
│ 🛠 Edit file                                             │
│    Foo.cs                     +18 -4       [View diff]  │
│                                                         │
│ ▶ Running tests                                         │
│    ████████████░░░░  72%                               │
│                                                         │
│ ⚠ Permission requested                                  │
│    Run: dotnet test                                     │
│                    [Reject] [Allow once] [Allow]        │
│                                                         │
│ 🖼 Generated artifact                                    │
│    character-concept.png              [Preview]         │
├─────────────────────────────────────────────────────────┤
│ Terminal                                      [expand]  │
│ > dotnet test ...                                       │
│ Determining projects to restore...                      │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘

The top part does not come from parsing those terminal lines.

There are really three kinds of “JSON”

This distinction is crucial.

Source	What JSON means	Should Orc parse it semantically?
zellij subscribe --format json	JSON envelope containing rendered terminal rows	No, except as terminal presentation
Agent --output-format json/stream-json / ACP	Actual machine-semantic events	Yes
AG-UI	Standardized frontend/agent events: lifecycle, text, tool calls, state, activity	Yes
A2UI	Declarative UI components/data/actions	Yes, through allowlisted renderer

Zellij currently emits NDJSON such as pane_update containing viewport[] and optionally scrollback[]. That JSON makes the Zellij automation API structured, but the strings inside are still the rendered screen, not the program's semantic stdout.

So:

{
  "event": "pane_update",
  "pane_id": "terminal_1",
  "viewport": [
    "╭─ Claude Code ─────────────────────╮",
    "│ Editing Foo.cs...                 │",
    "╰───────────────────────────────────╯"
  ]
}

should produce:

TerminalViewport

not:

AgentEditingFile("Foo.cs")

That latter conclusion would be screen scraping.

Your ADR-0003 already makes exactly this distinction: Zellij viewport events are for presentation/reconnect/diagnostics, while the machine channel carries lifecycle, tools, artifacts, progress, approvals, and completion.

Machine JSON is different

Suppose the provider emits an actual structured event:

{
  "type": "tool_call",
  "tool": "edit_file",
  "path": "project/scripts/Foo.cs"
}

Now Orc Bot can safely translate:

provider JSON
     ↓
AgentToolCall
     ↓
Orc Activity
     ↓
A2UI
     ↓
Godot native component


┌──────────────────────────────┐
│ ✎ Editing file               │
│ project/scripts/Foo.cs       │
│                    View diff │
└──────────────────────────────┘

AG-UI formalizes this kind of structured channel. Its event model has separate lifecycle, streamed text, tool-call, state, and activity events; for example, tool calls have start/argument/end events and state deltas use JSON Patch.

And importantly, AG-UI itself explicitly distinguishes its role from generative UI: AG-UI is the agent↔frontend interaction/event protocol; A2UI is a generative/declarative UI specification.

So I would think of:

AG-UI
 = what happened / what is happening


A2UI
 = how an agent-requested interactive representation
   can be composed from permitted components
A2UI is where it becomes visually versatile

For example, instead of an agent returning:

Build failed.
3 errors.
Foo.cs line 38...

it could provide—or Orc Bot could derive from validated internal facts—an A2UI description conceptually equivalent to:

ErrorSummary
  title: "Build failed"
  count: 3


ErrorList
  items:
    - file: Foo.cs
      line: 38
      message: ...


Button
  text: "Open file"
  action: open_source

A2UI is deliberately declarative: components and application data are separate, with actions bound through its model rather than arbitrary executable code. The client controls the component catalog.

That maps extremely well to Godot:

A2UI component ID
       │
       ▼
Orc allowlisted catalog
       │
       ├─ orc.text          → Label.tscn
       ├─ orc.markdown      → MarkdownControl.tscn
       ├─ orc.tool-call     → ToolCallCard.tscn
       ├─ orc.diff          → DiffCard.tscn
       ├─ orc.approval      → ApprovalCard.tscn
       ├─ orc.progress      → ProgressCard.tscn
       ├─ orc.image         → ArtifactPreview.tscn
       └─ orc.error-list    → DiagnosticList.tscn

The agent isn't creating Godot nodes.

It says:

"show an orc.approval with this data"

and Orc Bot decides what orc.approval actually means.

This is also where your earlier MPS + TSCN + Pencil/Figma architecture connects nicely:

Pencil/Figma
     ↓
 Orc.DesignIR
     ↓
 approval-card.tscn
 tool-call-card.tscn
 diff-card.tscn
       ▲
       │
MPS semantic definitions
       │
       ▼
A2UI catalog implementation


              runtime:


Agent → AG-UI → Orc facts → A2UI
                            │
                            ▼
                     those TSCN components

So A2UI is composition, while MPS/Pencil/Figma determine the trusted component implementations.

What if the CLI only outputs JSON through stdout?

This is the tricky case.

Suppose a CLI supports:

agent --output-format stream-json

and produces JSONL on stdout.

I would not put that stdout into a PTY, let Zellij render it, then scrape the viewport back into JSON.

That becomes:

JSON
 ↓
PTY
 ↓
terminal emulator
 ↓
line wrapping
ANSI/redraw
 ↓
Zellij viewport
 ↓
try to reconstruct JSON       ← bad boundary

Instead capture the structured stream before the PTY:

                    Agent
                      │
             structured stdout
                      │
                Orc wrapper
                /          \
               /            \
              ▼              ▼
       machine events     human rendering
              │              │
              │              ▼
              │            Zellij
              │
              ▼
           AG-UI

In fact your repository already has an early version of precisely this idea in JsonlCompletionBridge: it reads bounded JSONL from the child process, identifies configured semantic terminal events, and writes a typed completion receipt rather than deriving completion from the terminal display.

For a full provider adapter, I would generalize that idea.

If the tool must retain a real TTY and can expose an extra machine endpoint, an even better arrangement is:

Agent process
   │
   ├── stdin/stdout/stderr ─────── PTY ───── Zellij
   │
   └── machine endpoint ────────── Orc adapter
          named pipe/socket/
          extra fd/protocol

ACP fits conceptually into that second lane when the provider supports it; Orc Bot already models it as an independent IAgentMachineChannel.

Therefore I would not call it “parsing the terminal”

I would establish this rule:

              PRESENTATION CHANNEL


PTY → Zellij → TerminalViewport → terminal UI
                    │
                    └── NEVER semantic authority




               SEMANTIC CHANNEL


ACP / provider JSONL / AG-UI
              │
              ▼
       typed Orc events
              │
        ┌─────┴─────┐
        ▼           ▼
     Activity      Timeline
        │
       A2UI
        │
        ▼
 rich native Godot UI

And then there is a third path for domain-specific content:

artifact event
     │
     ├── source diff ──────► diff viewer
     ├── image ────────────► image viewer
     ├── 3D model ─────────► Godot 3D viewport
     ├── ComfyUI graph ─────► GraphEdit
     ├── execution plan ────► GraphEdit
     └── ordered events ────► AnimationPlayer timeline

This is where using Godot instead of an ordinary terminal-oriented UI can become especially powerful.

Zellij doesn't have to be the UI. Zellij can just be the durable interactive terminal substrate. Orc Bot can show the same agent run simultaneously as a terminal, A2UI Activity feed, tool-call cards, approval controls, source diffs, GraphEdit execution topology, timeline, artifact previews, and diagnostics.

And the raw terminal remains the perfect fallback when the structured adapter doesn't understand something.

So I would preserve the invariant already emerging in Orc Bot:

Never upgrade PTY text into facts. Downgrade structured facts into richer presentations.

That direction is much safer—and much more versatile.