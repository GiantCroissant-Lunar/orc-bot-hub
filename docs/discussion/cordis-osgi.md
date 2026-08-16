Yes. Cordis is unusually relevant to Orc Bot, but the useful conclusion is not “adopt Cordis as Orc Bot’s framework.” The stronger conclusion is:

Orc Bot is missing an explicit semantic model for reversible, dependency-aware runtime composition. Cordis provides a very good model for that layer.

Akka.NET should remain lifecycle/supervision authority, SQLite should remain durable operational truth, and Orc Bot’s fenced workspace/candidate/validation model should remain intact. Cordis-like semantics should sit between those authorities and dynamically composed adapters, agent-context providers, UI surfaces, observers, and extension modules.

That could simplify several pieces of Orc Bot while making dynamic composition considerably safer.

What Cordis actually is

I inspected the current cordiverse/cordis repository rather than going only by its description. Current main is at 8cc9e33, dated August 13, 2026. The core package identifies itself as cordis 4.0.0-rc.8; the repository is MIT-licensed, and the maintainers explicitly state that Cordis is under active development and the API is not yet stable. There are currently no GitHub Releases.

Its own description, “A Meta-Framework of Spatiotemporal Composability,” is more meaningful than it initially sounds. Cordis currently consists of a core plus packages for loading, HMR, grouping, inclusion, timers, logging and utilities.

The accompanying preprint, dated August 13, 2026, identifies two independent problems:

Temporal composability asks whether a component can be removed and have its effects completely reverted.

Spatial composability asks whether a component can state what its environment must provide and react appropriately as those dependencies change.

The paper names the corresponding ideas revertible effects and reactive coeffects, and unifies them through a common context model. The authors say Cordis implements these ideas using effect tracking, coeffect/dependency resolution, configuration reconciliation, and HMR. The paper is also explicitly marked as a preprint under active revision.

I could inspect the authors' preprint description and repository but not reliably render the PDF body itself here, so I am deliberately not attributing detailed proofs or theorem claims beyond what the authors' public abstract says.

The academic ancestry is sound

Cordis is not inventing “effects” and “coeffects” from nothing. Algebraic-effect work models things computations do to their environment; Plotkin and Pretnar's work explicitly includes state, I/O, time, exceptions and handler constructions including rollback.

Coeffect research approaches the complementary question: not what a computation changes, but what context/resources/environment it depends upon. Petricek, Orchard and Mycroft discuss examples such as resource requirements, distributed execution context, implicit parameters and caching requirements.

There is also prior formal work explicitly combining them. Gaboardi et al.'s Combining Effects and Coeffects via Grading describes effects as changes to execution context and coeffects as demands on that context, then provides a combined calculus.

Cordis's interesting move is therefore an operational/runtime interpretation of this older theoretical separation: instead of only analyzing “changes” and “requirements,” make them drive live component activation and teardown.

What Cordis actually does at runtime

This is where it becomes especially relevant to Orc Bot.

A Cordis Context is inherited/scoped rather than simply being one global DI container. Contexts can be extended, intercepted and isolated, and the context contains services for registration, reflection, events and lifecycle fibers.

A component runs inside a Fiber. Its effects may return one disposer, multiple disposers, asynchronous disposers, etc. Cordis collects them into an effect tree. On teardown it unwinds those disposers in reverse order. Fibers have explicit states including pending, loading, active, failed, unloading and disposed.

The more interesting half is dependency handling. Plugins declare their dependencies through inject. A fiber computes whether those injected services are actually present and usable. If a required implementation disappears, the fiber becomes inactive and its effects are unloaded. If the necessary context later becomes valid again, it can be loaded again.

ReflectService.provide() is correspondingly not just ordinary registration. Providing or withdrawing a service causes dependent fibers to be notified and reevaluated. It also enforces ownership rules such as preventing a service from being set without having been provided and preventing conflicting fiber ownership.

The loader adds a declarative tree of component entries. Config changes are reconciled against existing entries, and component contexts inherit from their parents. Entries can be disabled, changed or recreated without treating the whole application as a single static composition root.

Cordis's “realms” go one step further. A service name may be mapped to a local entry-specific realm or a named shared realm; changing that mapping causes dependent services to be reevaluated. This is logical service scoping, not operating-system isolation.

Its HMR package then builds on all of this. It determines affected module dependencies, treats plugin entry modules as atomic reload units, backs up the Node module caches, imports prospective replacement modules, disposes the old plugin fibers/effects, recreates them using the replacement implementation, and attempts to restore the old cache and implementation if replacement fails.

So the deeper Cordis model is approximately:

               COEFFECTS
       "what must exist for me?"


             Requires
                 │
                 ▼
          ┌─────────────┐
 Context ─►  Component  │
          └─────────────┘
                 │
                 ▼
              Effects
       "what did I install/change?"
                 │
                 ▼
        tracked inverse/cleanup


dependency changes
      ↓
re-evaluate component
      ↓
unload effects / rebind / reload

That is much more interesting for Orc Bot than its TypeScript plugin API.

Where it fits in Orc Bot

The current Orc Bot architecture already has a fairly strong authority separation. Akka.NET is the live workflow/resource-supervision authority; SQLite owns durable operational facts; Arch ECS is rebuildable projection state; Microsoft Agent Framework prepares/contextualizes invocations but does not become workflow authority; agent loadouts and permissions are typed and frozen per attempt; source workspaces are fenced and candidates are immutable; validation slots are separately fenced.

Cordis should not replace any of those.

Instead I would introduce a new conceptual layer:

┌─────────────────────────────────────────────────┐
│        Durable domain / operational truth       │
│ SQLite • candidates • decisions • receipts      │
└───────────────────────┬─────────────────────────┘
                        │ commands / facts
                        ▼
┌─────────────────────────────────────────────────┐
│         Workflow & resource authority           │
│ Akka.NET • fences • allocation • supervision    │
└───────────────────────┬─────────────────────────┘
                        │ desired runtime state
                        ▼
╔═════════════════════════════════════════════════╗
║     Runtime Composition Plane  ← NEW            ║
║                                                 ║
║ Requires • Provides • Scope • EffectScope       ║
║ generations • reconciliation • cleanup proof    ║
╚═══════════════════════╤═════════════════════════╝
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
 agent context      UI surfaces       adapters
 providers          / observers       / bridges
 MAF/Mem0           Godot             CLI/tool

Cordis gives a very coherent theory for the highlighted box.

This is importantly not another workflow engine.

Orc Bot's WorkItem DAG answers:

What work should happen, in what causal order?

A Cordis-like composition graph answers:

Given the context available right now, which runtime contributions can legitimately be active?

Those graphs should stay separate.

The key abstraction I would bring into Orc Bot

I would translate Cordis into explicit C# contracts rather than reproduce its proxy-based ctx.foo programming model.

Something close to:

public sealed record RuntimeComponentDescriptor(
    ComponentId Id,
    CompositionScope Scope,
    IReadOnlyList<CapabilityRequirement> Requires,
    IReadOnlyList<CapabilityOffer> Provides,
    ReversibilityClass Reversibility);


public interface IRuntimeComponent
{
    ValueTask<ComponentActivation> ActivateAsync(
        CompositionContext context,
        EffectScope effects,
        CancellationToken cancellationToken);
}


public sealed record ComponentActivation(
    ComponentId ComponentId,
    long CompositionGeneration,
    IReadOnlyList<EffectReceipt> Effects);


public interface IEffectScope
{
    void Register(
        IAsyncDisposable effect,
        EffectDescriptor descriptor);
}

The important thing is not these particular names. It is the contract:

Every dynamic component explicitly declares what it requires, what it provides, what it changes, and how those changes are released.

And Orc Bot should make that observable.

Instead of a pile of:

if mem0 exists...
if provider is available...
if this surface loaded...
if this observer supports...
if agent framework is active...
if zellij exists...

the reconciler sees:

