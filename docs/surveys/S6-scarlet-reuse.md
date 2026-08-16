# S6 — reuse from `scarlet-projects`

- Date: 2026-08-16
- Scope: the packages available in `<workspace>/packages/nuget`, checked against the public source in `<workspace>/scarlet-projects`.
- Decision frame: RFC-0001's W5 provider registry, W7 application composition, W8 daemon, W9 CLI, and W12 Godot host; ADR-0001's one application surface, ADR-0002's authority boundary, ADR-0003's independent semantic plane, and ADR-0008's separate runtime process.

Citation convention: every evidence block gives the full source path for its first file; subsequent bare filenames in that block are siblings of that fully qualified file unless they introduce another full path.  Package-version claims cite the actual `.nupkg` filename in the local feed.

## Result

Scarlet already has a usable plugin substrate and a small, suitable in-memory implementation registry.  It does **not** already have Orc Bot's daemon/client protocol, durable event subscription, `{ generation, sequence }` cursor, snapshot/journal recovery, or SQLite event store.  Reuse the former now; keep Orc Bot's protocol and event vocabulary its own work.

The local-feed rule matters: package IDs consumed here must begin `GiantCroissant.`.  Several older Unify packages in the feed and source do not, so they are not eligible until repacked/renamed even where their target framework would otherwise work.

## 1. PluginArchi

**Local feed.** `GiantCroissant.PluginArchi.Extensibility.Abstractions` **0.1.5**, `GiantCroissant.PluginArchi.Extensibility.Hosting.Abstractions` **0.1.5**, and `GiantCroissant.PluginArchi.Extensibility.Hosting` **0.1.5** are present.  The exact feed files are `<workspace>/packages/nuget/GiantCroissant.PluginArchi.Extensibility.Abstractions.0.1.5.nupkg`, `<workspace>/packages/nuget/GiantCroissant.PluginArchi.Extensibility.Hosting.Abstractions.0.1.5.nupkg`, and `<workspace>/packages/nuget/GiantCroissant.PluginArchi.Extensibility.Hosting.0.1.5.nupkg`.

**What it actually does.** `[Plugin("id")]` supplies stable metadata; `IPlugin` owns an `IPluginDescriptor`, and `IPluginLifecycle` supplies async initialise/shutdown hooks.  `ReflectionPluginDiscovery` finds types with that attribute which implement `IPlugin`; `PluginHostBuilder` can scan a directory or explicitly create a named isolated group, and `PluginHost` activates, orders, registers, and invokes lifecycle plugins.  Evidence: `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Abstractions/PluginAttribute.cs`, `IPlugin.cs`, `IPluginLifecycle.cs`, `IPluginDiscovery.cs`, `IPluginHost.cs`, `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Hosting/ReflectionPluginDiscovery.cs`, `PluginHostBuilder.cs`, and `PluginHost.cs`.

**Collectible hosting and unload probe.** `IsolatedLoader` uses a collectible `AssemblyLoadContext`; `PluginLoadContext` and `HierarchicalPluginLoadContext` are also explicitly collectible.  `IPluginHost.AddGroupAsync`/`RemoveGroupAsync` manage isolated groups, while the additive `IPluginHostDiagnostics.RemoveGroupWithDiagnosticsAsync` returns `PluginUnloadResult`, whose weak-only `IsCollected(forceGc)` performs one bounded collection probe.  This is real behaviour rather than an advertised interface: the host implementation captures the group's `IsolatedLoader.Context` only to construct the weak probe, and tests cover both a collectible group and a deliberately retained type reference.  Evidence: `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Hosting/IsolatedLoader.cs`, `PluginLoadContext.cs`, `PluginHost.cs`, `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Abstractions/IPluginHostDiagnostics.cs`, `PluginUnloadResult.cs`, and `<workspace>/scarlet-projects/plugin-archi/dotnet/tests/PluginArchi.Extensibility.Hosting.Tests/PluginHostDiagnosticsTests.cs`.

**What it replaces.** It replaces the generic plugin-host work implicit in RFC-0001's layout and needed by W5/W7: assembly discovery, load contexts, lifecycle ordering, plugin lookup, and the unload diagnostic.  It does **not** replace the Orc Bot application surface, candidate authority, or plugin policy.

