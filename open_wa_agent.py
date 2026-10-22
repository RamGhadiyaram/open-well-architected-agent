#!/usr/bin/env python3
"""
Open Well-Architected Agent – Version 1 (LangGraph-style)

Complete end-to-end implementation.
Works with zero external dependencies beyond the Python standard library + rich (optional).

This file is intentionally self-contained so you can understand every line.
"""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# 1. DATA MODELS
# =============================================================================

class Pillar(str, Enum):
    COST = "cost"
    SECURITY = "security"
    PERFORMANCE = "performance"
    RESILIENCE = "resilience"


class Level(str, Enum):
    RESOURCE = "resource"
    APPLICATION = "application"
    ARCHITECTURE = "architecture"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    id: str
    source: str
    account_id: str
    region: str
    service: str
    resource_id: Optional[str]
    title: str
    description: str
    pillar: Pillar
    severity: Severity
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Remediation:
    type: str               # terraform | cli | console | ssm | cloudformation
    title: str
    content: str
    estimated_effort: str = "low"
    risk_if_applied: str = "low"


@dataclass
class Recommendation:
    id: str
    title: str
    description: str
    pillar: Pillar
    level: Level
    severity: Severity
    priority_score: float
    estimated_monthly_savings_usd: Optional[float]
    trade_offs: List[str]
    related_findings: List[str]
    business_goal_alignment: str
    remediations: List[Remediation] = field(default_factory=list)


# =============================================================================
# 2. DEMO FINDINGS (realistic synthetic data)
# =============================================================================

DEMO_FINDINGS_TEMPLATE = [
    {
        "source": "trusted_advisor",
        "service": "Amazon EC2",
        "resource_id": "i-0abc123def456",
        "title": "Underutilized Amazon EC2 Instances",
        "description": (
            "Instance i-0abc123def456 (m5.2xlarge) has average CPU < 5% "
            "and network I/O < 5 MB/s over the last 14 days. You are paying "
            "for capacity you are not using."
        ),
        "pillar": Pillar.COST,
        "severity": Severity.HIGH,
        "region": "us-east-1",
        "raw_data": {"instance_type": "m5.2xlarge", "avg_cpu": 3.2},
    },
    {
        "source": "config",
        "service": "Amazon S3",
        "resource_id": "my-logs-bucket-prod",
        "title": "S3 Bucket Missing Server-Side Encryption",
        "description": (
            "Bucket my-logs-bucket-prod does not enforce server-side encryption. "
            "Objects may be stored unencrypted at rest."
        ),
        "pillar": Pillar.SECURITY,
        "severity": Severity.HIGH,
        "region": "us-east-1",
        "raw_data": {"sse": None},
    },
    {
        "source": "trusted_advisor",
        "service": "Amazon S3",
        "resource_id": "my-logs-bucket-prod",
        "title": "Amazon S3 Bucket Versioning Not Enabled",
        "description": (
            "Bucket my-logs-bucket-prod does not have versioning enabled. "
            "This increases risk of accidental deletion or overwrite."
        ),
        "pillar": Pillar.RESILIENCE,
        "severity": Severity.MEDIUM,
        "region": "us-east-1",
        "raw_data": {"versioning": "Disabled"},
    },
    {
        "source": "config",
        "service": "Elastic Load Balancing",
        "resource_id": "app/prod-alb/50dc6c495c0c9188",
        "title": "ALB Not Using HTTPS Listener",
        "description": (
            "Application Load Balancer prod-alb only has an HTTP listener on port 80. "
            "Traffic is not encrypted in transit."
        ),
        "pillar": Pillar.SECURITY,
        "severity": Severity.CRITICAL,
        "region": "us-east-1",
        "raw_data": {"listeners": ["HTTP:80"]},
    },
    {
        "source": "cloudwatch",
        "service": "Amazon Lambda",
        "resource_id": "process-orders",
        "title": "Lambda Function with High Error Rate",
        "description": (
            "Function process-orders has a 12% error rate over the last 7 days "
            "and average duration is close to the configured timeout."
        ),
        "pillar": Pillar.PERFORMANCE,
        "severity": Severity.HIGH,
        "region": "us-east-1",
        "raw_data": {"error_rate": 0.12, "avg_duration_ms": 2800},
    },
    {
        "source": "trusted_advisor",
        "service": "Amazon EBS",
        "resource_id": "vol-0xyz789",
        "title": "Unattached EBS Volume",
        "description": (
            "Volume vol-0xyz789 (100 GB gp3) has been unattached for > 30 days "
            "and is still incurring storage charges (~$8/month)."
        ),
        "pillar": Pillar.COST,
        "severity": Severity.MEDIUM,
        "region": "us-east-1",
        "raw_data": {"size_gb": 100, "type": "gp3"},
    },
    {
        "source": "cost_explorer",
        "service": "Amazon RDS",
        "resource_id": "db-prod-mysql-01",
        "title": "RDS Instance Eligible for Reserved Instance",
        "description": (
            "db-prod-mysql-01 (db.r5.large) has been running continuously "
            "for > 90 days. A 1-year Reserved Instance could save ~40%."
        ),
        "pillar": Pillar.COST,
        "severity": Severity.MEDIUM,
        "region": "us-east-1",
        "raw_data": {"instance_class": "db.r5.large", "engine": "mysql"},
    },
]