Mem0MemoryContextProvider
    requires:
        memory.scope:<attempt-scope>
        service:mem0
    provides:
        context.memory


AgentInvocationContext
    requires:
        agent.loadout
        provider.machine-channel
        context.memory?       # optional
    provides:
        invocation.context-package

Changing the environment causes a deterministic composition reconciliation.

That is Cordis's strongest contribution to Orc Bot.

It fits AgentLoadout particularly well

Orc Bot's current loadout design already separates Skill, Rule, Tool, Context, Memory, and Permission, freezes the selected inventory per attempt, preserves precedence, and keeps Microsoft Agent Framework and Mem0 subordinate to Orc Bot authority.

Cordis provides a missing runtime counterpart to that static/frozen description.

For example, a memory grant in an AgentLoadout should not itself “install memory.” It creates a requirement:

loadout says:
    memory scope = project/orc-bot/work-item-X


composition says:
    required service:
        Mem0ContextSource(scope X)


if available:
    activate contribution
    record exact digest
    provide context.memory


if unavailable:
    required -> attempt cannot become ready
    optional -> run without that contribution, with diagnostic

That would make the distinction among inventory, availability, binding, and authority much clearer.

One warning is critical: a Cordis coeffect is not a permission.

“Component requires workspace.write” must never be enough to obtain workspace.write. Orc Bot's existing permission policy remains the authority that creates an actual grant. A requirement can select an existing grant; it cannot manufacture one.

So:

requirement ≠ permission
dependency  ≠ authority
service     ≠ capability grant

This is an area where Orc Bot's current model is actually stricter than Cordis and should remain so.

It also improves the provider registry

The current provider registry knows about real provider availability, machine channels, capabilities and remediation.

With Cordis-style reactive coeffects, availability becomes an active composition fact.

Suppose a provider adapter exposes:

provides:
    agent.provider.codex
    machine-channel.jsonl
    capability.source-author

and its executable disappears or its probe changes generation.

The composition plane withdraws those offers.

Everything depending on them is then reevaluated.

That could automatically drive:

provider panel       → unavailable
agent profile        → unavailable for new attempts
workflow start       → blocked with exact missing requirement
context adapter      → unloaded
existing owned run   → NOT automatically terminated

That last line matters.

A live Akka-owned operation must not disappear because its composition dependency disappeared. Akka owns that lifecycle and must reconcile the real external resource, resulting in the appropriate durable state such as interrupted, unavailable, cleanup-pending or operator-attention.

This is why Cordis belongs under Akka rather than replacing it.

The old Orc Bot UI/bundle work becomes more understandable

The earlier Orc Bot experiment had a proposed SurfaceHost model in which a resident Godot shell hosted reloadable surfaces while bundle-owned view models and resources could be replaced, with cleanup, collectible AssemblyLoadContext verification, quarantine and restart-required dispositions.

Cordis gives that old design a much cleaner theoretical foundation.

A future Orc Bot surface could say:

Surface: agent-roster


requires
    projection.agent-roster
    command.agent-select


effects
    instantiate scene
    subscribe to projection
    register selection handler
    register layout instance
    bind presenter


dispose
    unsubscribe
    detach presenter
    remove layout instance
    free scene

The host should not have to know panel-specific cleanup rules.

Every surface owns an activation lease containing its reversible registrations.

That would significantly reduce the danger of stale Godot signals, old view models, lingering callbacks or a collectible ALC remaining rooted after a reload.

But I would not resurrect that entire old hot-reload architecture into the current foundation yet. Cordis makes it a better future design, not an urgent foundation requirement.

One thing I would change from Cordis: “reversible” is not binary

The paper's notion of temporal composability is deliberately strong: component removal completely reverts its effects.

That is useful theory, but Orc Bot deals with far more hostile effects than an in-process plugin runtime.

A Godot signal connection really can be reversed.

Registering a context provider can generally be reversed.

Opening a temporary file may be reversible.

Launching an external process is only reversibly cleaned up if Orc Bot can prove the entire process tree is gone.

Changing an engine project's derived state may require reconciliation.

Publishing an immutable candidate is a durable fact and should never be “unpublished” by a disposer.

A human acceptance decision is historical truth.

A Git push is certainly not an IAsyncDisposable.

So I would introduce something like this classification:

Class	Meaning in Orc Bot	Example
EphemeralReversible	Exact inverse is expected and provable	subscription, registration, timer, UI binding
OwnedCleanup	Cleanup is expected but needs external evidence	process tree, terminal session
Compensatable	No exact inverse; a controlled compensating operation exists	some tool/slot mutations
DurableIrreversible	Historical/domain fact; never managed by composition disposal	candidate publication, decision, integration fact

That keeps Cordis's insight without pretending every side effect in an agent-development system is mathematically invertible.

For the latter three cases, deactivation should return a typed disposition such as:

Reverted
Released
ResidualState
RestartRequired
Quarantined

rather than merely completing DisposeAsync().

This fits Orc Bot's current fail-closed approach much better.

Cordis “isolate” should not become Orc Bot isolation

Cordis's realm/isolation feature is clever: services can be remapped into entry-local or named shared realms, allowing different component groups to resolve different implementations of the same logical service.

That is useful for Orc Bot's composition scopes.

For example:

global
  └─ repository
      └─ workflow run
          └─ work item
              └─ attempt

An attempt can resolve its own memory scope or provider session without globally replacing a service.

But this is name-resolution isolation. It is not:

security sandbox
process containment
filesystem isolation
source-workspace fencing
credential isolation
validation-slot fencing

Those must remain Orc Bot's explicit security/resource mechanisms.

The distinction is especially important because Cordis currently has an open issue demonstrating that isolate teardown can over-clean parent registrations in a reproduction.

Cordis's HMR algorithm is conceptually useful, but don't port it

There is a good abstract transaction hidden inside Cordis HMR:

determine affected component closure
        ↓
load prospective replacements
        ↓
verify they can be constructed
        ↓
dispose old reversible effects
        ↓
activate new generation
        ↓
success ──────────┐
                  │
failure → restore previous generation

That is a good model for Orc Bot.

But Cordis's actual implementation manipulates Node's internal ESM/CJS module caches, requires Node-loader internals, and has version-specific code for Node 22–24.

Orc Bot's corresponding mechanism would be completely different:

.NET AssemblyLoadContext
Godot PCK/resource lifecycle
resident-vs-collectible contracts
process boundaries
explicit activation manifests

So I would copy the state machine, not the source code.

And even the state machine needs stronger generation fencing.

Cordis currently has an open issue demonstrating an ABA race where an asynchronous load starts with state A, configuration transitions A→B→A while loading, and the old activation can see A again and incorrectly conclude nothing changed.

Orc Bot already thinks in terms of monotonic fences/generations. It should use that advantage.

Every composition transition should have:

DesiredCompositionGeneration = 42


activate component against generation 42
        ↓
async initialization
        ↓
before publishing activation:
    expectedGeneration == currentGeneration ?
        yes → commit activation
        no  → dispose stale activation

Never compare only a computed dependency state for equality.

That is a direct lesson Orc Bot can take from Cordis's current implementation experience.

This gives Orc Bot a useful third kind of graph

Cordis also clarifies something about Orc Bot's visual graph direction.

There should really be at least three logically different graphs:

Work graph
    "What must be done?"
    durable WorkItems / dependencies


Resource graph
    "What owns what?"
    workspace / attempt / session / validation slot / candidate


Composition graph
    "What can currently be active?"
    requires / provides / active generation / effects

The first is intentional workflow.

The second is authority/ownership.

The third is reactive runtime composition.

Trying to make one graph serve all three would blur exactly the distinctions Cordis helps expose.

Godot GraphEdit can project all three, but with different graph dialects and different semantics. The current Orc Bot architecture already keeps projection subordinate to the runtime, so this fits naturally rather than requiring GraphEdit to become authority.

A particularly powerful debugging UI falls out of this

Cordis exposes an effect tree internally. Orc Bot could make something like that a first-class operator surface.