**Cost.** The abstraction package targets `net8.0;netstandard2.1`; hosting abstractions target `netstandard2.1`; the concrete host targets `net8.0`, so all are usable by the `net8.0` Godot host.  Concrete hosting brings the two prior PluginArchi packages plus `Microsoft.Extensions.DependencyInjection` and `Microsoft.Extensions.Hosting.Abstractions` 9.0.0; source generation is optional for reflection discovery.  The generator package `GiantCroissant.PluginArchi.SourceGenerators` 0.1.5 exists, but it is an analyzer and the builder hard-wires `ReflectionPluginDiscovery`; `GeneratedPluginDiscovery` exists but the public builder has no discovery-selection method, so do not make it a v0 dependency.  Evidence: `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Abstractions/PluginArchi.Extensibility.Abstractions.csproj`, `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Hosting.Abstractions/PluginArchi.Extensibility.Hosting.Abstractions.csproj`, `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Hosting/PluginArchi.Extensibility.Hosting.csproj`, `PluginHostBuilder.cs`, `IPluginHostBuilder.cs`, `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.SourceGenerators/PluginDescriptorGenerator.cs`, and `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Hosting/GeneratedPluginDiscovery.cs`.

**OrcBot.Extensibility decision.** Do **not** delete `OrcBot.Extensibility`; make it a thin Orc policy profile over PluginArchi.  Orc Bot's `IOrcPluginContext` deliberately exposes only an absolute per-plugin data directory and a structured log sink, whereas PluginArchi's `IPluginContext` exposes an `IServiceProvider`; keeping the Orc contract is what stops a plugin from treating the host as an ambient service locator and preserves ADR-0001/0002 authority policy.  Retain `[OrcPlugin]` and `IOrcPlugin`, require a PluginArchi-facing adapter (or both attributes on the adapter type) to implement `IPlugin`/`IPluginLifecycle`, and translate the restricted context at that edge; PluginArchi's sealed `[Plugin]` attribute cannot be derived from.  Evidence: `<workspace>/agent-projects/orc-bot/project/contracts/OrcBot.Extensibility/OrcPlugin.cs`, `<workspace>/scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Abstractions/PluginAttribute.cs`, `IPluginContext.cs`, `IPlugin.cs`, and `IPluginLifecycle.cs`.

**VERDICT: adopt-now.** It already solves the difficult, error-prone host mechanics, while a very small Orc-specific profile keeps capability from becoming authority.

## 2. RegistryArchi

**Local feed.** `GiantCroissant.RegistryArchi.Contracts` **0.1.1**, `GiantCroissant.RegistryArchi.Core` **0.1.1**, and the optional analyzer `GiantCroissant.RegistryArchi.SourceGen` **0.1.1** are present: `<workspace>/packages/nuget/GiantCroissant.RegistryArchi.Contracts.0.1.1.nupkg`, `GiantCroissant.RegistryArchi.Core.0.1.1.nupkg`, and `GiantCroissant.RegistryArchi.SourceGen.0.1.1.nupkg`.

**What it actually does.** `IRegistry` holds instances keyed by contract type, supports priority/tag/metadata/owner registration, resolves `First`, `Latest`, highest/lowest priority, or exactly one instance, and can remove all registrations for an owner.  `Registry` is an in-memory, locked/concurrent implementation; `RegisterOwned` returns an idempotent `IDisposable` removal handle.  This is a provider/capability registry, not DI and not durable state.  Evidence: `<workspace>/scarlet-projects/registry-archi/dotnet/RegistryArchi.Contracts/IRegistry.cs`, `RegistryRegistration.cs`, `SelectionMode.cs`, and `<workspace>/scarlet-projects/registry-archi/dotnet/RegistryArchi.Core/Registry.cs`.

**What it replaces.** W5's provider registry and the in-memory capability selection portion of W7.  Stamp plugin-owned registrations with the PluginArchi/Orc plugin ID and remove them on unload; do not use it as the repository for tasks, candidates, receipts, or events (W2 remains SQLite).

**Cost.** Contracts and Core both target `netstandard2.0`; Core depends only on Contracts and works under the Godot `net8.0` host.  No source generator is required; `RegistryArchi.SourceGen` merely produces attribute-driven registration extension methods.  Evidence: `<workspace>/scarlet-projects/registry-archi/dotnet/RegistryArchi.Contracts/RegistryArchi.Contracts.csproj`, `<workspace>/scarlet-projects/registry-archi/dotnet/RegistryArchi.Core/RegistryArchi.Core.csproj`, and `<workspace>/scarlet-projects/registry-archi/dotnet/RegistryArchi.SourceGen/RegistryExportGenerator.cs`.

**VERDICT: adopt-now.** It is the smallest verified match for a dynamic provider registry and its owner cleanup fits collectible plugin groups.

## 3. DependencyArchi

**Local feed.** `GiantCroissant.DependencyArchi.Abstractions` **0.1.1**, `GiantCroissant.DependencyArchi.MicrosoftExtensions` **0.1.1**, and optional `GiantCroissant.DependencyArchi.SourceGenerators` **0.1.1** are present: `<workspace>/packages/nuget/GiantCroissant.DependencyArchi.Abstractions.0.1.1.nupkg`, `GiantCroissant.DependencyArchi.MicrosoftExtensions.0.1.1.nupkg`, and `GiantCroissant.DependencyArchi.SourceGenerators.0.1.1.nupkg`.

