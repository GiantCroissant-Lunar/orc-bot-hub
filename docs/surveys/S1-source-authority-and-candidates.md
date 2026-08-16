# S1 — Source authority, allocations, and candidates

### Disposable authoring allocations were real Git worktrees, not copies or overlays

- Evidence: `prior-attempt (2026-08-11) orc-bot`: `project/bundles/source-control/OrcBot.SourceControl.LibGit2Sharp/LibGit2SourceWorkspaceAllocationProvider.cs`:163 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

The disposable strategy created a LibGit2Sharp worktree at the requested commit, then verified both its registered name/path and the new worktree's `HEAD` before returning it. An in-place strategy also existed, but it refused any request whose base would move the canonical checkout. The allocation record carried source authority, strategy, root, base digest, and ownership token, so a path or a Git worktree alone was not treated as the allocation's authority.

### Allocation recovery failed closed on unmanaged or partly materialised worktrees

- Evidence: `prior-attempt (2026-08-11) orc-bot`: `project/bundles/source-control/OrcBot.SourceControl.LibGit2Sharp/LibGit2SourceWorkspaceAllocationProvider.cs`:241 (+ internal commit); `project/tests/OrcBot.SourceControl.Tests/SourceWorkspaceAllocatorTests.cs`:116 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

The provider repaired only an unjournaled worktree that was both registered by Git and a direct child of its managed root; unknown partial state was retained for inspection. It rejected unknown directories and unknown registered worktrees under the managed root rather than guessing ownership. The restart test physically moved an allocated root and established that reconciliation, and even subsequent reads, must fail rather than reuse the now-ambiguous allocation.

### Allocation refused unsafe repository and filesystem identities before materialising source

- Evidence: `prior-attempt (2026-08-11) orc-bot`: `project/bundles/source-control/OrcBot.SourceControl.LibGit2Sharp/LibGit2SourceWorkspaceAllocationProvider.cs`:326 (+ internal commit); `project/bundles/source-control/OrcBot.SourceControl.LibGit2Sharp/LibGit2SourceWorkspaceAllocationProvider.cs`:343 (+ internal commit); `project/bundles/source-control/OrcBot.SourceControl.LibGit2Sharp/LibGit2SourceWorkspaceAllocationProvider.cs`:380 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

The allocator refused a configured canonical path that was not the repository root, a managed root overlapping that checkout, and any allocation path that escaped its managed root. It also rejected unsafe allocation IDs, reparse points, unknown bases, and a worktree registration whose path or name did not match the durable allocation. These guards were added because path identity otherwise permits traversal, symlink redirection, or a stale/foreign worktree to be mistaken for Orc Bot's fenced allocation.

### Allocation fences were durable monotonic ownership tokens, not just temporary locks

- Evidence: `prior-attempt (2026-08-11) orc-bot`: `project/tests/OrcBot.SourceControl.Tests/SourceWorkspaceAllocatorTests.cs`:9 (+ internal commit); `project/tests/OrcBot.SourceControl.Tests/SourceWorkspaceAllocatorTests.cs`:37 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

The allocation test reopened the durable journal and proved that the original token still validated after restart, then became stale on release while the next allocation received a larger token. A second allocator instance was refused while an in-place allocation was active, so canonical-root writing had one durable owner. Disposable allocations instead received distinct roots and distinct tokens when requested concurrently.

### Derived state was excluded from source candidates, and one shared Godot cache silently produced wrong results

- Evidence: `prior-attempt (2026-08-12) orc-bot`: `docs/adr/0001-layered-source-workspaces.md`:76 (+ internal commit); `docs/adr/0001-layered-source-workspaces.md`:156 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

The source filter was introduced after OpenCode left `.omo/` tool state in a live workspace; `.godot/`, `node_modules/`, `bin/`, `obj/`, and `.omo/` were classified as changed-but-not-source rather than candidate content. The Godot experiment found a private cache could be hardlink-seeded from a warm master in about 5.8 seconds without new bytes, while a shared cache was unsafe. Because cache entries were keyed by path, two divergent workspaces could both import successfully yet leave the shared cache describing the other workspace's asset.

### A live list of changed paths did not freeze a candidate

- Evidence: `prior-attempt (2026-08-12) orc-bot`: `project/hosts/complete-app/Anvil/SourceCandidate.cs`:28 (+ internal commit); `docs/adr/0001-layered-source-workspaces.md`:228 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

Before `SourceCandidate`, the proposed candidate was `SourceChanges`: paths reread from the live working tree on demand. If the agent was still writing, two captures could name different content as the same candidate, and deleting the workspace destroyed the only evidence. The replacement froze source-authority-selected entries and treated a selected file that vanished between inspection and capture as a deletion instead of silently dropping it.

### A hash-only candidate description could not support dependent work

- Evidence: `prior-attempt (2026-08-12) orc-bot`: `project/hosts/complete-app/Anvil/SourceCandidate.cs`:46 (+ internal commit); `project/hosts/complete-app/Anvil/CandidateStore.cs`:25 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

`SourceCandidate` originally retained hashes and metadata but not the file bytes, which made candidates comparable but unusable as a dependency base once the workspace was discarded. `CandidateStore` therefore paired the frozen description with a patch artifact written at publication time. The experiment explicitly treated the patch as a provider mechanism, while requiring that the stored artifact include exactly the same source-authority-approved paths as the candidate.

### Candidate digests were stable only because they named the base and canonicalised every entry