For every active runtime component, Orc Bot could show:

AgentInvocationContext / attempt-123
│
├─ Requires
│   ├─ ✓ agent.loadout / d861…
│   ├─ ✓ provider.codex / a972…
│   ├─ ✓ machine-channel.codex-jsonl
│   └─ ✗ memory.mem0.scope.project-x
│
├─ Provides
│   └─ invocation.context-package
│
├─ Effects
│   ├─ registered context provider
│   ├─ machine-channel observer
│   └─ temporary control-root materialization
│
└─ State
    Blocked
    reason: required memory scope unavailable

And for teardown:

Releasing AgentInvocationContext
  ✓ observer detached
  ✓ context provider removed
  ✓ temporary root removed


Disposition: Reverted

or:

Disposition: ResidualState
process 18272 still observed
→ operator attention / quarantine

For an agent orchestrator, that is considerably more useful than “plugin loaded” / “plugin unloaded.”

The implementation risk is real

I would not make Cordis itself a required Orc Bot dependency today.

Beyond the explicit RC/API-unstable status, Cordis currently has open lifecycle issues around asynchronous generation/epoch handling and scoped cleanup.

Those bugs do not invalidate the model. In fact, they are useful evidence of what Orc Bot's own implementation must test especially aggressively.

And Cordis is solving a Node/TypeScript dynamic-component problem. Orc Bot has much stronger concerns: durable facts, external processes, process containment, agents running for long periods, source fencing, validation authority, human decisions, Godot object lifetime and potentially collectible .NET assemblies.

So an embedded Cordis runtime would produce more architectural mismatch than benefit.

What I would change in Orc Bot

I would make this a new ADR—something like “Runtime contributions use reactive requirements and explicit effect ownership”—and implement it incrementally rather than as a rewrite.

First, introduce BCL-only composition contracts. Add typed Requirement, Offer, CompositionScope, ReversibilityClass, EffectDescriptor, ActivationReceipt and DeactivationReceipt. An activation receives a monotonic composition generation and an EffectScope; it cannot silently register global callbacks or resources outside that scope.
Then build a small CompositionReconciler, not another actor framework. Akka tells it desired runtime composition. It calculates Requires → Provides, starts components in dependency order, stops dependents before providers, and CAS-checks its generation after every asynchronous boundary. Its state is disposable/rebuildable. If desired activation itself matters durably, SQLite records the intent and receipts, never serialized component objects.
Dogfood it on low-authority Orc Bot components first. Agent invocation/context composition is a strong candidate: Agent Framework context providers, optional Mem0 context, read-only observation and provider capability availability. This exercises scopes, optional versus required dependencies, context removal, reload and diagnostics without entrusting candidate integration or source mutation to the new mechanism.
Only after that should the model govern reloadable UI/modules. At that point the previous SurfaceHost/collectible-payload ideas can be reconsidered using explicit effect ownership and coeffect requirements. HMR/ALC becomes one provider of the composition semantics, not the semantics themselves.

The acceptance tests should deliberately reproduce the classes of lifecycle problems already visible in Cordis: A→B→A during asynchronous activation, disposing child scope without touching parent effects, provider removal during dependent startup, failed partial activation, rebind to a new provider generation, teardown ordering, double disposal, cancellation during load/unload, and incomplete external cleanup producing quarantine rather than success. Cordis's current open lifecycle bugs make those particularly valuable adversarial fixtures.

Bottom line

Cordis changes my view of one part of Orc Bot's architecture quite substantially.

I would now describe Orc Bot as needing three distinct control mechanisms:

1. Durable orchestration
   Akka.NET + SQLite
   intent, workflow, authority, recovery


2. Resource transactions
   fenced workspace + candidate + validation slot
   ownership, immutable handoff, mutation safety


3. Reactive runtime composition          ← Cordis-inspired
   requires + provides + effect ownership
   scopes, availability, dynamic binding, unload/reload

The first two are already central to the current Orc Bot design.

Cordis gives a very convincing conceptual foundation for the missing third one.

And I would borrow that foundation fairly aggressively—especially revertible effect ownership, reactive requirements, scoped contexts, desired/observed reconciliation, and generation-safe reactivation—while deliberately not adopting Cordis itself as Orc Bot's runtime, not turning coeffects into permissions, and not applying “reversibility” to durable candidate/decision history.

That separation would also give future Orc Bot extension concepts a common rule:

Anything dynamically attachable must say what it needs, what it provides, what it changes, how those changes are released, and what Orc Bot does if release cannot be proven.

That is probably the most valuable architectural idea Cordis contributes to Orc Bot.

how does these compared to "https://en.wikipedia.org/wiki/OSGi", can you do more research?

Yes. After looking at OSGi Core, Declarative Services, Configuration Admin, its dependency-management research, and comparing those against Cordis's code/paper, I would revise my previous conclusion somewhat:

A large part of what I called the missing “runtime composition plane” in Orc Bot already has a mature historical precedent in OSGi—especially OSGi Declarative Services.

Cordis is still interesting, but its most distinctive contribution is not dynamic dependency injection itself. OSGi has been doing that for decades. Cordis's stronger contribution is the explicit effect/coeffect formulation and fine-grained reversible-effect ownership.

So for Orc Bot I would now borrow different pieces from each:

OSGi
  → module/revision/wiring model
  → requirements/capabilities
  → dynamic service registry
  → declarative component satisfaction
  → binding policies/cardinality/scopes
  → configuration model


Cordis
  → effect/coeffect conceptual unification
  → explicit EffectScope
  → nested reversible effects
  → scoped composition contexts
  → reconciliation as context changes


Orc Bot
  → durable authority, fences, receipts, quarantine
  → Akka.NET supervision
  → SQLite operational truth
  → agent/workspace/tool semantics

That combination is stronger than adopting either OSGi or Cordis wholesale.

First: OSGi is much closer to Cordis than the Wikipedia page initially suggests

The Wikipedia summary describes OSGi as a Java modularity/service platform with dynamically installable bundles, lifecycle management, and a service registry. That's accurate at a high level.

But the really relevant part for this discussion is Declarative Services (DS).

OSGi Core's service layer defines a dynamic publish/find/bind model: bundles publish Java objects as services, other bundles discover them, and consumers can observe services appearing, changing, and disappearing.

Declarative Services then adds a component runtime on top. A DS component declares references to services; its component configuration is considered satisfied only when its mandatory references are available. If an active component becomes unsatisfied, SCR deactivates it. When its requirements become satisfied again, it can be activated again.

That should sound very familiar after Cordis.

Cordis:

provide A
     ↓
fiber requiring A becomes viable
     ↓
activate


remove A
     ↓
fiber no longer viable
     ↓
unload


provide A again
     ↓
reload

OSGi DS:

register service A
      ↓
reference becomes satisfied
      ↓
activate component configuration


unregister A
      ↓
mandatory reference unsatisfied
      ↓
deactivate component


replacement A available
      ↓
satisfied again
      ↓
reactivate

So Cordis's “reactive coeffects” have a very strong operational analogue in OSGi Declarative Services.

That is probably the biggest correction to my earlier framing.

OSGi DS is actually more sophisticated than Cordis today in some dependency areas

Cordis currently has a relatively compact dependency mechanism: a plugin has inject requirements; ReflectService tracks provided implementations; dependency changes refresh the fiber.

OSGi DS has accumulated significantly more policy around this problem.

A service reference can have cardinalities:

0..1    optional single
1..1    mandatory single
0..n    optional multiple
1..n    mandatory multiple

and a mandatory cardinality becoming unsatisfied can deactivate the component.

It also distinguishes static and dynamic references.

With a static reference, changing the bound service can deactivate/reactivate the component.

With a dynamic reference, SCR can call bind/unbind/update methods on the existing component without destroying the component instance.

Then it adds reluctant vs greedy selection:

reluctant
    keep current suitable implementation


greedy
    switch when a better implementation appears