**What it actually does.** A module implements `IDependencyModule<TBuilder>.Register`; `DependencyModuleOrderer` topologically orders module registrations and rejects cycles or missing dependencies.  The Microsoft extension invokes those ordered modules against an `IServiceCollection`, and the optional scope-activation machinery builds and tears down a hierarchy of DI scopes.  Evidence: `<workspace>/scarlet-projects/dependency-archi/dotnet/src/DependencyArchi.Abstractions/IDependencyModule.cs`, `DependencyModuleOrderer.cs`, `DependencyScopeActivationRunner.cs`, and `<workspace>/scarlet-projects/dependency-archi/dotnet/src/DependencyArchi.MicrosoftExtensions/DependencyModuleServiceCollectionExtensions.cs`.

**What it replaces.** **Nothing in the first RFC slice.** It could later standardise startup module order, but PluginArchi already offers `PluginHostBuilder.ConfigureServices` before its provider is built; no RFC item calls for dependency-module metadata or a nested DI-scope topology.

**Cost.** The runtime packages target `netstandard2.0`, and the Microsoft adapter adds `Microsoft.Extensions.DependencyInjection` 8.0.0 plus Abstractions.  They work under Godot `net8.0`; the generator is optional but emits assembly manifests, static registration lists, and parameterless module construction, which is an unnecessary build-time convention for v0.  Evidence: `<workspace>/scarlet-projects/dependency-archi/dotnet/src/DependencyArchi.Abstractions/DependencyArchi.Abstractions.csproj`, `<workspace>/scarlet-projects/dependency-archi/dotnet/src/DependencyArchi.MicrosoftExtensions/DependencyArchi.MicrosoftExtensions.csproj`, and `<workspace>/scarlet-projects/dependency-archi/dotnet/src/DependencyArchi.SourceGenerators/DependencyArchiSourceGenerator.cs`.

**VERDICT: do-not-adopt.** It is a valid module-composition framework, but v0 has no requirement it uniquely satisfies and it would layer another lifecycle model over PluginArchi's host.

## 4. ServiceArchi

**Local feed.** `GiantCroissant.ServiceArchi.Contracts` **0.1.2**, `GiantCroissant.ServiceArchi.Core` **0.1.2**, and `GiantCroissant.ServiceArchi.SourceGen` **0.1.2** are present: `<workspace>/packages/nuget/GiantCroissant.ServiceArchi.Contracts.0.1.2.nupkg`, `GiantCroissant.ServiceArchi.Core.0.1.2.nupkg`, and `GiantCroissant.ServiceArchi.SourceGen.0.1.2.nupkg`.

**What it actually does.** `ServiceRegistry` is a facade over RegistryArchi: it registers/retrieves typed instances, delegates priority/tag/owner behaviour, and maps RegistryArchi failures into `ServiceResolutionException`.  Its attributes and generator create registration/proxy boilerplate; they do not create a Microsoft DI container or a daemon service boundary.  Evidence: `<workspace>/scarlet-projects/service-archi/dotnet/ServiceArchi.Contracts/IRegistry.cs`, `IServiceRegistrationOwner.cs`, `<workspace>/scarlet-projects/service-archi/dotnet/ServiceArchi.Core/ServiceRegistry.cs`, and `<workspace>/scarlet-projects/service-archi/dotnet/ServiceArchi.SourceGen/RegistrationGenerator.cs`.

**What it replaces.** **Nothing.** RegistryArchi directly supplies the one needed mechanism without another naming layer.

**Cost.** It targets `netstandard2.0`, so Godot compatibility is fine, but Core pulls ServiceArchi Contracts and RegistryArchi Core; generators are optional analyzers.  Evidence: `<workspace>/scarlet-projects/service-archi/dotnet/ServiceArchi.Contracts/ServiceArchi.Contracts.csproj`, `<workspace>/scarlet-projects/service-archi/dotnet/ServiceArchi.Core/ServiceArchi.Core.csproj`, and `<workspace>/scarlet-projects/service-archi/dotnet/ServiceArchi.SourceGen/ServiceArchi.SourceGen.csproj`.

**VERDICT: do-not-adopt.** It duplicates RegistryArchi's mechanism and the generated service/proxy conventions add no value to Orc Bot's explicit application ports.

## 5. Crosscut Foundation — configuration

