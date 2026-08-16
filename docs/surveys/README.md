# Surveys

Evidence recovered from the two abandoned Orc Bot attempts on the prior-attempt snapshots.

Surveys are **input to decisions, never decisions themselves**. A finding may
change an ADR or an RFC work item, but only by someone writing that change.

Every claim carries evidence in this shape:

```markdown
### <short claim, stated as a fact>

- Evidence: <snapshot path>:<file>[:line] (+ commit sha where the tree has git)
- Confidence: high | medium | low
- Bearing: <which RFC-0001 work item or ADR this changes, or "none">

<two to six sentences: what was tried, what happened, why it matters here.>
```

A claim with no evidence line is deleted rather than softened. Things a surveyor
believes but cannot evidence go at the end, under `## Unverified recollections`.

Scope and assignments: [RFC-0002](../rfc/0002-recover-prior-attempt-knowledge.md).