Service ranking and filters provide further selection semantics.

Cordis's current model mostly takes the simpler position:

dependency identity changes
          ↓
effectively recompute fiber epoch
          ↓
unload / reload as needed

So if Orc Bot needs sophisticated runtime provider rebinding, OSGi DS is a richer source of design ideas than Cordis.

The OSGi research lineage is almost uncannily similar to Cordis's motivation

This is especially interesting.

The OSGi Declarative Services specification explicitly cites the 2003 Cervantes/Hall paper Automating Service Dependency Management in a Service-Oriented Component Model.

Its motivation was that application building blocks could become dynamically available or unavailable, potentially because the surrounding context changes, and applications should automatically adapt their composition rather than making developers write error-prone dependency-tracking code.

That's conceptually extremely close to Cordis's spatial composability.

Twenty-three years apart:

OSGi DS research, 2003


context/environment changes
      ↓
available services change
      ↓
declared dependencies change satisfaction
      ↓
component composition changes

versus:

Cordis, 2026


context changes
      ↓
coeffect requirements change satisfaction
      ↓
fiber composition changes

So Cordis isn't discovering the operational problem.

What it is doing is giving it a more explicit programming-language-theoretic interpretation.

The major difference is Cordis's treatment of effects

This is where Cordis remains genuinely interesting.

OSGi has lifecycle cleanup.

When a bundle stops, the framework unregisters services registered by that bundle, releases services it was using, and removes listeners registered through the framework. A BundleActivator.stop() is also expected to undo work performed during start().

Declarative Services similarly has activation/deactivation callbacks.

But arbitrary component effects are not represented as one first-class tree of reversible operations.

Suppose an OSGi component does this:

register service
subscribe to external event source
start timer
open socket
spawn thread
create temp file
register callback in third-party library

OSGi understands some of those directly.

The rest are the component author's cleanup responsibility.

Cordis makes the pattern itself a primitive:

ctx.effect(() => {
    acquireSomething()


    return () => {
        releaseSomething()
    }
})

and effects can contain child effects, asynchronous disposal, multiple disposers, and reverse-order unwinding.

Conceptually:

Component
 │
 ├── Effect A
 │    ├── Effect A1
 │    └── Effect A2
 │
 ├── Effect B
 │
 └── Effect C


dispose component


C⁻¹
B⁻¹
A2⁻¹
A1⁻¹
A⁻¹

That is much closer to structured resource lifetime.

This is the Cordis idea I would most strongly import into Orc Bot.

OSGi also has a dimension Cordis mostly lacks: real module wiring

This is the other huge difference.

OSGi isn't merely a service container.

Its module layer controls actual code visibility.

Bundles declare exports/imports, versions, requirements and capabilities. Before a resource can operate, the resolver computes a wiring satisfying its mandatory requirements. OSGi Core generalizes this through namespaced Requirement and Capability objects plus filters.

Conceptually:

Bundle A
 provides:
   package Foo 2.1
   capability parser=json


 requires:
   package Bar [3,4)
   capability storage=sqlite


Bundle B
 provides:
   package Bar 3.6


Bundle C
 provides:
   capability storage=sqlite


             Resolver
                ↓


A ─── Bar ─────► B
A ─── storage ─► C

Once resolved, OSGi maintains stable wiring. Importantly, updating or uninstalling the provider does not necessarily make existing consumers immediately switch revisions; an already-resolved bundle can continue loading classes from the revision it was wired to until a refresh.

This is a much stronger concept than Cordis's runtime provide()/inject() mechanism.

Cordis has Node's module graph plus its own service context, loader and HMR, but it doesn't replace Node with an OSGi-style versioned module resolver/class-loader graph. Its HMR package instead analyzes module dependencies and manipulates Node ESM/CJS caches.

For Orc Bot's future .NET AssemblyLoadContext module architecture, OSGi is therefore more relevant than Cordis for the actual binary/module layer.

OSGi teaches an important distinction Orc Bot should adopt

I now think Orc Bot should explicitly distinguish three different kinds of dependency.

1. Deployment/module requirements

Can this piece of code even be loaded?

requires contract API >= 3 < 4
requires host capability: godot.surface-host/v2
requires OS: windows
requires architecture: x64
requires .NET >= 8

This is OSGi's Resource/Requirement/Capability territory.

2. Runtime service requirements

Given loaded code, can this component currently operate?

requires provider.codex
requires terminal.zellij
requires memory.mem0?
requires projection.agent-roster

This is the domain where OSGi DS and Cordis overlap.

3. Authority/resource requirements

May this component perform this operation?

requires:
    permission.workspace.write
    allocation fence 42
    validation-slot lease
    candidate digest

This is Orc Bot-specific and should remain outside both OSGi and Cordis dependency satisfaction.

That gives:

          MODULE RESOLUTION
        OSGi-inspired resolver
                 │
                 ▼
          code can be loaded
                 │
                 ▼
        RUNTIME COMPOSITION
   OSGi DS + Cordis inspired
                 │
                 ▼
        component can be active
                 │
                 ▼
        AUTHORITY EVALUATION
          Orc Bot policies
                 │
                 ▼
        action may be performed

That's substantially safer than treating all three as “capabilities.”

OSGi Config Admin also maps surprisingly well to Orc Bot

Cordis's loader manages a declarative entry/config tree and reconciles entries when their configuration changes.

OSGi has a mature counterpart: Configuration Admin.

Configuration Admin persistently stores configuration objects identified by PIDs. It watches the service registry and pushes matching configuration to registered targets. A Managed Service Factory can create multiple differently configured instances from multiple configuration objects.

And DS integrates with this directly.

A DS component can require configuration before it is considered satisfied:

component requirements satisfied
           +
required configuration exists
           ↓
        activate

Configuration changes can trigger a modification callback or component deactivate/reactivate.

This could inform Orc Bot's future extension configuration.

For example:

ComponentDefinition
    "provider.codex"


Configuration
    executable = C:\...\codex.exe
    model = ...
    protocol = jsonl


Service state
    executable exists
    credential usable
    protocol probe succeeds


Composition
    provider.codex = SATISFIED

But I would not make configuration itself authoritative. Orc Bot's current design correctly makes actual capability probes and typed evidence authoritative over configuration claims.

Service scope has another direct Orc Bot parallel

OSGi services can have three scopes:

OSGi scope	Meaning
singleton	one service object globally
bundle	one service object per consuming bundle
prototype	a distinct service object per request

Cordis approaches a related question using inherited contexts and isolation realms.

For Orc Bot, I would use domain-native scopes:

Application
    │
    ├── Project
    │    │
    │    ├── WorkflowRun
    │    │    │
    │    │    ├── WorkItem
    │    │    │    │
    │    │    │    └── Attempt

A composition service could declare:

Mem0 transport
scope: application


project memory source
scope: project


agent loadout context
scope: attempt


provider machine channel
scope: attempt


usage observer
scope: application


validation process
scope: validation lease

This combines the useful part of OSGi service scopes with Cordis context inheritance without confusing them with security isolation.

Hot update: OSGi and Cordis make opposite trade-offs

This part is especially instructive for Orc Bot.

OSGi

A bundle update installs a new revision. If installation of the replacement fails, the original must be restored. But existing resolved consumers can remain wired to the old revision until a framework refresh occurs.

So OSGi essentially says:

old revision
    │
    ├──── existing stable wiring ──── consumers
    │
new revision installed
    │
    └──── available to new resolution


refresh
    ↓
recompute wiring

That's extremely conservative and good for type/class consistency.

Its downside is that multiple revisions and stale object references can coexist. Academic work has documented OSGi “stale reference” problems when active code retains objects originating from stopped or updated bundles.

Cordis

Cordis HMR is much more eager:

changed module
   ↓
compute affected plugin closure
   ↓
load replacements
   ↓
dispose old fibers
   ↓
install replacements
   ↓
rollback if failure