**Local feed.** All are **0.3.1**: `GiantCroissant.CrosscutFoundation.Config.Contracts`, `.Core`, `.Env`, `.Json`, and `.CommandLine`; corresponding files are under `<workspace>/packages/nuget/GiantCroissant.CrosscutFoundation.Config.*.0.3.1.nupkg`.

**What it actually does.** `ConfigService` orders `IConfigurationSourceProvider`s by priority and builds a Microsoft `IConfigurationRoot`; it exposes get/section/bind/reload operations.  The shipped source providers add JSON at priority 50, environment variables at 90, and command-line arguments at 100.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Config.Contracts/ConfigContracts.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Config.Core/ConfigService.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Config.Json/JsonConfigurationSourceProvider.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Config.Env/EnvConfigurationSourceProvider.cs`, and `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Config.CommandLine/CommandLineConfigurationSourceProvider.cs`.

**What it replaces.** Configuration composition in W8/W9 and the host-side configuration portion of W12; it does not replace application commands, local IPC, or profile authorisation.

**Cost.** The packages target `netstandard2.1` and work under Godot `net8.0`.  Core adds Microsoft Configuration/Binder and `System.Text.Json`; source-specific packages add their Microsoft provider, and no source generator is required.  Do not call the JSON provider's parameterless constructor: it deliberately uses `Environment.CurrentDirectory/appsettings.json`, contrary to the repository's absolute-path rule; give it the runtime's explicit absolute configuration path instead.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Config.Contracts/Config.Contracts.csproj`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Config.Core/Config.Core.csproj`, `Config.Env.csproj`, `Config.Json.csproj`, `Config.CommandLine.csproj`, and `JsonConfigurationSourceProvider.cs`.

**VERDICT: adopt-now.** It is a thin, usable wrapper over established configuration primitives, provided the daemon owns absolute config paths and treats reload as a controlled input.

## 6. Crosscut Foundation — logging

**Local feed.** `GiantCroissant.CrosscutFoundation.Logging.Contracts`, `.Core`, `.Console`, and `.Godot` are all **0.3.1**; the Godot package is `<workspace>/packages/nuget/GiantCroissant.CrosscutFoundation.Logging.Godot.0.3.1.nupkg`.

**What it actually does.** `LoggingService` creates a Microsoft `ILoggerFactory` from ordered configurators; `ConsoleLoggingBuilderConfigurator` simply calls `AddConsole`; `GodotLoggerProvider` maps Microsoft log levels to `GD.Print`, `GD.PushWarning`, and `GD.PushError`.  `LogMessageFormatter` can preserve structured state/scopes in text for the Godot console, but no shipped component establishes Orc-specific correlation or guarantees diagnostic output stays off CLI stdout.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Logging.Contracts/LoggingContracts.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Logging.Core/LoggingService.cs`, `LogMessageFormatter.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Logging.Console/ConsoleLoggingBuilderConfigurator.cs`, and `<workspace>/scarlet-projects/crosscut-foundation/godot/CrosscutFoundation.Logging.Godot/GodotLoggerProvider.cs`.

**What it replaces.** **Nothing.** W9 must make stdout a machine-only result and stderr diagnostics; this wrapper's only console configurator offers no sink/stream policy.  Use Microsoft.Extensions.Logging directly with an Orc-controlled stderr/JSON sink and scopes for task/attempt/correlation IDs.

**Cost.** Contracts/Core/Console target `netstandard2.1` and Godot targets `net8.0`; Core adds Microsoft Logging 8.0 and related DI/diagnostics packages; no generator is needed.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Logging.Contracts/Logging.Contracts.csproj`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Logging.Core/Logging.Core.csproj`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Logging.Console/Logging.Console.csproj`, and `<workspace>/scarlet-projects/crosscut-foundation/godot/CrosscutFoundation.Logging.Godot/CrosscutFoundation.Logging.Godot.csproj`.

**VERDICT: do-not-adopt.** Its abstractions are thinner than the standard library but do not cover Orc Bot's stdout/stderr and correlation invariants.

## 7. Crosscut Foundation — diagnostics

**Local feed.** `GiantCroissant.CrosscutFoundation.Diagnostics.Contracts`, `.Core`, `.Console`, `.OpenTelemetry`, `.Godot`, and `.Generators` are **0.3.1**; e.g. `<workspace>/packages/nuget/GiantCroissant.CrosscutFoundation.Diagnostics.OpenTelemetry.0.3.1.nupkg`.

**What it actually does.** The contracts define a tracer/span API, metrics, error reporter, and registered async health checks.  `DiagnosticsService` provides no-op defaults and records which optional facilities were actually supplied; the OpenTelemetry package adapts the API to `ActivitySource`/`Meter`, while `GodotErrorReporter` routes errors to Godot output.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Diagnostics.Contracts/DiagnosticsContracts.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Diagnostics.Core/DiagnosticsService.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Diagnostics.OpenTelemetry/OpenTelemetryTracer.cs`, `OpenTelemetryMetrics.cs`, and `<workspace>/scarlet-projects/crosscut-foundation/godot/CrosscutFoundation.Diagnostics.Godot/GodotErrorReporter.cs`.