def collect_findings(account_ids: List[str], demo: bool = True) -> List[Finding]:
    """Step 1 – Collect findings (demo data or real AWS APIs)."""
    findings: List[Finding] = []
    for account_id in account_ids:
        for item in DEMO_FINDINGS_TEMPLATE:
            findings.append(
                Finding(
                    id=str(uuid.uuid4()),
                    account_id=account_id,
                    **item,
                )
            )
    return findings


# =============================================================================
# 3. KNOWLEDGE BASE (Well-Architected best practices)
# =============================================================================

WA_KNOWLEDGE = {
    Pillar.COST: [
        "Right-size instances based on utilization metrics.",
        "Delete unattached EBS volumes and unused Elastic IPs.",
        "Use Reserved Instances or Savings Plans for steady-state workloads.",
        "Enable S3 lifecycle policies / Intelligent-Tiering.",
    ],
    Pillar.SECURITY: [
        "Enforce encryption at rest and in transit (TLS).",
        "Apply least-privilege IAM policies.",
        "Enable S3 Block Public Access.",
        "Require HTTPS on all public-facing load balancers.",
    ],
    Pillar.PERFORMANCE: [
        "Right-size Lambda memory and concurrency.",
        "Use caching layers (ElastiCache, CloudFront).",
        "Monitor and tune database queries.",
    ],
    Pillar.RESILIENCE: [
        "Deploy across multiple Availability Zones.",
        "Enable automated backups and test restores.",
        "Enable S3 versioning on critical buckets.",
        "Define RTO/RPO and practice recovery.",
    ],
}


# =============================================================================
# 4. ANALYSIS ENGINE (the "brain")
# =============================================================================

SEVERITY_SCORE = {
    Severity.CRITICAL: 95,
    Severity.HIGH: 80,
    Severity.MEDIUM: 55,
    Severity.LOW: 30,
    Severity.INFO: 10,
}


def analyze_and_prioritize(
    findings: List[Finding],
    business_goals: str,
) -> List[Recommendation]:
    """
    Step 2 – Turn raw findings into prioritized recommendations.

    This is a deterministic reasoning engine that mimics what a LangGraph
    multi-step agent would do. It is fully transparent and reproducible.
    """
    recommendations: List[Recommendation] = []
    goals_lower = business_goals.lower()

    for finding in findings:
        base_score = SEVERITY_SCORE[finding.severity]

        # Boost score when the finding matches the stated business goals
        if "cost" in goals_lower and finding.pillar == Pillar.COST:
            base_score = min(100, base_score + 15)
        if "security" in goals_lower and finding.pillar == Pillar.SECURITY:
            base_score = min(100, base_score + 10)
        if "availability" in goals_lower or "resilience" in goals_lower:
            if finding.pillar == Pillar.RESILIENCE:
                base_score = min(100, base_score + 10)

        # Estimate savings for cost findings (simple heuristic)
        savings = None
        if finding.pillar == Pillar.COST:
            if "EC2" in finding.title:
                savings = 120.0
            elif "EBS" in finding.title:
                savings = 8.0
            elif "RDS" in finding.title:
                savings = 90.0

        trade_offs = [
            "Review impact on availability and performance before applying.",
        ]
        if finding.pillar == Pillar.COST:
            trade_offs.append(
                "Right-sizing may reduce headroom for traffic spikes – "
                "consider Auto Scaling instead of a permanent downsize."
            )
        if finding.pillar == Pillar.SECURITY:
            trade_offs.append(
                "Enforcing encryption or HTTPS may require certificate "
                "management and minor application changes."
            )

        rec = Recommendation(
            id=str(uuid.uuid4()),
            title=finding.title,
            description=finding.description,
            pillar=finding.pillar,
            level=Level.RESOURCE,
            severity=finding.severity,
            priority_score=float(base_score),
            estimated_monthly_savings_usd=savings,
            trade_offs=trade_offs,
            related_findings=[finding.id],
            business_goal_alignment=(
                f"Directly addresses {finding.pillar.value} concerns "
                f"that align with the stated business goals."
            ),
            remediations=[],
        )
        recommendations.append(rec)

    recommendations.sort(key=lambda r: r.priority_score, reverse=True)
    return recommendations