That is excellent for a development loop but harder to make watertight; Cordis currently has open lifecycle-race/cleanup issues, as we discussed previously.

For Orc Bot

I would take an intermediate model:

install immutable ComponentRevision N+1
          ↓
resolve dependencies without touching N
          ↓
construct candidate activation
          ↓
verify candidate generation
          ↓
quiesce N
          ↓
dispose N's EffectScope
          ↓
verify collection / external cleanup
          ↓
activate N+1
          ↓
commit ComponentWiring N+1


failure
    ↓
reactivate N
    OR
quarantine / restart-required

That is OSGi-style revisioning + Cordis-style explicit effects + Orc Bot-style evidence and quarantine.

The biggest place Orc Bot should exceed both systems

Neither OSGi nor Cordis operates under Orc Bot's threat and authority model.

A dynamically composed Orc Bot component may control:

a coding agent
a writable source allocation
a process tree
a GPU-heavy editor
a Git candidate
a validation slot
credentials
a human approval workflow

That means Deactivate() cannot merely mean:

“the callback returned successfully.”

Orc Bot already has a much stronger cleanup philosophy: its native-session contracts explicitly distinguish confirmed released resources from retained or unknown cleanup states, and its process-containment code requires evidence rather than inferring release. Its architecture also deliberately keeps Akka.NET as live lifecycle authority, SQLite as durable operational authority, and adapters/frameworks subordinate to those authorities.

So Orc Bot should augment the OSGi/Cordis model:

OSGi:
    lifecycle transition


Cordis:
    disposer executed


Orc Bot:
    disposer executed
       +
    real external state observed
       +
    receipt recorded
       ↓
    Released


otherwise:
    Retained
    Unknown
    Quarantined
    RestartRequired

That's a major architectural advantage Orc Bot can have.

I would now change the proposed Orc Bot component contract

Previously I suggested something relatively Cordis-like.

After comparing OSGi, I would make it more explicit:

ComponentDescriptor
{
    Id
    Version
    RevisionDigest


    ModuleRequirements
    RuntimeRequirements
    Provides


    Scope
    ActivationPolicy
    BindingPolicy
    Reversibility
}

Where a requirement could resemble OSGi more than simple DI:

Requirement:
    namespace: agent.machine-channel
    filter:
        protocol = "acp"
        provider = "codex"
    cardinality: 1..1
    policy: static
    required: true

And:

Offer:
    namespace: agent.machine-channel
    properties:
        protocol: acp
        provider: codex
        version: 1

Then introduce a Cordis-inspired activation primitive:

ActivateAsync(
    ComponentContext context,
    EffectScope effects,
    CancellationToken cancellationToken)

Every reversible registration goes into EffectScope.

And an Orc Bot-specific deactivation result:

DeactivationReceipt
{
    ComponentRevision
    CompositionGeneration


    EffectsExpected
    EffectsReleased


    ExternalResourcesObserved


    Disposition:
        Released
        ResidualState
        Quarantined
        RestartRequired
}

This is considerably stronger than either source architecture alone.

OSGi also changes how I think Orc Bot should name things

Instead of a single vague Capability, I would make several concepts explicit.

ModuleRequirement / ModuleCapability
    load-time compatibility


ServiceRequirement / ServiceOffer
    runtime composition


PermissionGrant
    authority


ResourceClaim / Lease
    exclusive physical ownership


Ability
    agent-facing UI inventory


Skill / Rule / Context / Memory
    agent semantics

This matches something Orc Bot already does very well: its accepted agent-loadout design explicitly refuses to collapse skills, rules, tools, context, memory, and permissions into one semantic category, and keeps Microsoft Agent Framework from becoming a competing lifecycle authority.

OSGi strengthens the case that “capability” should not become one universal bag of things.

How I now see Cordis versus OSGi
Concern	OSGi	Cordis	Better source for Orc Bot
Code/module isolation	Very strong	Relies largely on JS/Node modules	OSGi
Versioned module wiring	Very strong	Limited	OSGi
Requirements/capabilities	Rich generalized model	Inject/provide context model	OSGi
Service registry	Mature	Context/ReflectService	OSGi
Dynamic dependency activation	Very mature DS	Fiber reconciliation	OSGi DS
Optional/multiple dependencies	Cardinality built in	Less explicit	OSGi
Rebinding policy	static/dynamic, greedy/reluctant	mostly reload/reconcile	OSGi
Scoped service instances	singleton/bundle/prototype	context/realm isolation	Both
Configuration reconciliation	Config Admin + DS	loader entry tree	Both
Fine-grained effect ownership	Limited/general cleanup manual	Core primitive	Cordis
Nested disposer tree	No equivalent core concept	Yes	Cordis
Formal effect/coeffect framing	No	Central idea	Cordis
Hot replacement	Bundle update/refresh/revisions	HMR dependency closure	Depends
Rollback evidence	Framework-level	in-memory rollback	Neither
External process/resource proof	No	No	Orc Bot
Durable workflow authority	No	No	Orc Bot/Akka+SQLite
Candidate/workspace semantics	No	No	Orc Bot

This is the important picture.

A useful way to think about the three systems

OSGi answers:

How can independently versioned modules and dynamic services safely inhabit one long-running Java runtime?

Cordis asks:

How can dynamically composed components explicitly express what context they need and cleanly reverse what they install?

Orc Bot asks something larger:

How can dynamically composed software agents operate on real development resources under durable authority, isolation, evidence, review and recovery?

So:

                 Orc Bot
              ┌────────────┐
              │ Authority  │
              │ Evidence   │
              │ Fences     │
              │ Workflow   │
              └─────┬──────┘
                    │
          runtime composition
                    │
         ┌──────────┴──────────┐
         │                     │
     OSGi lessons          Cordis lessons
   requirements /          effects /
   capabilities /          coeffects /
   revisions /             scoped context /
   binding policy          disposer ownership

I think that is a substantially more complete architecture than the Cordis-only interpretation.

What I would do for Orc Bot now

I wouldn't implement this immediately. The current accepted Orc Bot first slice explicitly excludes dynamic module loading, while making Akka.NET the single live lifecycle/supervision authority, SQLite the durable authority, and adapter/framework types subordinate to provider-neutral contracts.

But I would record an architecture research/ADR precursor now, because it will matter later for provider extensions, dynamically added UI surfaces, ComfyUI/n8n/iii adapters, graph dialects, tool integrations and reloadable Godot/.NET modules.

I would name the future abstraction something like Component Composition Model, and base it explicitly on:

OSGi Resource + Service + Declarative Services semantics for requirements, capabilities, scopes, revisions and binding policy; Cordis semantics for EffectScope/coeffects and reversible activation; Orc Bot semantics for authority, generation fencing, external cleanup evidence, quarantine and durable receipts.

That feels like the right synthesis rather than reinventing either framework.

And there is one particularly interesting next comparison: OSGi Declarative Services vs MEF/MAF/.NET AssemblyLoadContext vs Cordis. Since Orc Bot is C#, that would let us determine what parts of the OSGi model can already be implemented using existing .NET primitives, what MEF already covers, and what genuinely needs a new Orc Bot composition layer.

Please do more research, especially ALC as we are going to Godot project written in C#

Yes. Looking specifically at Godot + C# + AssemblyLoadContext, I think the architecture becomes much clearer than in the OSGi/Cordis-only comparison.

The central conclusion is:

ALC should be Orc Bot's low-level managed module/revision mechanism, but it should not itself be Orc Bot's component framework.

Use ALC for code identity, dependency isolation and collectible revisions; take requirement/service/revision ideas from OSGi; take effect ownership and reactive reconciliation ideas from Cordis; and keep Orc Bot's Akka.NET/SQLite/fencing model above all of them.

There is also a very important Godot-specific constraint: the exported Godot application should be treated as a resident, non-reloadable C# shell. Only carefully constrained plain-C# payloads should live in Orc Bot-created collectible ALCs.

The most important Godot discovery