**What it replaces.** Later operational diagnostics around W8/W12 only; it does not replace typed semantic completion (W5), durable event evidence (W2), or the W8 cursor.  Its Console implementation emits human text and must not be mistaken for an attempt semantic channel.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Diagnostics.Console/ConsoleTracerAndMetrics.cs`.

**Cost.** Contracts/Core/Console/OpenTelemetry target `netstandard2.1`; Godot targets `net8.0`, all compatible with the Godot host.  Contracts/Core require no generator; OpenTelemetry adds ServiceArchi Contracts, OpenTelemetry 1.7, and Microsoft configuration/logging/DI dependencies; the generator is optional.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Diagnostics.Contracts/Diagnostics.Contracts.csproj`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Diagnostics.Core/Diagnostics.Core.csproj`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Diagnostics.OpenTelemetry/Diagnostics.OpenTelemetry.csproj`, and `<workspace>/scarlet-projects/crosscut-foundation/godot/CrosscutFoundation.Diagnostics.Godot/CrosscutFoundation.Diagnostics.Godot.csproj`.

**VERDICT: adopt-later.** The health/tracing surface is useful once a running daemon exists, but it is not a prerequisite for the authoritative W1–W9 loop and the OpenTelemetry adapter has a disproportionate fan-out.

## 8. Crosscut Foundation — hosting, messaging, and persistence

**Local feed.** `GiantCroissant.CrosscutFoundation.Hosting.Contracts`, `.Core`, `.Microsoft`, `Messaging.Contracts`, `Messaging.MessagePipe`, and `Persistence.Abstractions` are **0.3.1** (for example, `<workspace>/packages/nuget/GiantCroissant.CrosscutFoundation.Hosting.Microsoft.0.3.1.nupkg` and `<workspace>/packages/nuget/GiantCroissant.CrosscutFoundation.Persistence.Abstractions.0.3.1.nupkg`).

**What they actually do.** Hosting starts ordered `IHostedComponent`s and rolls already-started components back on failure; its Microsoft bridge only exposes that order through `IHostedService`.  Messaging is a process-local `Publish<T>`/`Subscribe<T>` bus backed by a privately owned MessagePipe service provider.  Persistence contributes only a generic append/load/exists interface keyed by stream and a one-string `EventStreamId`; it has no shipped storage implementation in this package.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Hosting.Contracts/HostingContracts.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Hosting.Core/HostingService.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Hosting.Microsoft/CrosscutRegistryHostedService.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Messaging.Contracts/IMessageBus.cs`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Messaging.MessagePipe/MessagePipeMessageBus.cs`, and `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Persistence.Contracts/IAppendOnlyLogStore.cs`.

**ADR-0008 check.** None is a daemon/client boundary.  There is no listener/socket/pipe, protocol version, client session, snapshot exchange, backpressure, reconnect, mutation journal, idempotency key, or uncertain-outcome model in these APIs.  None represents an event cursor, and the messaging contract has neither sequence nor replay, while `IAppendOnlyLogStore` has no cursor/generation parameter.  The W8 local protocol and W1 `{ generation, sequence }` cursor therefore remain Orc Bot work.  Evidence: `IMessageBus.cs`, `IAppendOnlyLogStore.cs`, `EventStreamId.cs`, and the W8 requirements in `<workspace>/agent-projects/orc-bot/docs/rfc/0001-bootstrap-slice.md`.

**What they replace.** **Nothing.** Hosting could be a future internal implementation detail of `orc serve`, but W8's actual boundary cannot be delegated to it; MessagePipe is unsuitable as operational truth; Persistence.Abstractions cannot replace W2's SQLite schema/repository/migrations.

**Cost.** These packages target `netstandard2.1` and are Godot-compatible.  Hosting.Microsoft pulls Microsoft Hosting/DI plus its ServiceArchi bridge; MessagePipe pulls MessagePipe and DI; persistence pulls MessagePack and TimeDete primitives.  No source generator is necessary.  Evidence: `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Hosting.Microsoft/Hosting.Microsoft.csproj`, `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Messaging.MessagePipe/Messaging.MessagePipe.csproj`, and `<workspace>/scarlet-projects/crosscut-foundation/dotnet/src/Persistence.Contracts/Persistence.Contracts.csproj`.

