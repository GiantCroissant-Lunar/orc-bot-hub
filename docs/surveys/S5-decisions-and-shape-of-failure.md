# S5 — Decisions, build tooling, and the shape of the failure

Survey for RFC-0002, topic S5. Reads the second attempt's documentation against
what its code and build tooling actually did, then dates the moment each attempt
stopped being usable by the people building it.

Path shorthand (all snapshots read-only; no git command was run — every git fact
below was read directly from `.git\logs\HEAD` and `.git\config` as files):

- **A2** = `prior-attempt (2026-08-15) orc-bot` (attempt 2, final state; reflog begins 2026-08-12 21:10 +08, ends 2026-08-14 19:51 +08, HEAD `eeda20a`)
- **A2b** = `prior-attempt (2026-08-12) orc-bot` (attempt 2's other lineage, per its own ledger)
- **A1-dddd** = `<workspace>/-<date>\agent-projects\orc-bot` (attempt 1 snapshots)

## Attempt 2: which decisions held, which were violated

### Attempt 2 accepted its foundation decisions and reversed most of them the same day it started

- Evidence: A2:docs\decision-register.md:45-55 (seven wholesale reversals in the "Superseded decisions" table); A2:docs\adr\0001-product-root-and-runtime-boundary.md:3, 0002:3, 0003:3 (all "Accepted (corrected 2026-08-12)")
- Confidence: high
- Bearing: ADR-0000

The register was opened 2026-08-12 with an accepted fake-first, thin-panel,
no-frameworks direction, and the same date's "corrected" ADRs replace it with
real-first, GraphEdit-required, Akka+Arch-now. The superseded table is not
evolution over weeks; it is a day-one flip. A restart that begins by accepting
and then correcting its own first-day ADRs has not actually made decisions — it
has made drafts. The new attempt should treat its earliest ADRs as its most
suspect ones and keep the irreversible set minimal until code exists.

### The fake-first code really existed; its excision left Godot `.uid` residue behind

- Evidence: A2:project\validation\OrcBot.Validation.Fakes\ contains only `DeterministicFakeValidator.cs.uid` and `FakeMaterializationProvider.cs.uid` (the `.cs` files are gone); the project is absent from A2:project\OrcBot.slnx
- Confidence: high
- Bearing: ADR-0002, ADR-0004; RFC-0001 W3

The superseded "deterministic fake materialization" direction was not
hypothetical — `DeterministicFakeValidator` and `FakeMaterializationProvider`
were implemented, then deleted when D-11/D-14 banned them, leaving only the
Godot editor's `.cs.uid` sidecar files. Two lessons: a reversed decision leaves
physical residue that no gate caught (the `.gitignore` ignores `*.cs.uid`, so
this residue lived only on disk), and cleanup of a reversed decision was
necessarily incomplete because nothing enumerates "things the old decision
created."

### Two whole test projects survive only as `.uid` residue; the solution includes neither

- Evidence: A2:project\tests\OrcBot.Foundation.Tests\ and A2:project\tests\agent-execution\ each contain only `*.cs.uid` files (`ContractAndBoundaryTests.cs.uid`, `LayeredLifecycleTests.cs.uid`, `AgentOperationSupervisorTests.cs.uid`, ...); A2:project\OrcBot.slnx:40-43 admits only `tests/workflow` and `tests/live`
- Confidence: high (absence); medium (that the sources were deleted rather than renamed — the surviving `tests/workflow` file names do not match)
- Bearing: RFC-0001 ordering — a gate must live in a runnable task before the code it gates is deleted or moved

The implementation plan's Phase 0 gate claims "real SQLite-backed command
replay, changed-intent rejection, restart reopen, and evidence-digest checks
pass" (A2:docs\implementation-plan.md:17). The projects that would have proven
that have no surviving source and no place in the solution. Whatever they
covered now has no automated proof, while the plan still cites the gate as
passed. Gates recorded only in prose rot exactly as fast as the tests they
describe.

### The decisions that genuinely held: adapter isolation and terminal-versus-machine-channel separation, enforced by tests that still exist

- Evidence: A2:project\tests\workflow\RealWorkflowRestartTests.cs:48-56 (workflow contracts assert no Akka/Arch/Markdig/Microsoft.Data.Sqlite/GodotSharp references); A2:project\tests\workflow\OperatorBindingDurabilityTests.cs:314-328 (four contract/runtime assemblies assert no Sqlite binding leakage); Zellij lives in `execution\zellij`, the typed bridges in `execution\agent-bridge`, with durable events asserted separate from pane diagnostics (A2:project\tests\README.md:88-98)
- Confidence: high
- Bearing: confirms new ADR-0001/0003 invariants are cheaply enforceable; RFC-0001 can lift these two test shapes nearly verbatim

Amid the churn, two structural decisions held all the way into the final tree
and were protected by assembly-reference assertions rather than review. D-14
also held in the letter: a grep of `A2\project\**\*.cs` finds no
Fake/Stub/Sample/Demo identifier, and live provider modes are env-gated opt-ins
that report `unavailable` rather than pass (A2:project\tests\README.md:28-70).
These are the pieces worth keeping faith with.

### The decision register decayed into an implementation specification

- Evidence: A2:docs\decision-register.md:42-43 — D-28 and D-29 are single-decision paragraphs specifying protocol bytes ("a literal-empty `session/set_mode` success is an acknowledgment, not independent mode readback", "exactly one absolute confined `toolCall.locations` path"); the register grew D-01 through D-29 between 2026-08-12 and 2026-08-14 (line 3)
- Confidence: high
- Bearing: ADR-0000

Twenty-nine accepted decisions in three days, the last two unreadable without
the ACP spec beside you. D-29 alone defines five durable launch phases and
their recovery semantics. Decisions at that granularity cannot be reviewed,
cannot be checked, and — the important part — cannot be *held* by code, which
is presumably why the final days disappeared into exactly the recovery and
cleanup machinery D-21/D-28/D-29 describe. This is the direct failure the new
attempt's short-immutable-ADR rule answers.

### A machine-usable surface was bolted on only at the end, after two days of driving the product exclusively through a giant window

- Evidence: A2:project\hosts\dogfood-console\Program.cs:39-42 ("Bounded machine-oriented product host ... intentionally exposes no lifecycle ... control surface of its own"), added by reflog commit `57ada405` 2026-08-13 21:36 "feat(host): add bounded dogfood console"; until then the only surface was the Godot window (`hosts\complete-app\scripts\Main.cs`, 1,638 lines)
- Confidence: high
- Bearing: RFC-0001 (CLI-first), ADR-0001

On day two of three, the builders gave themselves a console host because
operating the product through its own exported window was too expensive even
for the agent building it. The dogfood console is deliberately bounded — it
can observe, not act — which is the right instinct arrived at two days late.
The third attempt making "headless, agent-addressable" the v0 target is
adopting attempt 2's deathbed realization as its starting point.

## Build, CI, and the artifact/version layout

### Attempt 2's only automated gate never ran a single test

- Evidence: A2:Taskfile.yml:3-26 — tasks are `build`, `verify:windowed`, `repomix`, `repomix:with-tests`, `repomix:no-tests`; there is no test or lint task, and A2 has no `.github` directory (no CI at all)
- Confidence: high
- Bearing: new ADR-0005; RFC-0001 must land `task test`/`task verify` before the code they gate

xunit test projects existed (`tests/workflow` with 25 test files), but nothing
in the task pipeline or any automation executed them. Tests ran only when a
human or agent chose to run `dotnet test`. Combined with the deleted foundation
projects above, any amount of test rot could land while every gate stayed
green. The current repo's honesty about `task ci` proving only
hygiene/format/compile is the correct response; the moment W1 lands, the gate
must actually run.

### The automated "verify" was precisely the window-presence check the attempt's own product rules disallow as acceptance

- Evidence: A2:build\build.ps1:66 invokes verify-windowed.ps1 at the end of `build`; A2:build\verify-windowed.ps1:8-9,104-130 asserts a visible window titled "Orc Bot", at least 2400x1450, surviving a 3-second observation; A2:docs\product-brief.md:32 — "a ... window-presence check is not semantic completion by itself"
- Confidence: high
- Bearing: ADR-0005; W12

The repo's own brief forbids window-presence as acceptance, yet the build task
ends with a window-presence check as its only verification. The distinction the
docs draw — presence versus exercised behavior — was real and enforced, but
only by the *manual* protocol (`.agent\skills\verify-exported-godot-app\SKILL.md`
plus screenshot runs), never by automation. The new attempt separating
`task build` from windowed validation is drawing this same line in tooling.

### Attempt 1's final line had the richer build gate; attempt 2 regressed to a single task

- Evidence: A1-20260811:docs\build.md:3-57 (GitVersion SemVer with FullSemVer/MajorMinorPatch fallback, artifact retention keeping newest three, bundle roots) and :75-80 (`agent-dispatch-smoke` boots the exported app, runs a real CLI to completion, then asserts ownership "from SQLite rather than from the app's log")
- Confidence: high
- Bearing: RFC-0001 — recover the assert-from-durable-state smoke pattern when the runtime exists

Attempt 1's last repository had version fallback chains, artifact retention,
and smokes whose assertions read the control-plane database instead of app
output — exactly the "terminal output is never truth" discipline, in tooling.
Attempt 2 replaced all of it with one build task and a screenshot protocol.
The regression direction is worth remembering: the second attempt was not
strictly more mature than the first; it traded build tooling for decision
documents.

### Attempt 2's version never advanced past 0.1.0, so every build overwrote the same artifact directory

- Evidence: A2:GitVersion.yml:3-7 (`next-version: 0.1.0`, strategies begin with `ConfiguredNextVersion`); A2:.nuke\temp\build.2026-08-14_19-32-42.log and build.2026-08-14_19-50-50.log — distinct `repo_commit` values (`71cf3d`, `fedd69`) both end "Linked ...\build\_artifacts\latest -> 0.1.0"
- Confidence: high on the effect (two builds of different commits, same `0.1.0`); medium on the mechanism (ConfiguredNextVersion is documented to force `next-version`)
- Bearing: ADR-0005 — the new "one version per commit" invariant; keep `ConfiguredNextVersion` out of the strategy list

`GitVersion.yml` was added to make the first build come out as 0.1.0, and the
strategy list pinned it there permanently. `build/_artifacts/0.1.0` was
overwritten on every build, and `latest` pointed at a directory that did not
identify a commit. The layout itself (`build/_artifacts/<version>/godot/win-x64`
plus a `latest` symlink, A2:build\build.config.json:3-4, build.ps1:58-66) was
sound and nothing depended on version differentiation except the humans.

### Because builds were indistinguishable, human acceptance records pinned executables by SHA-256 by hand

- Evidence: A2:.tmp\windowed-acceptance\20260814-1812-m2\acceptance.md:5-6 — "Packaged executable: ...\latest\godot\win-x64\orc-bot.exe / Executable SHA-256: EF4C2949..."
- Confidence: high
- Bearing: ADR-0005

The manual acceptance record has to state the executable's SHA-256 because the
artifact path identifies nothing. When the build system cannot name a build,
the evidence protocol grows a compensating human step — the same pattern as the
screenshot protocol compensating for the missing test task.

### Nothing else depended on the versioned artifact tree

- Evidence: A2:build\build.ps1:64-66 (consumers are verify:windowed via `latest` and the receipt path); workflow validation materializes into its own slot workspace (A2:docs\architecture.md:106-110), not the artifact tree
- Confidence: high
- Bearing: none

The artifact layout served the build and the manual acceptance loop only.
The new attempt's consumers (`task artifacts`, `task godot:export`) match this
shape, so no additional dependency needs manufacturing.

## Attempt 1: the shape of the failure

### "Attempt 1" was at least five fresh `git init`s in fifteen days, each abandoning the previous tree unmerged

- Evidence: initial reflog commits — A1-20260803 (2026-07-29 08:49, SurrealDB sidecar), A1-20260805 (2026-08-03 21:56, "orc-bot spine — Godot host, ProcessKit containment"), A1-20260806 (2026-08-05 16:29, "task methods, planner, claims, SurrealKV journal"), A1-20260808 (2026-08-07 11:33, "docs: v1 architecture baseline, ADR/RFC decision records"), A1-20260811 (2026-08-08 14:24, "chore: establish orc bot architecture baseline"); A1-20260727 contains `.git`, a `vault\`, and no reflog at all
- Confidence: high
- Bearing: ADR-0000

The unit of failure was the repository, not the feature. Median repo lifetime
was about two days; the 20260808 repo was re-initialized the same day its last
commit landed (08-08 05:30 branch checkout, new init 14:24). Nothing was merged
forward — each snapshot's initial commit is fresh, so no history, and no
learning encoded in history, survived a restart. This is why the third attempt
insists on one repo and conventional commits from day zero.

### Attempt 1's final day fissioned into three parallel repositories plus an unmerged survey worktree

- Evidence: `prior-attempt snapshot (2026-08-12)\agent-projects\` contains `orc-bot`, `orc-bot-kilo`, `orc-bot-oc`; A2:docs\source-ledger.md:10 records main at `00dea65`, kilo at `1a31113` merged at `50e3d3e`, oc at `ffd864e` present-by-blob-not-ancestry, and a survey worktree at `876054e` unmerged
- Confidence: high
- Bearing: ADR-0000; the AGENTS.md worktree-race traps

The known multi-agent failure mode — `opencode` and `kilo` resolving the
project root through the gitdir pointer and diverging into sibling checkouts —
happened here at repository scale: three agent-named repos with different
merge states. "Which tree is real" stopped having an answer, and the response
was to demote all of them to research material.

### Attempt 1's technical decisions flipped within hours, repeatedly

- Evidence: A1-20260805 reflog 2026-08-04 09:17 → 09:23 → 09:28 ("revise M4 after studying how Orca solves terminals" → "adopt godot-xterm" → "prefer alacritty_terminal"), with a self-built TerminalView GDExtension landed at 10:07; storage: A1-20260803 commits are a SurrealDB sidecar, A1-20260806's initial commit says SurrealKV journal, A1-20260811:docs\adrs\0012 adopts "SQLite control plane and transactional outbox"
- Confidence: high
- Bearing: none — supports the reference-only posture

Three terminal-emulator decisions inside eleven minutes, and a storage
substrate that changed three times across three repos. None of these flips was
wrong on its merits; the failure is that each flip was paid for at full price
because no repo survived long enough to amortize anything.

### Attempt 1's own progress records were discovered to be false at least twice

- Evidence: A1-20260805 reflog 2026-08-04 20:36 "docs: correct finding 005 -- session/prompt was never actually verified"; A1-20260806 reflog final entry 2026-08-06 18:10 "fix(ui): one write path per act, and stop reporting an outage as a fact"
- Confidence: high
- Bearing: ADR-0003

A milestone previously recorded as verified turned out never to have been, and
the UI was reporting outages as completed facts. These are the concrete
incidents behind "terminal output is never truth" — the invariant was learned
from the builder's own logs, twice.

## When each attempt stopped being usable, and what was being built

### Attempt 2 passed its entire first-slice acceptance exactly once, manually, on 2026-08-13 at 23:45 — then spent its last twenty hours on interruption hardening and died inside that hardening's acceptance loop

- Evidence: A2:.tmp\windowed-acceptance\pass-20260813-233530\evidence\ (twelve screenshots: initial → allocated → agent-completed → typed-events → candidate-published → validation-succeeded → rejected-completed → restart-recovered, 23:35–23:45); A2 reflog 2026-08-14: `4506365` 18:43 "feat: add durable operator-attention surface and safety-gated Retry cleanup", then `6b14946` 19:20 "fix: secure milestone three cleanup retry", `43a187a` 19:32 "fix: retain cleanup receipt in operator view", `eeda20a` 19:51 "fix: harden windowed cleanup acceptance" (the last commit); A2:.tmp\windowed-acceptance\20260814-1922-m3\ and 20260814-1938-m3-r3\ contain screenshots named `05-retry-receipt-overwritten-fail.png` and `06-retry-remained-disabled-fail.png`; `20260814-1953-m3-final\` has four screenshots and **no** acceptance.md
- Confidence: high
- Bearing: RFC-0001 ordering — automatable acceptance must precede durability hardening, and manual-protocol milestones must be capped

The full vertical slice — real workflow, real Codex provider, immutable
candidate, exported-window validation, human rejection, restart recovery —
genuinely worked once. What followed was the killer: milestones 1–3 of
recovery/cleanup/attention hardening, each requiring the manual windowed
protocol, with the attempt's final three commits all fixing the acceptance of
its own newest feature. The last recorded action on the project (19:53, two
minutes after the last commit) is an incomplete acceptance retry. The failure
shape is not "couldn't build it" — it is "acceptance cost grew faster than
features, and the attempt ran out of runway inside its own gate."

### Attempt 2's final hours of work are not fully represented in its own commit history

- Evidence: A2:.nuke\temp\build.2026-08-14_19-32-42.log and _19-50-50.log cite `repo_commit` `71cf3d` and `fedd69`, neither of which appears in A2:.git\logs\HEAD (which ends at `eeda20a`, 2026-08-14 19:51); `.tmp` evidence continues to 19:53
- Confidence: high on the observation; low on the cause (amend/rebase churn during the final fix sequence is plausible but unverifiable without git commands)
- Bearing: AGENTS.md "commit often and in small slices"; ADR-0000

Even the snapshot's own telemetry disagrees with its reflog about what HEAD
was on the final evening. Whatever the mechanism, the final state of attempt 2
was not reproducible from its history — the exact problem the new attempt's
small-slice commit rule and `task verify` hygiene gates exist to prevent.

### Attempt 1 stopped being usable when "which tree is real" became unanswerable; it was mid-bridge, not mid-crisis

- Evidence: A1-20260811 reflog final entry 2026-08-11 16:25 `b88054c` "fix: bridge Claude completion receipts" (preceded same-day by "pane-argv-fidelity" and "rfc0007-c5a-rust-lifecycle" notes); A2:docs\source-ledger.md:9-10 demotes the whole line to research ("Do not import OwnedOperationRunner ... Do not treat GraphDemo as real dispatch"); A2:docs\adr\0005-work-item-dags-provider-registry-and-observation.md:10-12 names the 20260812 line's stub-authored graph and auto-approve policy as "what must not be copied"
- Confidence: high
- Bearing: ADR-0000

The last attempt-1 repository ended on an ordinary engineering commit, with
live proofs recorded that week (Zellij smoke, OpenCode live proof, Rust live
proof, C3 dispatch — A1-20260811:docs\notes\). It did not collapse; it was
ruled unusable from outside, a day later, when its successor had to write a
source ledger explaining that three divergent checkouts and a demo graph
disconnected from real dispatch did not add up to one product. The usability
death was organizational: too many trees, no authority.

### Every commit on both attempts, across all seven repositories, is by a single agent identity

- Evidence: reflog author lines "ApprenticeGC <apprentice@giantcroissant.com>" on every entry of A1-20260803, A1-20260805, A1-20260806, A1-20260808, A1-20260811, A1-20260812 (main), and A2
- Confidence: high
- Bearing: RFC-0001's v0 target ("headless, agent-addressable ... remembers previous development experience")

The builder was an agent with no durable memory across five repository
re-initializations, operating its own product through screenshots of a
2560x1440 window. The two failure shapes above — decisions that churn because
nothing remembers them, and repositories that restart because nothing carries
forward — are what it looks like when the coordination tool you need is the
one you are trying to build. The v0 goal of an agent-addressable coordinator
with memory is aimed directly at this builder's recorded experience.

## Unverified recollections

- The mechanism pinning every build at 0.1.0 is almost certainly the
  `ConfiguredNextVersion` strategy forcing `next-version`; the effect is
  evidenced by the paired Nuke logs, but I could not confirm the strategy's
  semantics from the snapshot itself.
- I believe the 2400x1450 minimum window size in verify-windowed.ps1 exists
  because the screenshot-driven acceptance protocol needed text legible to the
  verifying agent; no document states a motive.
- I believe the `71cf3d`/`fedd69` commits cited by the final Nuke logs were
  amended or rebased away during the last cleanup-fix sequence; verifying would
  require git commands, which were forbidden.
- The mapping of the commits' "milestone one/two/three" labels onto the
  implementation plan's numbered phases is my inference (M1 ≈ authority
  recovery, M2 ≈ lifecycle settlement, M3 ≈ attention/cleanup); no surviving
  document defines the mapping.