Godot itself already uses AssemblyLoadContext.

Its current PluginLoadContext has almost exactly the pieces we have been discussing: an AssemblyDependencyResolver, a set of assemblies that must be shared with the main context, an explicit reference to that main context, managed dependency resolution, native dependency resolution, and an isCollectible switch. For shared assemblies, Godot deliberately resolves them from the main load context rather than loading another copy.

Godot's managed bootstrap also explicitly treats GodotSharp as a shared assembly and obtains the actual context containing its managed host with AssemblyLoadContext.GetLoadContext(...); crucially, the project assembly is loaded with collectibility tied to whether Godot is running in the editor.

And Godot's C# reload implementation has an even stronger restriction: project-assembly reload is disabled outside editor mode. In other words, the fact that C# scripts can reload in the Godot editor must not be interpreted as exported-game/runtime hot reload support.

That aligns with Godot's public modding documentation, which tells a C# application loading an external PCK to load the accompanying DLL with Assembly.LoadFile(...). That is useful for loading additional code, but it does not give Orc Bot the controlled collectible/revision lifecycle we want.

So our exported application should look like:

Godot process
│
├── Godot managed hosting
│
├── GodotSharp                     resident
│
└── Orc Bot project assembly       resident / non-collectible in player
    │
    ├── Godot Nodes
    ├── SurfaceHost
    ├── GraphEdit / Window / UI
    ├── runtime composition bridge
    ├── shared contracts
    │
    └── Orc Bot-created collectible ALCs
        │
        ├── Extension revision A
        ├── private dependencies
        └── NO GodotObject-derived objects

There isn't literally a CLR parent/child ALC hierarchy here. The arrows mean explicit delegation policy. That distinction matters.

What ALC actually gives us

AssemblyLoadContext is fundamentally a loader namespace plus lifetime boundary.

Within one ALC, only one assembly version per simple assembly name can be loaded. Multiple ALCs make it possible for separate modules to load different versions of the same dependency, and they also provide a natural grouping boundary for later unloading.

For example:

Resident Orc Bot
    Newtonsoft.Json 14.x


ALC: ComfyAdapter-r17
    SomeLib 2.x


ALC: LegacyToolAdapter-r4
    SomeLib 1.x

That is quite close to an OSGi bundle revision from the code-loading perspective.

But ALC does not provide OSGi's resolver, service registry, Declarative Services, configuration model, bundle lifecycle, or Cordis's effects/coeffects. It only gives us primitives with which those things can be implemented.

And its isolation is not security isolation. Microsoft explicitly describes ALC dependency isolation as name-resolution isolation rather than a binary/process security boundary. Microsoft also warns that untrusted plugins should not be loaded into a trusted .NET process; an OS or virtualization boundary should be used when security/reliability isolation is required.

That is particularly important for Orc Bot.

An agent-generated adapter should not automatically become:

download DLL
→ create ALC
→ execute arbitrary DLL inside Orc Bot

ALC is not a sandbox.

Type identity is the first major trap

This may be the single most important implementation rule.

Two types with exactly the same namespace and class/interface name are different CLR types when their definitions came from different Assembly instances. Microsoft explicitly documents the confusing result where an object of X cannot be converted to X.

Imagine:

Resident ALC
  OrcBot.Extensibility.Contracts.dll
      IOrcComponent


Plugin ALC
  OrcBot.Extensibility.Contracts.dll   ← accidental second copy
      IOrcComponent

Then:

typeof(host.IOrcComponent)
    !=
typeof(plugin.IOrcComponent)

and this can fail:

instance is IOrcComponent

even though the source code appears identical.

This is exactly why the old Orc Bot experiment's implementation was significant. Its ManagedPayloadHost did not blindly use AssemblyLoadContext.Default; it obtained the context actually containing IBundleService:

AssemblyLoadContext.GetLoadContext(
    typeof(IBundleService).Assembly)

and delegated shared contract assemblies to that context. Its comments explicitly identify duplicate contract assembly identity as the failure mode.

That is the correct pattern for Godot because our resident Orc Bot assembly may itself not live in AssemblyLoadContext.Default.

So our future loader should conceptually do:

var hostContext =
    AssemblyLoadContext.GetLoadContext(
        typeof(IOrcComponent).Assembly)
    ?? AssemblyLoadContext.Default;

and explicitly share:

OrcBot.Extensibility.Contracts
possibly selected Orc Bot DTO contract assemblies

from that context.

Not from some guessed global default.

Microsoft's own ALC documentation describes shared dependencies exactly this way: one context owns the Assembly instance and another context returns that same instance during resolution.

This means we should create a very small stable contract assembly

I would not use the complete OrcBot.Contracts assembly as the permanent plugin ABI if we can avoid it.

I would eventually introduce something like:

OrcBot.Extensibility.Contracts

containing only BCL-shaped types:

IOrcComponent
ComponentDescriptor


ComponentId
ComponentRevision


ServiceRequirement
ServiceOffer


ActivationContext
ActivationReceipt
DeactivationReceipt


EffectDescriptor


immutable DTOs

No:

Godot.Node
Godot.Resource
Godot.Variant


Akka ActorRef
Arch Entity
SQLite connection


Zellij handles
Process handles


Mem0 SDK types
Agent Framework implementation types

The reason is partly architectural and partly ALC longevity.

Every shared contract becomes something the resident runtime and every extension revision must agree upon. The larger that assembly becomes, the more often unrelated changes invalidate extension compatibility.

The previous Orc Bot experiment already encountered a related problem with its bridge: embedding a large changing contract closure made unrelated contract changes churn the binary digest and force re-admission. The current research record recommends recovering that idea only with a much smaller stable protocol boundary.

The second major rule: Godot objects stay outside the collectible ALC

This rule becomes much stronger after inspecting Godot's own implementation.

The old Orc Bot experiment already specified:

PCK/content               potentially replaceable
resident Godot C#         process lifetime
plain C# managed payload  collectible

and explicitly prohibited types deriving from Node, Resource, RefCounted, or GodotObject inside the collectible payload.

It also encoded the same rule directly into IBundleService: implementations are plain C#, must not hold a Node/Resource, and return data so a resident node can update the scene tree.

After inspecting Godot's own reload machinery, that looks like a very good design boundary rather than merely an old experiment workaround.

Godot's managed integration has to maintain native↔managed object identity and handles. That makes arbitrary Godot-derived types much more complicated than ordinary CLR objects.

For Orc Bot, I would therefore treat this as an architectural invariant:

                   COLLECTIBLE
                  ┌───────────────┐
snapshot DTO ────►│ plain C# code │────► view/state DTO
                  │ rules         │
                  │ presenters    │
                  │ transforms    │
                  │ adapters      │
                  └───────────────┘
                          │
                          │ data only
                          ▼
                  ┌───────────────┐
                  │ resident host │
                  │ Godot Node    │
                  │ signals       │
                  │ resources     │
                  └───────────────┘

Rather than:

collectible DLL
    └── MyPanel : Godot.Control     ← avoid

Use:

resident OrcRosterPanel : Control
              │
              ▼
reloadable IAgentRosterPresenter
              │
              ▼
AgentRosterPresentation DTO

This has a second advantage: the same plain-C# component can be tested outside Godot.

It fits the OSGi comparison very neatly

The closest mappings are now:

OSGi concept	.NET/Godot mechanism	Orc Bot concept
Bundle revision	collectible ALC + immutable DLL set	ComponentRevision
Bundle class space	ALC dependency namespace	revision-private dependencies
Import/export package	shared/private assembly policy	module requirements
Bundle resolver	AssemblyDependencyResolver + Orc resolver	compatibility resolution
Service Registry	not provided by ALC	Orc component/service registry
Declarative Services	not provided by ALC	composition reconciler
Service reference	stable contract/interface	ServiceRequirement
Bundle stop/update	ALC lifecycle	revision deactivate/swap
DS activation/deactivation	custom component lifecycle	Cordis-like reconciliation
—	EffectScope	Cordis contribution
—	fencing/evidence	Orc Bot contribution