**VERDICT: do-not-adopt.** They contain useful generic mechanics but none meets the durable, reconnectable authority and cursor requirements of ADR-0008.

## 9. UnifyEcs

**Local feed.** `GiantCroissant.UnifyEcs.Core` **0.1.14** and `GiantCroissant.UnifyEcs.Runtime.Arch` **0.1.14** are present: `<workspace>/packages/nuget/GiantCroissant.UnifyEcs.Core.0.1.14.nupkg` and `<workspace>/packages/nuget/GiantCroissant.UnifyEcs.Runtime.Arch.0.1.14.nupkg`.  The source has Attributes and Generators projects, but no matching prefixed package was found in this feed.

**What it actually does.** Core supplies an `IWorld` with entity/component operations, optional `IWorldQuery`, command buffers, and a static backend factory.  The Arch runtime implements that contract atop Arch 2.1.0 and supports component-filter queries; its module initializer registers the Arch factory.  Evidence: `<workspace>/scarlet-projects/unify-ecs/dotnet/src/UnifyEcs.Core/IWorld.cs`, `IWorldQuery.cs`, `ICommandBuffer.cs`, `WorldFactory.cs`, `<workspace>/scarlet-projects/unify-ecs/dotnet/src/UnifyEcs.Runtime.Arch/ArchWorld.cs`, and `ArchBackendRegistration.cs`.

**What it replaces.** A later ECS projection only — explicitly out of scope in RFC-0001.  It does not model durable Orc Bot truth, source allocations, candidate authority, or events.

**Cost.** Core targets `netstandard2.0`; Arch targets `netstandard2.1` and adds only Core plus Arch 2.1.0.  Both can be referenced by a Godot `net8.0` host, and the basic world/query API does not require source generators.  Evidence: `<workspace>/scarlet-projects/unify-ecs/dotnet/src/UnifyEcs.Core/UnifyEcs.Core.csproj`, `<workspace>/scarlet-projects/unify-ecs/dotnet/src/UnifyEcs.Runtime.Arch/UnifyEcs.Runtime.Arch.csproj`, and `<workspace>/scarlet-projects/unify-ecs/dotnet/src/UnifyEcs.Generators/UnifyEcs.Generators.csproj`.

**VERDICT: adopt-later.** It is a concrete, compatible starting point when a Godot read-model projection is demanded, but RFC-0001 correctly excludes it from the bootstrap authority path.

## 10. GameFoundation

**Local feed.** Resource and SceneFlow Contract/Proxy/Godot packages are all **0.2.0**, including `GiantCroissant.GameFoundation.Resource.Contracts`, `GiantCroissant.GameFoundation.Resource.Godot`, `GiantCroissant.GameFoundation.SceneFlow.Contracts`, and `GiantCroissant.GameFoundation.SceneFlow.Godot`; see `<workspace>/packages/nuget/GiantCroissant.GameFoundation.Resource.Contracts.0.2.0.nupkg` and `<workspace>/packages/nuget/GiantCroissant.GameFoundation.SceneFlow.Contracts.0.2.0.nupkg`.

**What it actually does.** Resource defines engine-neutral acquire/release leases by logical resource ID; SceneFlow opens/closes Godot main-scene sessions with optional parent sessions.  Evidence: `<workspace>/scarlet-projects/game-foundation/dotnet/GameFoundation.Resource.Contracts/IResourceService.cs`, `ResourceRequest.cs`, `<workspace>/scarlet-projects/game-foundation/dotnet/GameFoundation.SceneFlow.Contracts/ISceneFlowService.cs`, and `SceneRequest.cs`.

**What it replaces.** **Nothing.** W12 validates Orc Bot's Godot client; it does not need a game resource-leasing or scene-session architecture.

**Cost.** Contracts/Proxies target `netstandard2.1`; Godot implementations target `net8.0` with GodotSharp.  Proxies also bring ServiceArchi SourceGen, so they require generators.  Evidence: `<workspace>/scarlet-projects/game-foundation/dotnet/GameFoundation.Resource.Contracts/GameFoundation.Resource.Contracts.csproj`, `GameFoundation.Resource.Proxy.csproj`, `<workspace>/scarlet-projects/game-foundation/godot/GameFoundation.Resource.Godot/GameFoundation.Resource.Godot.csproj`, and `<workspace>/scarlet-projects/game-foundation/godot/GameFoundation.SceneFlow.Godot/GameFoundation.SceneFlow.Godot.csproj`.

**VERDICT: do-not-adopt.** Its engine contracts solve a different problem and their ServiceArchi coupling is unnecessary for a thin Orc client.

## 11. PlateShared source generators

