# S3 — Memory, context, profiles, and loadouts

### Dependency-edge context was only a transcript-tail placeholder

- Evidence: prior-attempt (2026-07-27) orc-bot:README.md:129-147; prior-attempt (2026-07-27) orc-bot:project\terminal-host\crates\orcbot-host\src\work.rs:1278-1299 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The first snapshot made a graph edge both a dependency and a memory channel: it prefixed upstream task summaries to the next prompt. Its “derived” summary was explicitly a placeholder made from a transcript tail, not a semantic summary, so the context content was whatever terminal output happened to be captured. This established useful dependency-local context but did not produce a scoped or durable recall record.

### SurrealKV memory made store ownership a prerequisite for planning

- Evidence: prior-attempt (2026-08-06) orc-bot:docs\handovers\2026-08-06-store-lifecycle-and-memory.md:9-49,82-107 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The first live memory implementation put semantic and procedural rows beside the journal in embedded SurrealKV, but opening the store per run and per read created competing handles in a one-handle engine. The repair introduced a lazy, shared `JournalHost`, serialized reads through the write pump, bounded opening, and an explicit unavailable state so an unopenable memory store no longer stopped a plan. Dogfood evidence showed both a scoped recall and a goal brief carrying one remembered procedure and three past runs.

### SurrealKV’s operational sharp edges outweighed its initial fit

- Evidence: prior-attempt (2026-08-08) orc-bot:docs\adr\0003-sqlite-segments-filesystem-not-surrealdb.md:8-31 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The first attempt’s decision record says the SurrealKV journal and memory prototype worked, but a fresh-store `SELECT` failed rather than returning an empty result and the embedded .NET SDK was still young. It replaced that role with SQLite for durable control-plane data, FTS behind an `IMemoryIndex` seam, and filesystem-native agent-visible procedures. The failure was operational rather than a lack of CRUD capability.

### The first attempt’s rich execution profiles never reached production admission

- Evidence: prior-attempt (2026-08-11) orc-bot:docs\rfcs\0004-development-execution-profiles.md:57-71 (+ internal commit)
- Confidence: high
- Bearing: W10

By the first attempt’s final snapshot, development-profile validation, digests, capability probing, and admission policy were described as landed, while no profile had been admitted and no production operation had run through the runtime facade. The document separates test-harness Cargo evidence from a durable production admission record. Profile vocabulary therefore was not evidence that a real provider run had been reproducibly equipped.

### The second attempt’s SurrealDB design remained a context-store spike

- Evidence: prior-attempt (2026-08-12) orc-bot:docs\surveys\surrealdb-context-memory.md:5-20,86-107,219-235 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The second attempt proved file-backed embedded SurrealKV reads and writes on .NET 8/Windows and sketched immutable assembled-context rows with recipe and per-memory provenance. Its own qualification was that embedded live queries required WebSocket transport, SurrealKV was beta, and the spike did not decide memory truth, promotion, conflict handling, ranking, prompt-injection defenses, or good-context assembly. It also explicitly separated queryable memory from replayable event history.

### The final Mem0 path implemented only an agent-profile grant as a live scope

- Evidence: prior-attempt (2026-08-15) orc-bot:project\application\contracts\MemoryContracts.cs:45-69,151-170; prior-attempt (2026-08-15) orc-bot:project\agents\OrcBot.AgentExecution.Framework\LoadoutContextProviders.cs:568-590 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The general memory contract names installation, project, agent-profile, work-item, and session scope kinds, with opaque IDs derived from installation and Orc-owned references. The delivered framework resolver admitted only `scope.agent-profile`, deriving it from the installation reference and frozen profile ID; every other authored memory-grant reference was refused without a retrieval. The generic scope taxonomy was therefore broader than the provider path actually exercised.

### Mem0 provider filters could not be trusted to preserve Orc scope