So I would not try to recreate all of OSGi.

We should use the OSGi architecture as a specification mine.

ALC replaces the Java classloader mechanics.

Then Orc Bot needs only the OSGi ideas that are valuable for us:

revision identity
requirements / offers
binding
cardinality
scope
activation satisfaction
dynamic re-resolution

not a Java-compatible OSGi framework.

Cordis then fits one level above the ALC

This gives a much cleaner separation than we had earlier:

AssemblyLoadContext
    code exists
    dependencies resolve
    assembly identity/lifetime
          │
          ▼
Component composition
    OSGi DS-like:
      requirements
      offers
      cardinality
      activation satisfaction


    Cordis-like:
      EffectScope
      reactive dependency changes
      reversible teardown
          │
          ▼
Orc Bot authority
    permissions
    fences
    leases
    durable commands
    receipts
    quarantine

ALC answers:

Can revision R physically exist in this process?

OSGi-inspired composition answers:

Given the currently available services, may R's component become active?

Cordis-inspired lifecycle answers:

What did activation install, and how do we reverse those effects?

Orc Bot answers:

Was it authorized, what durable facts changed, and can we prove cleanup?

Those are four different questions.

Unload() is not an unload guarantee

This is another major point for Orc Bot.

Microsoft explicitly defines collectible ALC unload as cooperative. Calling Unload() merely initiates unloading. The context remains alive while external strong references exist, while plugin code is executing on thread stacks, or while strong/pinned GC handles point into it.

Even something as subtle as a JIT-kept local variable can delay collection. Microsoft's recommended unload-testing pattern uses a WeakReference and separates load/use/unload into a non-inlined method to avoid stack roots.

Godot itself follows essentially the same model. Its managed plugin loader keeps a weak reference around the load context and tries to prove that collection occurred when unloading.

So this:

alc.Unload();
return Success;

is not acceptable for Orc Bot.

We need:

request deactivate
       ↓
revoke public service registrations
       ↓
detach resident callbacks/signals
       ↓
cancel/await extension work
       ↓
dispose EffectScope
       ↓
drop all host references
       ↓
ALC.Unload()
       ↓
WeakReference still alive?
    /             \
  no               yes
  ↓                 ↓
Released       UnloadFailed
               RestartRequired

That gives Orc Bot a stronger lifecycle than ordinary plugin frameworks.

Static caches are a real unload hazard

ALC unload problems aren't limited to code we explicitly write.

Microsoft's runtime issue tracker documents cases where shared framework/static caches such as TypeDescriptor retained references to types from collectible ALCs, preventing collection. Json.NET historically triggered one of these patterns through type-converter lookup.

That means we should be suspicious of this pattern:

collectible plugin type
    ↓
passed into resident serializer/reflection/cache
    ↓
resident static cache stores Type
    ↓
plugin ALC can never collect

For example, I would avoid having a reloadable extension expose arbitrary plugin-defined DTO types to resident:

System.Text.Json options
Godot inspector reflection
property-grid systems
DI containers
logging enrichers
static event aggregators
generic metadata registries

Instead:

plugin-internal type
      ↓
convert before boundary
      ↓
shared-contract DTO
      ↓
resident system

The shared DTO's Type belongs to the resident contract assembly, so the resident serializer cannot accidentally retain the extension Assembly through its DTO type.

This is another reason the old Orc Bot model of “snapshot in, view DTO out” was strong. Its control-centre contract explicitly used immutable data both ways so payload objects didn't need to escape their context.

ALC-per-revision is preferable to one giant plugin ALC

I would make the logical unload unit explicit:

Bundle/Component revision
        =
one collectible ALC

For example:

orcbot-extension/
  comfyui/
    revision-17/
      Comfy.OrcAdapter.dll
      Comfy.OrcAdapter.deps.json
      DependencyA.dll
      DependencyB.dll

Then:

ALC comfyui:r17

loads that complete private dependency closure.

When r18 arrives:

ALC comfyui:r17
ALC comfyui:r18

can briefly coexist during staged replacement.

That is much closer to OSGi revision semantics than overwriting a loaded DLL in place.

Microsoft's sample specifically demonstrates using custom ALCs plus AssemblyDependencyResolver so separate plugins may carry conflicting dependency versions without interfering with each other.

The plugin project should also use the .NET dynamic-loading build support. Microsoft's current plugin tutorial recommends:

<EnableDynamicLoading>true</EnableDynamicLoading>

so the output is prepared as a dynamically loadable component and its required dependencies are copied appropriately.

AssemblyDependencyResolver then uses the component's .deps.json and files to resolve managed and native dependencies.

I would go a little further than Microsoft's standard sample

The common sample model is approximately:

plugin ALC
    ↓
resolver
    ↓
private dependencies
    ↓
otherwise fall back to Default

For a normal CLI app, that's fine.

For Godot/Orc Bot I want:

Resolve assembly X
      │
      ├─ X is explicitly shared Orc Bot contract
      │        ↓
      │   return resident Assembly instance
      │
      ├─ X is prohibited
      │        ↓
      │      fail
      │
      └─ otherwise
               ↓
       AssemblyDependencyResolver
               ↓
        private revision dependency

The important difference is allowlisted sharing, rather than accidental fallback.

And the resident context should be determined by:

AssemblyLoadContext.GetLoadContext(
    typeof(IOrcComponent).Assembly)

not assumed to be Default.

That matches what the older Orc Bot experiment had already learned empirically.

I would explicitly forbid GodotSharp in reloadable component dependencies

Even if we say “don't derive from GodotObject,” it's safer to make this mechanical.

A collectible extension should fail admission if its dependency graph contains:

GodotSharp
GodotSharpEditor

or if its exported component types derive from Godot types.

That turns:

“please don't accidentally do this”

into:

“the build/admission gate cannot produce such a revision.”

Resident adapters then offer narrowly typed functionality to the component.

For example, instead of a reloadable component receiving:

Control panel

give it:

AgentRosterSnapshot

and let it return:

AgentRosterPresentation

The resident Godot code owns actual Label, Tree, GraphEdit, Window, signals and resources.

The current Orc Bot first-slice architecture already keeps contracts/runtime provider-neutral and requires framework-specific projects to translate inward rather than leaking Godot/Akka/etc. types into those contracts.

So this is not fighting the architecture; it extends the same rule to dynamic extensions.

PCK and ALC should be separate lifecycles

This is important for a Godot product.

A future Orc Bot extension may contain both:

visual/resource part
    PCK


managed behaviour part
    ALC

These should not be treated as one magical reload primitive.

Think:

ComponentRevision r17
│
├── PresentationUnit
│      panel.pck
│      .tscn
│      theme
│      icons
│
└── ManagedUnit
       Presenter.dll
       private dependencies

Godot's PCK system handles resources and scenes; ALC handles managed code.

Godot's public documentation warns that already-preloaded resources may not change simply because another pack was mounted later, reinforcing that the content lifecycle has its own caching semantics.

The earlier Orc Bot experiment came to the same practical conclusion: PCK scene structure and plain-C# collectible behavior were separate layers, while resident Godot-derived C# remained process-lifetime.

That concept is worth recovering.

This leads to an OSGi-style revision transaction

I think the eventual hot-replacement transaction should be closer to this:

            desired revision r18
                     │
                     ▼
        verify manifest + hashes
                     │
                     ▼
             create ALC r18
                     │
                     ▼
        resolve module requirements
                     │
                     ▼
      load + construct components r18
          but DON'T publish yet
                     │
                     ▼
         validate requirements
                     │
                     ▼
        composition generation CAS
                     │
                     ▼
             quiesce r17
                     │
                     ▼
       revoke r17 service offers
                     │
                     ▼
        dispose r17 EffectScope
                     │
                     ▼
     publish r18 service offers
                     │
                     ▼
           activate dependents
                     │
                     ▼
              unload r17
                     │
            ┌────────┴────────┐
        collected          still alive
            │                  │
         success       RestartRequired /
                       Quarantined