**Local feed.** The feed has `GiantCroissant.PlateShared.SCG.DI.ConstructorInjection` **0.1.10** plus its attributes package and several AutoProperties/AutoToString/DisposePattern generators at **0.1.10**; for example `<workspace>/packages/nuget/GiantCroissant.PlateShared.SCG.DI.ConstructorInjection.0.1.10.nupkg`.

**What it actually does.** The constructor generator responds to `[ConstructorInjection]` and `[ResolveInConstructor]`; the general generators create properties or other boilerplate from field attributes.  They do not register services, load plugins, or own runtime lifecycles.  Evidence: `<workspace>/scarlet-projects/plate-shared/dotnet/source-generators/DI.ConstructorInjection.Set/DI.ConstructorInjection.Attributes/ConstructorInjectionAttribute.cs`, `ResolveInConstructorAttribute.cs`, and `<workspace>/scarlet-projects/plate-shared/dotnet/source-generators/General.AutoProperties.Set/General.AutoProperties.Attributes/AutoPropertyAttribute.cs`.

**What it replaces.** **Nothing.** RFC-0001 asks for explicit vocabulary, not generated incidental boilerplate.

**Cost.** Attribute packages target `netstandard2.0`; the generators are Roslyn analyzer packages and therefore increase build-time/tooling coupling rather than runtime compatibility.  Evidence: `<workspace>/scarlet-projects/plate-shared/dotnet/source-generators/DI.ConstructorInjection.Set/DI.ConstructorInjection.Attributes/DI.ConstructorInjection.Attributes.csproj` and `<workspace>/scarlet-projects/plate-shared/dotnet/source-generators/DI.ConstructorInjection.Set/DI.ConstructorInjection/DI.ConstructorInjection.csproj`.

**VERDICT: do-not-adopt.** They require generators to remove code that should remain obvious in a small, policy-heavy bootstrap.

## 12. UnifySerialization and UnifyStorage

**Local feed.** The feed contains unprefixed `UnifySerialization.Abstractions`, `.Generators`, and `.MessagePack.Runtime` at **0.3.0** but no `GiantCroissant.UnifySerialization.*` package; it contains no UnifyStorage package.  Their source package IDs are likewise unprefixed, so neither family meets the local-feed prefix rule.

**What they actually do.** UnifySerialization marks models for a source generator and has a MessagePack `typeId + payload` envelope codec; it is serialization, not a protocol/session system.  UnifyStorage declares generic document/key-value/event-store interfaces, including an event stream that begins at a scalar `fromVersion`; the source does not define an Orc-compatible two-part cursor.  Evidence: `<workspace>/scarlet-projects/unify-serialization/dotnet/src/UnifySerialization.Abstractions/Attributes.cs`, `IUnifySerializer.cs`, `<workspace>/scarlet-projects/unify-serialization/dotnet/src/UnifySerialization.MessagePack.Runtime/MessagePackEnvelopeCodec.cs`, `<workspace>/scarlet-projects/unify-storage/dotnet/src/UnifyStorage.Abstractions/IEventStore.cs`, and `UnifyStorage.Abstractions.csproj`.

**What they replace.** **Nothing.** Neither solves W8 local IPC, snapshot/reconnect, journal recovery, or W1's `{ generation, sequence }` cursor; W2 still needs its explicit SQLite implementation.

**Cost.** Serialization's abstractions/generator target `netstandard2.0`; its runtime project references MessagePack and Crosscut persistence, while some Storage runtimes target `net8.0` and pull database/native dependencies.  Generator use is central to UnifySerialization's model path; in any event these unprefixed packages cannot be consumed.  Evidence: `<workspace>/scarlet-projects/unify-serialization/dotnet/src/UnifySerialization.Abstractions/UnifySerialization.Abstractions.csproj`, `UnifySerialization.Generators.csproj`, `UnifySerialization.MessagePack.Runtime.csproj`, `<workspace>/scarlet-projects/unify-storage/dotnet/src/UnifyStorage.Abstractions/UnifyStorage.Abstractions.csproj`, and `<workspace>/scarlet-projects/unify-storage/dotnet/src/UnifyStorage.Runtime.LiteDb/UnifyStorage.Runtime.LiteDb.csproj`.

**VERDICT: do-not-adopt.** The packages are ineligible under the naming rule and, independently, their APIs stop well short of Orc Bot's durable daemon protocol.

## 13. UnifyCell, UnifyTopology, UnifyGeometry, and UnifyMaths

**Local feed.** Available IDs are unprefixed: `UnifyCell.Abstractions`/`.Core` **0.1.1**, `UnifyTopology.*` **0.1.2**, `UnifyGeometry.*` **0.1.4**, and `UnifyMaths*` up to **0.1.6**.  None is `GiantCroissant.*`, so none is consumable under the organisation rule.