# =============================================================================
# 5. REMEDIATION GENERATOR
# =============================================================================

def generate_remediations(rec: Recommendation) -> List[Remediation]:
    """Step 3 – Produce concrete, copy-pasteable fixes."""
    title = rec.title.lower()
    remediations: List[Remediation] = []

    if "s3" in title and "encryption" in title:
        remediations.append(
            Remediation(
                type="terraform",
                title="Enable default S3 server-side encryption",
                content='''resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}''',
                estimated_effort="low",
                risk_if_applied="low",
            )
        )
        remediations.append(
            Remediation(
                type="cli",
                title="AWS CLI – enable bucket encryption",
                content=(
                    "aws s3api put-bucket-encryption \\\n"
                    "  --bucket my-logs-bucket-prod \\\n"
                    "  --server-side-encryption-configuration "
                    "'{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":"
                    "{\"SSEAlgorithm\":\"AES256\"}}]}'"
                ),
                estimated_effort="low",
                risk_if_applied="low",
            )
        )

    elif "versioning" in title:
        remediations.append(
            Remediation(
                type="terraform",
                title="Enable S3 versioning",
                content='''resource "aws_s3_bucket_versioning" "logs" {
  bucket = aws_s3_bucket.logs.id
  versioning_configuration {
    status = "Enabled"
  }
}''',
                estimated_effort="low",
                risk_if_applied="low",
            )
        )

    elif "ec2" in title or "underutilized" in title:
        remediations.append(
            Remediation(
                type="cli",
                title="Inspect metrics then right-size or stop",
                content=(
                    "# 1. Confirm low utilization\n"
                    "aws cloudwatch get-metric-statistics \\\n"
                    "  --namespace AWS/EC2 \\\n"
                    "  --metric-name CPUUtilization \\\n"
                    "  --dimensions Name=InstanceId,Value=i-0abc123def456 \\\n"
                    "  --start-time 2026-10-01T00:00:00Z \\\n"
                    "  --end-time 2026-10-15T00:00:00Z \\\n"
                    "  --period 86400 \\\n"
                    "  --statistics Average\n\n"
                    "# 2. Stop the instance (or change instance type)\n"
                    "aws ec2 stop-instances --instance-ids i-0abc123def456"
                ),
                estimated_effort="medium",
                risk_if_applied="medium",
            )
        )
        remediations.append(
            Remediation(
                type="console",
                title="Right-size via EC2 Console",
                content=(
                    "1. Open EC2 → Instances → select i-0abc123def456\n"
                    "2. Actions → Instance settings → Change instance type\n"
                    "3. Choose a smaller type (e.g. m5.large) or stop the instance\n"
                    "4. Monitor application health after the change"
                ),
                estimated_effort="medium",
                risk_if_applied="medium",
            )
        )

    elif "https" in title or "alb" in title:
        remediations.append(
            Remediation(
                type="console",
                title="Add HTTPS listener on ALB",
                content=(
                    "1. Open EC2 → Load Balancers → select prod-alb\n"
                    "2. Listeners tab → Add listener\n"
                    "3. Protocol: HTTPS, Port: 443\n"
                    "4. Select an ACM certificate\n"
                    "5. Forward to the existing target group\n"
                    "6. (Optional) Redirect HTTP:80 → HTTPS:443"
                ),
                estimated_effort="medium",
                risk_if_applied="low",
            )
        )
        remediations.append(
            Remediation(
                type="terraform",
                title="HTTPS listener + redirect",
                content='''resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.prod.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.prod.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}''',
                estimated_effort="medium",
                risk_if_applied="low",
            )
        )

    elif "lambda" in title:
        remediations.append(
            Remediation(
                type="console",
                title="Investigate and fix Lambda errors",
                content=(
                    "1. Open Lambda → process-orders → Monitor tab\n"
                    "2. Check CloudWatch Logs for the error pattern\n"
                    "3. Increase memory / timeout if duration is the issue\n"
                    "4. Add proper error handling and dead-letter queue\n"
                    "5. Re-deploy and verify error rate drops"
                ),
                estimated_effort="high",
                risk_if_applied="medium",
            )
        )

    elif "ebs" in title or "unattached" in title:
        remediations.append(
            Remediation(
                type="cli",
                title="Snapshot then delete unattached volume",
                content=(
                    "# Create a final snapshot for safety\n"
                    "aws ec2 create-snapshot \\\n"
                    "  --volume-id vol-0xyz789 \\\n"
                    "  --description \"Final snapshot before deletion\"\n\n"
                    "# Delete the volume\n"
                    "aws ec2 delete-volume --volume-id vol-0xyz789"
                ),
                estimated_effort="low",
                risk_if_applied="low",
            )
        )

    elif "rds" in title or "reserved" in title:
        remediations.append(
            Remediation(
                type="console",
                title="Purchase RDS Reserved Instance",
                content=(
                    "1. Open RDS → Reserved Instances → Purchase reserved DB instance\n"
                    "2. Select the same engine, instance class (db.r5.large) and region\n"
                    "3. Choose 1-year term (All Upfront or Partial Upfront)\n"
                    "4. Review savings estimate and purchase"
                ),
                estimated_effort="low",
                risk_if_applied="low",
            )
        )

    if not remediations:
        remediations.append(
            Remediation(
                type="console",
                title="Manual review in AWS Console",
                content=(
                    f"1. Open the AWS Console for the related service\n"
                    f"2. Locate the resource mentioned in the finding\n"
                    f"3. Apply the configuration change suggested by the title\n"
                    f"4. Validate in a non-production environment first"
                ),
                estimated_effort="medium",
                risk_if_applied="medium",
            )
        )

    return remediations