Notice what this borrows:

OSGi
    immutable-ish revisions
    resolver/wiring
    service requirements


Cordis
    effect ownership
    dependency reaction


ALC
    physical assembly namespace
    dependency/version isolation
    cooperative unload


Orc Bot
    generation CAS
    admission
    receipts
    quarantine

I think this is the right synthesis.

The EffectScope becomes especially important with ALC

ALC can only unload if the rest of the process stops holding references into it.

So Cordis-like effects become more than a nice abstraction—they become a mechanism for satisfying ALC unloadability.

An extension activation should not freely do:

GlobalEvent += Handler;
Timer.Start();
registry.Add(this);
something.RegisterCallback(Method);

It should go through owner-aware registrations:

EffectScope r17
│
├── registry registration
├── event subscription
├── timer
├── cancellation registration
├── observer subscription
└── host callback proxy

Then:

Dispose EffectScope(r17)

tears down every host→plugin reference.

The old Orc Bot implementation's registry already had the right related idea: service entries belonged to a generation/owner and were revoked on reload, while callers did not retain the IBundleService; they resolved the current service per call.

That is extremely similar to an OSGi service proxy plus Cordis effect ownership.

I would keep that principle.

Direct references between extensions should also be avoided

Suppose:

Plugin A ALC
    returns PluginA.InternalThing


Plugin B ALC
    caches InternalThing

Now unloading A requires B to release an object whose type belongs to A.

This rapidly turns the ALC graph into spaghetti.

Instead:

Plugin A
   │
   │ registers IIndexService
   ▼
resident service registry
   ▲
   │ resolves current service
Plugin B

And ideally B receives a resident proxy:

IIndexServiceProxy

rather than the raw Plugin A implementation.

Then the proxy can resolve by:

service ID
owner generation
current composition generation

for each call or bounded lease.

This is another area where OSGi's indirection is useful.

Where MEF fits

I researched MEF too because it is the obvious .NET analogue.

MEF's focus is discovery and composition through exports/imports. Microsoft's own documentation distinguishes it from the older Managed Add-in Framework, which put more emphasis on isolation, loading and unloading.

For Orc Bot I would not make MEF foundational.

We already need:

immutable revision manifests
ALC ownership
shared-assembly policy
dependency satisfaction
generation fencing
EffectScope
owner-scoped registrations
durable receipts
quarantine

MEF does not eliminate that machinery.

At most, MEF could become an implementation choice for discovering parts inside one already-admitted ALC.

But even there, plain manifest-based discovery or a small shared attribute such as:

[OrcComponent("foo")]

is probably easier to audit.

The older Orc Bot experiment discovered another subtlety: reflecting custom attributes on plugin types causes the CLR to resolve the assemblies containing those attribute definitions, which means even discovery metadata can become part of the shared-assembly identity contract.

So “just use reflection attributes everywhere” is not completely free either.

Three kinds of extensions should have three deployment policies

This is the part I think should shape Orc Bot most.

Trusted, pure managed extension. A presenter, parser, graph dialect implementation, context transformer or read-only provider adapter can be a good collectible-ALC candidate if its dependencies pass unload testing.

Godot-facing extension. A surface that needs Node, Control, GraphEdit, Resource, signals, etc. should split into a resident Godot adapter plus a collectible plain-C# behavior/presenter. The Godot side is not ALC-reloadable.

Untrusted or strongly stateful extension. Agent-generated code, native-heavy tooling, frameworks with difficult global/static state, or adapters needing strong reliability boundaries should run out-of-process. Microsoft explicitly cautions that ALC is not a security boundary.

This gives us a much more useful escalation ladder than “plugin or not plugin”:

plain trusted C#
     ↓
collectible ALC


needs Godot
     ↓
resident Godot adapter
+
collectible logic


untrusted / native-heavy /
poor unloadability
     ↓
separate process
What I would recover from the previous Orc Bot experiment

The current accepted slice deliberately excludes dynamic module loading, which I still think is correct sequencing.

But when we eventually add it, I would selectively recover several ideas from the previous implementation rather than start from zero.

The pieces worth carrying forward are: resolving shared contracts from the ALC that actually owns them instead of assuming Default; keeping reloadable payloads free of Godot types; returning immutable data rather than plugin objects; never caching raw reloadable service references in resident code; owner/generation-scoped service registration; immutable/versioned payload extraction instead of overwriting files loaded by the running process; and weak-reference collection verification after unload. The historical source shows several of those rules directly.

What I would not automatically restore is the whole PluginArchi/ServiceArchi/bundle framework from that experiment. The fresh architecture should first prove that the invariants are necessary and then implement the smallest composition layer that satisfies them.

The first ALC spike I would run

Before writing a big ADR, I would make a tiny experiment with one exported Godot C# process and exactly two versions of one plain managed extension:

The exported app stays running. A resident Control displays a string supplied through a shared IOrcComponent contract.
Load revision A into a collectible custom ALC using AssemblyDependencyResolver. The ALC explicitly delegates the contract assembly to AssemblyLoadContext.GetLoadContext(typeof(IOrcComponent).Assembly).
The plugin may use its own dependency version, but it has no GodotSharp reference and exposes only shared DTOs.
Activate A through an EffectScope, render its result through the resident Godot node, then load revision B without touching A.
Atomically swap the owner/generation registration from A to B, dispose A's effects, call Unload(), and prove via WeakReference that A was collected.
Repeat A→B→C perhaps 100 times while observing managed memory, loaded assemblies, files, event handlers and Godot behavior. Include intentional leaks: retained delegate, static host cache, running task, serializer reflection of plugin-defined type and duplicated contract DLL. Each must make the test fail for the expected reason.
Run the same test from the exported Godot executable, not only dotnet test or the editor, because the exported/player load-context behavior is exactly the part that differs from editor reload.

That spike would tell us far more than immediately implementing a general module framework.

Revised recommendation

I would now phrase the future Orc Bot architecture this way:

┌────────────────────────────────────────────┐
│ Orc Bot durable authority                  │
│ Akka.NET • SQLite • permissions • fences   │
└──────────────────────┬─────────────────────┘
                       │ desired composition
                       ▼
┌────────────────────────────────────────────┐
│ Orc Component Runtime                      │
│                                            │
│ OSGi-inspired                              │
│   requirements / offers / revisions        │
│   scopes / cardinality / binding           │
│                                            │
│ Cordis-inspired                            │
│   EffectScope / reactive reconciliation    │
│                                            │
│ Orc Bot-specific                           │
│   generation CAS / receipts / quarantine   │
└──────────────────────┬─────────────────────┘
                       │ physical code revision
                       ▼
┌────────────────────────────────────────────┐
│ .NET AssemblyLoadContext                   │
│ AssemblyDependencyResolver                 │
│ shared-contract policy                     │
│ collectible revision                       │
└──────────────────────┬─────────────────────┘
                       │ data-only boundary
                       ▼
┌────────────────────────────────────────────┐
│ Resident Godot C# host                     │
│ Nodes • Resources • GraphEdit • Windows    │
└────────────────────────────────────────────┘

The strongest new conclusion from this research is that Godot's own ALC implementation validates the basic architecture we had stumbled onto earlier: shared core assemblies must have one identity, project/runtime code has a resident role, and collectible contexts are a specialized code-loading mechanism rather than a general replacement for Godot's script system.

For Orc Bot, that means the future dynamic composition system should be designed around Godot rather than trying to make Godot-managed classes themselves dynamically unloadable.

The next useful research step would be to go one level deeper into Godot's PluginLoadContext, ScriptManagerBridge/GCHandle lifetime, and the precise exported C# assembly-loading path, and from that derive a concrete OrcAssemblyLoadContext design plus an unload test matrix. That would tell us exactly which boundary can be mechanically enforced in the current Godot 4.7.x C# host.