- Evidence: prior-attempt (2026-08-15) orc-bot:project\source\mem0\OrcBot.Source.Mem0\Mem0HttpSource.cs:234-267,332-352; prior-attempt (2026-08-15) orc-bot:project\application\contracts\MemoryContracts.cs:517-610 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The Mem0 V3 search response did not guarantee returned `user_id` or `app_id`, so the adapter could not safely relabel a provider result into the requested Orc scope. Candidate writes stamped reserved Orc-owned scope and installation metadata, and retrieval rejected missing or mismatched attestations instead of exposing the result. This made provider scope filtering an input to verify, not an authority to trust.

### Supporting Mem0 meant supporting two operationally different transports

- Evidence: prior-attempt (2026-08-15) orc-bot:project\source\mem0\OrcBot.Source.Mem0\Mem0HttpSource.cs:17-66,312-414 (+ internal commit)
- Confidence: high
- Bearing: W10

The adapter split hosted Mem0 and self-hosted OSS because their routes, authentication headers, and add-response semantics differed. It also reported absent credentials, unreachable service, and timeouts as unavailable rather than fabricating an empty successful capability. The cost of a memory-provider seam included distinct transport and receipt validation paths, not simply one HTTP endpoint.

### Retrieved memory entered the invocation as bounded, lowest-precedence evidence

- Evidence: prior-attempt (2026-08-15) orc-bot:project\agents\OrcBot.AgentExecution.Framework\LoadoutContextProviders.cs:421-505; prior-attempt (2026-08-15) orc-bot:project\agents\OrcBot.AgentExecution.Framework\AgentFrameworkInvocationPreparer.cs:15-35,252-310 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

A materialized memory grant issued a real scoped query before the framework callback, rendered admitted recalls as JSON-quoted text with provider-memory ID and update time, and labelled every recall untrusted. Memory was assigned the `MemoryEvidence` layer below all policy, rules, intent, and skills; the framework adapter also capped results per grant and applied a finite character budget, recording excluded context sections. This is evidence that recall changed the delivered prompt, while retaining explicit limits and trust framing.

### A resolved loadout froze profile and provider state before dispatch

- Evidence: prior-attempt (2026-08-15) orc-bot:project\application\loadout\AgentLoadoutResolver.cs:39-42,158-173,183-271; prior-attempt (2026-08-15) orc-bot:project\application\operator\AgentLoadoutAuthority.cs:54-76 (+ internal commit)
- Confidence: high
- Bearing: W10

The resolver selected an admitted profile, bound an available provider, resolved the typed ability inventory, and derived a deterministic loadout digest before dispatch; unresolved profiles and unavailable providers were refused before resource allocation. It then materialized the loadout outside the source worktree into an attempt-private control root, including copied rules and skills plus a context package. This prevented mutable profile definitions or generated control files from silently changing an allocated source candidate.

### Historical loadout inspection verified retained bytes instead of re-resolving current definitions

- Evidence: prior-attempt (2026-08-15) orc-bot:project\application\operator\AgentLoadoutAuthority.cs:112-316 (+ internal commit)
- Confidence: high
- Bearing: W10

Attempt inspection read the retained binding and attempt-private `loadout.json`/manifest, then checked containment, binding identity, semantic digest, expected membership, file sizes, and SHA-256 values. The authority explicitly refused to re-resolve mutable current definitions as historical truth and returned a tampering or unavailable reason instead. This made the frozen profile/loadout itself reproducible as an audited inventory.

### Context receipts verified a constructed prompt but did not preserve a replayable memory retrieval