# =============================================================================
# 6. MAIN PIPELINE (the LangGraph-style flow)
# =============================================================================

def run_agent(
    account_ids: List[str],
    business_goals: str,
    demo: bool = True,
) -> Dict[str, Any]:
    """
    End-to-end pipeline that mirrors a LangGraph multi-node agent:

        collect → analyze → remediate → finalize
    """
    print("=" * 70)
    print("  Open Well-Architected Agent  –  v1 (LangGraph-style)")
    print("=" * 70)
    print(f"Accounts      : {', '.join(account_ids)}")
    print(f"Demo mode     : {demo}")
    print(f"Business goals: {business_goals}")
    print()

    print("▶ Node 1 – Collect findings...")
    findings = collect_findings(account_ids, demo=demo)
    print(f"  → Collected {len(findings)} findings\n")

    print("▶ Node 2 – Analyze against Well-Architected + business goals...")
    recommendations = analyze_and_prioritize(findings, business_goals)
    print(f"  → Produced {len(recommendations)} prioritized recommendations\n")

    print("▶ Node 3 – Generate ready-to-use remediation...")
    for rec in recommendations:
        rec.remediations = generate_remediations(rec)
    print(f"  → Attached remediation artefacts to all recommendations\n")

    print("▶ Node 4 – Finalize & sort by priority...")
    recommendations.sort(key=lambda r: r.priority_score, reverse=True)
    print("  → Done\n")

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
        print(f"   Trade-offs: {rec.trade_offs[0]}")
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


# =============================================================================
# 7. CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open Well-Architected Agent – v1 (LangGraph-style)"
    )
    parser.add_argument(
        "--account", "-a",
        action="append",
        dest="accounts",
        default=["123456789012"],
        help="AWS account ID(s)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        default=True,
        help="Use synthetic demo findings (default: True)",
    )
    parser.add_argument(
        "--goals", "-g",
        default=(
            "Prioritize cost savings while maintaining high availability "
            "for production workloads and strong security posture."
        ),
        help="Business goals that drive prioritization",
    )
    parser.add_argument(
        "--output", "-o",
        help="Write full JSON result to this file",
    )
    args = parser.parse_args()

    result = run_agent(
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