- Evidence: `prior-attempt (2026-08-12) orc-bot`: `project/hosts/complete-app/Anvil/SourceCandidate.cs`:77 (+ internal commit); `project/hosts/complete-app/Anvil/SourceCandidate.cs`:130 (+ internal commit); `project/tests/acp-conformance/SourceCandidateTests.cs`:67 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

Freezing sorted distinct source paths and hashed the base generation plus every path, operation kind, and content hash. The test proved that an unchanged tree re-froze to the same digest at a different time, while changing a captured file or changing only the base changed the candidate identity. This made the candidate a representation of a specific delta over a specific generation rather than of a workspace at a time.

### Untracked added files initially yielded an appliable-looking but empty dependency artifact

- Evidence: `prior-attempt (2026-08-12) orc-bot`: `project/hosts/complete-app/Anvil/CandidateStore.cs`:135 (+ internal commit); `project/tests/acp-conformance/MaterializeTests.cs`:103 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

`git diff HEAD` ignores an untracked new file, so a candidate could list its content hash while the generated patch carried no file at all. The resulting patch applied cleanly and a dependent workspace appeared successfully materialised, but lacked the code it was supposed to inherit. Publication had to add the candidate paths with `git add --intent-to-add` before diffing; this modified Git's index but not the worker's working tree.

### Composing dependencies required a new private allocation, verified byte application, and a synthetic composed base

- Evidence: `prior-attempt (2026-08-15) orc-bot`: `project/application/operator/CandidateStackComposer.cs`:76 (+ internal commit); `project/application/operator/CandidateStackComposer.cs`:678 (+ internal commit); `project/application/operator/CandidateStackComposer.cs`:751 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

`CandidateStackComposer` resolved every transitive ancestor's published candidate, allocated a new fenced Git workspace, then applied each layer before binding that workspace to the dependent work item. Applying a layer verified both manifest and artifact digests, provenance fields, each entry's content digest and size, and wrote the verified bytes into the workspace. It then made a synthetic Git commit of the composed paths, because later delta capture against the root generation would otherwise republish ancestor changes as the dependent item's own work.

### One untyped `DependsOn` edge simultaneously gated execution and selected workspace layers

- Evidence: `prior-attempt (2026-08-12) orc-bot`: `project/hosts/complete-app/Dispatch/WorkGraph.cs`:77 (+ internal commit); `project/hosts/complete-app/Dispatch/WorkGraph.cs`:102 (+ internal commit); `project/hosts/complete-app/Anvil/CandidateStore.cs`:79 (+ internal commit)
- Confidence: high
- Bearing: ADR-0007, W3

The planner used `DependsOn` first as an ordering gate: an item was blocked until every dependency had a candidate. It used the same field again to derive the transitive `WorkBase.Layers` to materialise in that item's workspace. Because the candidate store keyed this lookup by work-item ID and chose the newest publication, an edge to item `A` also implicitly selected whichever `A` candidate was latest rather than a declared immutable candidate identity.

### Independent sibling conflicts were detectable before spending a dependent agent invocation

- Evidence: `prior-attempt (2026-08-15) orc-bot`: `project/application/operator/CandidateStackComposer.cs`:621 (+ internal commit); `project/hosts/complete-app/Dispatch/WorkExecutor.cs`:160 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0007

Composition compared changed paths only between candidate layers whose work items were independent; ancestor/descendant pairs were allowed to overlap. An overlap raised a `candidate_layer_conflict` that named both work items, candidate identities, and paths, and refused dependent allocation before agent launch. The earlier executor applied the same policy by returning `RefusedConflict` rather than dispatching an agent to rediscover the collision during a merge-like failure.

### Semantic completion, publication, review, and acceptance remained distinct durable outcomes

- Evidence: `prior-attempt (2026-08-15) orc-bot`: `project/runtime/agent-execution/AgentOperationSupervisor.cs`:461 (+ internal commit); `project/runtime/agent-execution/AgentOperationSupervisor.cs`:489 (+ internal commit); `prior-attempt (2026-08-11) orc-bot`: `project/contracts/OrcBot.Contracts/Candidates/CandidateLifecycle.cs`:4 (+ internal commit)
- Confidence: high
- Bearing: ADR-0002

On an `AgentCompleted` machine event, the supervisor attempted candidate finalization but still recorded the semantic operation outcome as `Completed`; a finalizer exception became a separate failed capture result. The earlier candidate lifecycle likewise stated that a published candidate could be rejected without rewriting the authoring outcome, and modelled acceptance as a later state. This is direct evidence that the mature code did not equate the agent's end turn with candidate publication or human disposition.

### Frozen candidates were immutable evidence bundles addressed by candidate identity and SHA-256 artifacts

- Evidence: `prior-attempt (2026-08-15) orc-bot`: `project/evidence/files/OrcBot.Evidence.Files/FileCandidateArtifactAuthority.cs`:26 (+ internal commit); `project/evidence/files/OrcBot.Evidence.Files/FileCandidateArtifactAuthority.cs`:79 (+ internal commit); `project/application/operator/CandidateStackComposer.cs`:684 (+ internal commit)
- Confidence: high
- Bearing: W3, ADR-0002

Publication sorted and validated selected entries, then wrote an artifact containing the candidate ID, source generation, producing allocation, fence, attempt, operations, bytes, sizes, and content digests, plus a manifest referring to the artifact digest. It addressed the evidence under the candidate ID and refused to overwrite an existing candidate directory, while artifact and manifest filenames incorporated their SHA-256 digests. Before composition, the later code required the candidate to be published, from the same source generation, and to pass both artifact and manifest digest verification.