- Evidence: prior-attempt (2026-08-15) orc-bot:project\application\contracts\AgentProfileContracts.cs:349-458; prior-attempt (2026-08-15) orc-bot:project\application\contracts\AgentFrameworkContracts.cs:123-227,314-365; prior-attempt (2026-08-15) orc-bot:project\agents\OrcBot.AgentExecution.Framework\LoadoutContextProviders.cs:446-505 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The frozen context package retained prompt digest and length, skill/rule metadata, four typed grant collections, provider binding, and five evidence leaves; it did not include a memory-retrieval response leaf. The framework receipt retained memory-scope grant digests and context-entry instruction digests/lengths, while the actual provider response was fetched during preparation and its recalled text was rendered into the prompt. A receipt can therefore authenticate the assembled context evidence but cannot independently rerun or reconstruct the provider retrieval from retained receipt data.

### The six-way profile split made permissions operational but left four kinds as generic grants

- Evidence: prior-attempt (2026-08-15) orc-bot:project\application\contracts\AgentProfileContracts.cs:57-75,349-370,423-458; prior-attempt (2026-08-15) orc-bot:project\application\loadout\AgentLoadoutResolver.cs:558-561; prior-attempt (2026-08-15) orc-bot:project\application\operator\FrozenLoadoutPermissionPolicy.cs:8-75 (+ internal commit)
- Confidence: high
- Bearing: W10

Profiles classified abilities as Skill, Rule, Tool, Context, Memory, and Permission, with distinct semantics: tool availability was not permission, context remained bounded, memory remained scoped untrusted recall, and permission defaulted to denial outside its scope. Skills and rules were source-backed, copied, and individually indexed, whereas tool/context/memory/permission values were `AgentLoadoutGrant` records collected in one `grants-summary.json` leaf. The permission branch was operational: a frozen typed grant and allocation-private resource check decided requests rather than treating the profile as prompt text.

### Memory candidates could not self-promote and needed an independent authority record

- Evidence: prior-attempt (2026-08-15) orc-bot:project\application\contracts\MemoryContracts.cs:415-465,709-770; prior-attempt (2026-08-15) orc-bot:project\source\mem0\OrcBot.Source.Mem0\MemoryScopeFilter.cs:66-147 (+ internal commit)
- Confidence: high
- Bearing: ADR-0006

An agent-derived memory write remained an untrusted candidate with `IsSelfPromotable` false, and a promotion decision also declared itself not self-authorized. Promotion only targeted project or installation scope, deferred sensitive data, denied expired or mismatched cases, and required a separately source-attributed authorization that exactly matched candidate, source scope, target scope, installation, and trust. Terminal text could not become promoted memory by itself.

### Microsoft Agent Framework was constrained to prepare and observe, but its vocabulary reached application contracts

- Evidence: prior-attempt (2026-08-15) orc-bot:project\agents\OrcBot.AgentExecution.Framework\AgentFrameworkBoundary.cs:10-81; prior-attempt (2026-08-15) orc-bot:project\application\contracts\AgentFrameworkContracts.cs:9-44,148-227,314-365 (+ internal commit)
- Confidence: high
- Bearing: W10, ADR-0006

The adapter boundary prohibited Microsoft Agent Framework from executing a model, running a workflow graph, settling lifecycle, granting permission, publishing candidates, or making decisions; the existing typed machine channel remained the execution route. It did provide deterministic context preparation, a framework-session observation scope, and receipts that named loaded framework assemblies. At the same time, `AgentFrameworkContextPackage` and `AgentFrameworkInvocationReceipt` were application-contract types, so framework-specific context and receipt vocabulary crossed beyond the adapter project.

### The Mem0 proof established persistence and scope filtering, not a later-run quality gain

- Evidence: prior-attempt (2026-08-15) orc-bot:project\tests\live\OrcBot.AgentExecution.LiveSmoke\Program.cs:186-263 (+ internal commit)
- Confidence: medium
- Bearing: W10

The live smoke used a deterministic agent-profile scope, could run read-only after a native OSS restart, and checked that an accepted candidate became searchable through scoped retrieval. Its success criterion was provider availability, accepted write, and post-write search; it did not measure a subsequent agent task’s correctness, speed, or acceptance. The surveyed proof therefore demonstrates durable scoped recall, not that recall improved a later development run.
