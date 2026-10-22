# Architecture Deep Dive

## High-level flow (both versions)

```
Collect Findings -> Analyze & Prioritize -> Generate Remediation -> Finalize & Present
```

## Version 1 – Pure Python / LangGraph-style

- No external LLM required.
- Four explicit stages that map 1:1 to LangGraph nodes.
- Scoring is transparent (severity base + business-goal boost).
- Remediation is rule-based and produces real Terraform / CLI snippets.

Ideal for learning the flow, CI / offline environments, and guaranteed reproducible output.

## Version 2 – Amazon Bedrock

- Same collection and final schema.
- Analyze + Remediate steps call Bedrock Converse API.
- Falls back automatically to Version 1 logic if Bedrock is unreachable.

Ideal for production-quality natural language reasoning and cross-pillar trade-off analysis.

## Data contracts

Every recommendation always contains:

| Field | Purpose |
|-------|--------|
| priority_score | 0–100 ranking driven by severity + business goals |
| pillar | cost / security / performance / resilience |
| level | resource / application / architecture |
| trade_offs | explicit cross-pillar impact statements |
| remediations[] | ready-to-use Terraform, CLI, Console, or SSM |

## Extending to real multi-account AWS

Replace `collect_findings()` with:

1. STS AssumeRole into each target account
2. AWS Config → resource configurations
3. CloudWatch → utilization metrics
4. Trusted Advisor (Support API) → existing findings
5. Cost Explorer → spend anomalies

Keep the same `Finding` → `Recommendation` → `Remediation` pipeline.
