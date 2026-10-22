# Open Well-Architected Agent

**An open-source AI agent that analyzes AWS environments against the AWS Well-Architected Framework and your business goals, then delivers prioritized recommendations with ready-to-implement remediation.**

This is a complete, working end-to-end implementation (inspired by the official AWS Well-Architected Agent preview).

---

## What it does (end-to-end)

```
AWS Accounts (or demo data)
        |
        v
+-----------------------+
| 1. Collect Findings   |  <- resource configs, utilization, Trusted Advisor style findings
+-----------+-----------+
            |
            v
+-----------------------+
| 2. Analyze & Prioritize|  <- against Well-Architected pillars + YOUR business goals
+-----------+-----------+
            |
            v
+-----------------------+
| 3. Generate Remediation|  <- Terraform / CLI / Console / SSM ready-to-use fixes
+-----------+-----------+
            |
            v
+-----------------------+
| 4. Human Review       |  <- you stay in control (review -> test -> implement)
+-----------------------+
```

---

## Two versions included

| File | Version | Description |
|------|---------|-------------|
| `open_wa_agent.py` | **v1 – Pure Python / LangGraph-style** | Fully self-contained. Runs with zero external AI keys. Uses a deterministic reasoning engine that mimics LangGraph multi-step flow. |
| `open_wa_agent_bedrock.py` | **v2 – Amazon Bedrock** | Same interface, but calls Amazon Bedrock Converse API for real LLM reasoning. Falls back to v1 if Bedrock is unavailable. |

Both produce the exact same recommendation schema.

---

## Quick Start (30 seconds)

```bash
cd open-well-architected-agent

# Version 1 – works immediately, no keys needed
python open_wa_agent.py --demo

# Version 2 – Bedrock (needs AWS credentials + model access)
python open_wa_agent_bedrock.py --demo
```

You will see:
- Collected findings
- Prioritized recommendations (with priority scores)
- Concrete remediation (Terraform + CLI + Console steps)
- Full JSON export option

---

## Project Layout

```
open-well-architected-agent/
├── README.md
├── open_wa_agent.py              # v1 complete end-to-end (LangGraph-style)
├── open_wa_agent_bedrock.py      # v2 Bedrock version
├── examples/
│   └── sample_output.json
└── docs/
    └── ARCHITECTURE.md
```

---

## Disclaimer

This is an independent open-source project.  
It is **not** affiliated with or endorsed by Amazon Web Services.  
Always review recommendations before applying them in production.

The official AWS Well-Architected Agent remains the managed, fully supported service.
