#!/usr/bin/env python3
"""
Open Well-Architected Agent – Version 2 (Amazon Bedrock)

Same end-to-end flow as v1, but the Analyze + Remediate steps call
Amazon Bedrock Converse API for real LLM reasoning.

Falls back to the deterministic engine from v1 if Bedrock is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Re-use everything from v1
from open_wa_agent import (
    Finding,
    Recommendation,
    Remediation,
    Pillar,
    Level,
    Severity,
    collect_findings,
    analyze_and_prioritize,
    generate_remediations,
    asdict,
)


def call_bedrock(system: str, user: str, model_id: Optional[str] = None) -> str:
    """Call Amazon Bedrock Converse API."""
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for the Bedrock version") from exc

    region = os.getenv("AWS_REGION", "us-east-1")
    model = model_id or os.getenv(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
    )

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"temperature": 0.1, "maxTokens": 4096},
    )
    return response["output"]["message"]["content"][0]["text"]


def extract_json(text: str) -> Any:
    text = text.strip()
    if "```" in text:
        for start, end in (("[", "]"), ("{", "}")):
            s = text.find(start)
            e = text.rfind(end) + 1
            if s != -1 and e > s:
                text = text[s:e]
                break
    return json.loads(text)


def run_bedrock_agent(
    account_ids: List[str],
    business_goals: str,
    demo: bool = True,
) -> Dict[str, Any]:
    print("=" * 70)
    print("  Open Well-Architected Agent  –  v2 (Amazon Bedrock)")
    print("=" * 70)
    print(f"Accounts      : {', '.join(account_ids)}")
    print(f"Demo mode     : {demo}")
    print(f"Business goals: {business_goals}")
    print()

    # Node 1 – Collect (same as v1)
    print("▶ Node 1 – Collect findings...")
    findings = collect_findings(account_ids, demo=demo)
    print(f"  → Collected {len(findings)} findings\n")

    findings_json = json.dumps(
        [
            {
                "id": f.id,
                "title": f.title,
                "description": f.description,
                "pillar": f.pillar.value,
                "severity": f.severity.value,
                "service": f.service,
                "resource_id": f.resource_id,
            }
            for f in findings
        ],
        indent=2,
    )

    # Node 2 – Analyze with Bedrock
    print("▶ Node 2 – Analyze with Bedrock...")
    system = f"""You are an expert AWS Solutions Architect.
Analyze the findings against the AWS Well-Architected Framework and the customer's business goals.
Business goals: {business_goals}

Return ONLY a valid JSON array. Each object must have:
id, title, description, pillar (cost|security|performance|resilience),
level (resource|application|architecture), severity (critical|high|medium|low),
priority_score (0-100), estimated_monthly_savings_usd (number or null),
trade_offs (array of strings), related_findings (array of finding ids),
business_goal_alignment (string).
Do NOT include remediations yet.
"""
    try:
        raw = call_bedrock(system, f"Findings:\n{findings_json}")
        recs_raw = extract_json(raw)
        print(f"  → Bedrock produced {len(recs_raw)} recommendations\n")

        recommendations = []
        for r in recs_raw:
            recommendations.append(
                Recommendation(
                    id=r.get("id", str(__import__("uuid").uuid4())),
                    title=r["title"],
                    description=r["description"],
                    pillar=Pillar(r["pillar"]),
                    level=Level(r.get("level", "resource")),
                    severity=Severity(r["severity"]),
                    priority_score=float(r.get("priority_score", 50)),
                    estimated_monthly_savings_usd=r.get("estimated_monthly_savings_usd"),
                    trade_offs=r.get("trade_offs", []),
                    related_findings=r.get("related_findings", []),
                    business_goal_alignment=r.get("business_goal_alignment", ""),
                    remediations=[],
                )
            )
    except Exception as exc:
        print(f"  → Bedrock unavailable ({exc}). Falling back to deterministic engine.\n")
        recommendations = analyze_and_prioritize(findings, business_goals)

    # Node 3 – Remediation (try Bedrock, fall back to rules)
    print("▶ Node 3 – Generate remediation...")
    try:
        recs_for_llm = [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "pillar": r.pillar.value,
            }
            for r in recommendations
        ]
        system_rem = (
            "For each recommendation produce practical remediation artefacts. "
            "Return a JSON object keyed by recommendation id. Each value is a list of "
            "objects with keys: type (terraform|cli|console|ssm), title, content, "
            "estimated_effort, risk_if_applied. Prefer short, copy-pasteable code."
        )
        raw_rem = call_bedrock(system_rem, json.dumps(recs_for_llm, indent=2))
        rem_map = extract_json(raw_rem)
        for rec in recommendations:
            if rec.id in rem_map:
                rec.remediations = [
                    Remediation(**item) for item in rem_map[rec.id]
                ]
            else:
                rec.remediations = generate_remediations(rec)
        print("  → Used Bedrock-generated remediations\n")
    except Exception:
        for rec in recommendations:
            rec.remediations = generate_remediations(rec)
        print("  → Used rule-based remediations\n")

    # Node 4 – Finalize
    print("▶ Node 4 – Finalize...")
    recommendations.sort(key=lambda r: r.priority_score, reverse=True)
    print("  → Done\n")

    # Output (same format as v1)
    print("-" * 70)
    print("PRIORITIZED RECOMMENDATIONS")
    print("-" * 70)
    for i, rec in enumerate(recommendations, 1):
        savings = (
            f"${rec.estimated_monthly_savings_usd:.0f}/mo"
            if rec.estimated_monthly_savings_usd
            else "n/a"
        )
        print(
            f"\n{i}. [{rec.priority_score:.0f}] {rec.pillar.value.upper():12} "
            f"| {rec.severity.value:8} | savings: {savings}"
        )
        print(f"   {rec.title}")
        print(f"   {rec.description[:110]}...")
        print("   Remediations:")
        for rem in rec.remediations:
            print(f"     • ({rem.type}) {rem.title}")

    result = {
        "account_ids": account_ids,
        "business_goals": business_goals,
        "findings_count": len(findings),
        "recommendations": [
            {
                **asdict(r),
                "pillar": r.pillar.value,
                "level": r.level.value,
                "severity": r.severity.value,
                "remediations": [asdict(rem) for rem in r.remediations],
            }
            for r in recommendations
        ],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open Well-Architected Agent – v2 (Amazon Bedrock)"
    )
    parser.add_argument("--account", "-a", action="append", dest="accounts", default=["123456789012"])
    parser.add_argument("--demo", action="store_true", default=True)
    parser.add_argument(
        "--goals", "-g",
        default=(
            "Prioritize cost savings while maintaining high availability "
            "for production workloads and strong security posture."
        ),
    )
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    result = run_bedrock_agent(
        account_ids=args.accounts,
        business_goals=args.goals,
        demo=args.demo,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nFull JSON written to {args.output}")


if __name__ == "__main__":
    main()