**What they actually do.** UnifyCell models grids/tessellations; UnifyTopology models in-memory graph nodes/edges and topology algorithms; Geometry/Maths support spatial primitives and numerical work.  They provide neither a service registry, plugin host, process boundary, nor event cursor.  Evidence: `<workspace>/scarlet-projects/unify-cell/dotnet/src/UnifyCell.Abstractions/ITessellation.cs`, `ICellCoordinateSpace.cs`, `<workspace>/scarlet-projects/unify-topology/dotnet/src/UnifyTopology.Graph.Abstractions/ITopologyGraph.cs`, `<workspace>/scarlet-projects/unify-geometry/dotnet/src/UnifyGeometry.Primitives/UnifyGeometry.Primitives.csproj`, and `<workspace>/scarlet-projects/unify-maths/dotnet/src/UnifyMaths/UnifyMaths.csproj`.

**What they replace.** **Nothing.** RFC-0001 excludes graph engineering and ECS projection work from the bootstrap, and the Godot validation host does not need geometry or maths libraries.

**Cost.** These packages are generally `netstandard2.1`-compatible, but many have generator or geometry/native dependency fan-out; that technical compatibility does not override the package-ID rule.  Evidence: `<workspace>/scarlet-projects/unify-cell/dotnet/src/UnifyCell.Abstractions/UnifyCell.Abstractions.csproj`, `<workspace>/scarlet-projects/unify-topology/dotnet/src/UnifyTopology.Abstractions/UnifyTopology.Abstractions.csproj`, `UnifyGeometry.Primitives.csproj`, and `UnifyMaths.csproj`.

**VERDICT: do-not-adopt.** They are outside the v0 problem and ineligible from this local feed.

## 14. UnifyBuild

**Local feed.** `GiantCroissant.UnifyBuild.Tool` **0.1.28-1** and `GiantCroissant.UnifyBuild.Nuke` **0.1.28-1** are present; Orc Bot already pins the Tool package in `<workspace>/agent-projects/orc-bot/.config/dotnet-tools.json`.

**What it actually does.** It is the build tool driving the existing `Compile`, packaging, publishing, and Godot export targets; it is not a runtime component.  Evidence: `<workspace>/agent-projects/orc-bot/Taskfile.yml` and `<workspace>/scarlet-projects/unify-build/dotnet/src/UnifyBuild.Tool/UnifyBuild.Tool.csproj`.

**What it replaces.** Already adopted for the build/artifact layout required by ADR-0005; it replaces no W1–W12 implementation work.

**Cost.** The Tool targets `net8.0`; it is a development-time dotnet tool, so it is not loaded by the Godot host and needs no source generator.

**VERDICT: adopt-now (already adopted).** Keep the existing pinned version and do not make it part of Orc Bot's runtime dependency graph.

## Recommended adoption order

1. **W1/W7 foundation:** add PluginArchi Abstractions + Hosting Abstractions + Hosting 0.1.5, retaining `OrcBot.Extensibility` as the restricted profile/adapter rather than deleting it.  Add RegistryArchi Contracts + Core 0.1.1 for provider/capability selection and plugin-owned cleanup.
2. **W7/W8 host composition:** add Crosscut Config Contracts/Core/Env/Json/CommandLine 0.3.1; construct the JSON provider with an absolute daemon-controlled path and do not permit a plugin to alter the active configuration root.
3. **W8 explicitly remains Orc Bot work:** define the versioned local protocol and `{ generation, sequence }` record in Contracts, then implement snapshot-plus-idempotent-journal recovery over W2 SQLite.  No surveyed package is a substitute.
4. **After the dogfood loop:** optionally add Crosscut Diagnostics Contracts/Core, and only add the OpenTelemetry/Godot adapters when their operational consumers exist.
5. **Only when the operator UI needs a derived runtime projection:** evaluate UnifyEcs Core + Runtime.Arch 0.1.14 behind a projection boundary.  Keep it read-model-only and never let it become operational truth.

The adopt-now set is therefore: **PluginArchi (the three runtime packages), RegistryArchi Contracts/Core, CrosscutFoundation Config Contracts/Core/Env/Json/CommandLine, and the already-present UnifyBuild tool.**

## Verification limits

This survey read public source and inspected the local feed's package IDs, versions, target assets, and dependency manifests.  It did not execute the packages, build a sample external plugin, or run a Godot import; the PluginArchi unload claim is supported by its public implementation and unit tests but should still be covered by an Orc Bot integration test with an actual plugin that holds and then releases host resources.  I found no source or feed API matching the daemon/client or typed cursor requirements; that is a verified absence from the enumerated public surfaces above, not a claim that a different unpublished package cannot exist.
