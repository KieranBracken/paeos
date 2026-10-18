"""Canonical Structural Question Sensor Pack (PAEOS Doctrine §12 / WF-STR-01..12).

Implements estate-wide structural diagnostic inquiries auditing fundamental
engineering safety, authority, provenance, non-vacuity, and state boundaries.
"""

from __future__ import annotations

import re
from typing import Any

from runtime.autonomy.weakness_finder.types import (
    FindingSeverity,
    SensorFinding,
    WeaknessCategory,
)


from pathlib import Path

def _extract_text(context: Any) -> str | None:
    if isinstance(context, str):
        return context
    if isinstance(context, Path):
        try:
            return context.read_text(encoding="utf-8")
        except Exception:
            return None
    if isinstance(context, dict):
        if "source_code" in context and isinstance(context["source_code"], str):
            return context["source_code"]
    return None


class StructuralQuestionSensorPack:
    """Sensor pack executing the 12 canonical structural inquiries from Doctrine §12."""

    name: str = "StructuralQuestionSensorPack"
    category: WeaknessCategory = WeaknessCategory.MDG_STRUCTURAL

    def scan(self, context: Any) -> list[SensorFinding]:
        findings: list[SensorFinding] = []
        probes = [
            self.probe_wf_str_01_unverified_model_assertion,
            self.probe_wf_str_02_invalid_state_possible,
            self.probe_wf_str_03_prose_only_policy,
            self.probe_wf_str_04_actor_self_certification,
            self.probe_wf_str_05_capability_omission,
            self.probe_wf_str_06_non_discriminating_test,
            self.probe_wf_str_07_unreachable_integration,
            self.probe_wf_str_08_concurrency_restart_vulnerability,
            self.probe_wf_str_09_duplicated_authority,
            self.probe_wf_str_10_human_defect_escape,
            self.probe_wf_str_11_superfluous_defensive_control,
            self.probe_wf_str_12_diminishing_search_surface,
        ]
        for probe in probes:
            finding = probe(context)
            if finding is not None:
                findings.append(finding)
        return findings

    def probe_wf_str_01_unverified_model_assertion(self, context: Any) -> SensorFinding | None:
        """WF-STR-01: Where is model assertion trusted when runtime state could establish the fact?"""
        if isinstance(context, dict) and context.get("model_assertion_unverified"):
            claim = context.get("claim", "unspecified claim")
            return SensorFinding(
                finding_id="WF-STR-01",
                sensor_name=self.name,
                category=WeaknessCategory.EVIDENCE_PROVENANCE,
                severity=FindingSeverity.CRITICAL,
                title="Model Assertion Trusted Without Runtime Fact Verification",
                description=f"Model assertion '{claim}' accepted without independent physical runtime check.",
                affected_nodes=(str(context.get("task_id", "unknown")),),
                remediation_hint="Bind assertion to deterministic observation or CAS receipt.",
            )
        text = _extract_text(context)
        if text and re.search(r"(?:verdict|decision)\s*=\s*(?:resp|response)\.(?:content|text)", text):
            return SensorFinding(
                finding_id="WF-STR-01",
                sensor_name=self.name,
                category=WeaknessCategory.EVIDENCE_PROVENANCE,
                severity=FindingSeverity.CRITICAL,
                title="Model Assertion Trusted Without Runtime Fact Verification",
                description="Model output assigned directly to decision/verdict variable without schema/verifier gate.",
                affected_nodes=("model_response_assignment",),
                remediation_hint="Bind assertion to deterministic observation or CAS receipt.",
            )
        return None

    def probe_wf_str_02_invalid_state_possible(self, context: Any) -> SensorFinding | None:
        """WF-STR-02: Where can invalid state be made impossible?"""
        if isinstance(context, dict) and context.get("untyped_state_allowed"):
            field_name = context.get("field", "state_field")
            return SensorFinding(
                finding_id="WF-STR-02",
                sensor_name=self.name,
                category=WeaknessCategory.STATE_RECOVERY,
                severity=FindingSeverity.WARNING,
                title="Invalid State Possible in Open Schema",
                description=f"Field '{field_name}' permits invalid/untyped values that could be made impossible via enum.",
                affected_nodes=(field_name,),
                remediation_hint="Replace string/dict with typed frozen dataclass or enum.",
            )
        text = _extract_text(context)
        if text and re.search(r"state\s*:\s*dict\b", text):
            return SensorFinding(
                finding_id="WF-STR-02",
                sensor_name=self.name,
                category=WeaknessCategory.STATE_RECOVERY,
                severity=FindingSeverity.WARNING,
                title="Invalid State Possible in Open Schema",
                description="Open untyped dict used for state signature instead of typed frozen schema.",
                affected_nodes=("state_dict",),
                remediation_hint="Replace string/dict with typed frozen dataclass or enum.",
            )
        return None

    def probe_wf_str_03_prose_only_policy(self, context: Any) -> SensorFinding | None:
        """WF-STR-03: Where is policy expressed only in prose?"""
        if isinstance(context, dict) and context.get("prose_only_policy_detected"):
            policy_name = context.get("policy", "prose_policy")
            return SensorFinding(
                finding_id="WF-STR-03",
                sensor_name=self.name,
                category=WeaknessCategory.ARCHITECTURE_DRIFT,
                severity=FindingSeverity.WARNING,
                title="Policy Expressed Only in Prose",
                description=f"Policy requirement '{policy_name}' has no corresponding AST rule or mechanical test.",
                affected_nodes=(policy_name,),
                remediation_hint="Implement executable AST linter rule or contract test.",
            )
        text = _extract_text(context)
        if text and re.search(r"#\s*MUST\s+NOT\b", text) and not re.search(r"(?:raise|assert)\b", text):
            return SensorFinding(
                finding_id="WF-STR-03",
                sensor_name=self.name,
                category=WeaknessCategory.ARCHITECTURE_DRIFT,
                severity=FindingSeverity.WARNING,
                title="Policy Expressed Only in Prose",
                description="Prose policy comments found without executable enforcement.",
                affected_nodes=("prose_comment",),
                remediation_hint="Implement executable AST linter rule or contract test.",
            )
        return None

    def probe_wf_str_04_actor_self_certification(self, context: Any) -> SensorFinding | None:
        """WF-STR-04: Where can an actor self-certify its own output?"""
        if isinstance(context, dict):
            builder = (context.get("builder_family") or "").strip().lower()
            auditor = (context.get("auditor_family") or "").strip().lower()
            if builder and auditor and builder == auditor:
                return SensorFinding(
                    finding_id="WF-STR-04",
                    sensor_name=self.name,
                    category=WeaknessCategory.VERIFICATION_ORACLE,
                    severity=FindingSeverity.CRITICAL,
                    title="Self-Certification Invariant Violation (Builder == Auditor)",
                    description=f"Actor family '{builder}' is auditing its own output without heterogeneous review.",
                    affected_nodes=(builder,),
                    remediation_hint="Enforce Rule A-08 heterogeneous model family separation.",
                )
        return None

    def probe_wf_str_05_capability_omission(self, context: Any) -> SensorFinding | None:
        """WF-STR-05: Where can required capabilities disappear through omission?"""
        if isinstance(context, dict) and context.get("omitted_capabilities"):
            omitted = tuple(context.get("omitted_capabilities", ()))
            return SensorFinding(
                finding_id="WF-STR-05",
                sensor_name=self.name,
                category=WeaknessCategory.SEMANTIC_SCOPE,
                severity=FindingSeverity.CRITICAL,
                title="Required Capabilities Dropped Through Omission",
                description=f"Capabilities omitted from downstream contract: {', '.join(omitted)}",
                affected_nodes=omitted,
                remediation_hint="Require explicit disposition (IMPLEMENTED or DEFERRED) before freeze.",
            )
        return None

    def probe_wf_str_06_non_discriminating_test(self, context: Any) -> SensorFinding | None:
        """WF-STR-06: Where can a test pass without discriminating the intended property?"""
        if isinstance(context, dict) and context.get("test_vacuous"):
            test_id = context.get("test_id", "test_case")
            return SensorFinding(
                finding_id="WF-STR-06",
                sensor_name=self.name,
                category=WeaknessCategory.VERIFICATION_ORACLE,
                severity=FindingSeverity.CRITICAL,
                title="Non-Discriminating / Vacuous Test Detected",
                description=f"Test '{test_id}' passes vacuously without failing on broken negative controls.",
                affected_nodes=(test_id,),
                remediation_hint="Add negative CANARY control proving test fails on mutated implementation.",
            )
        return None

    def probe_wf_str_07_unreachable_integration(self, context: Any) -> SensorFinding | None:
        """WF-STR-07: Where can integration be claimed without physical reachability?"""
        if isinstance(context, dict) and context.get("phantom_integration"):
            adapter = context.get("adapter_name", "adapter")
            return SensorFinding(
                finding_id="WF-STR-07",
                sensor_name=self.name,
                category=WeaknessCategory.PRODUCTION_PATH,
                severity=FindingSeverity.CRITICAL,
                title="Unreachable Phantom Integration Claimed",
                description=f"Adapter '{adapter}' is imported only in tests or lacks live production reachability.",
                affected_nodes=(adapter,),
                remediation_hint="Verify live end-to-end event trail on production lifecycle path.",
            )
        return None

    def probe_wf_str_08_concurrency_restart_vulnerability(self, context: Any) -> SensorFinding | None:
        """WF-STR-08: Where can restart, concurrency, stale state, or partial failure violate invariants?"""
        if isinstance(context, dict) and context.get("missing_fencing_token"):
            task_id = context.get("task_id", "task")
            return SensorFinding(
                finding_id="WF-STR-08",
                sensor_name=self.name,
                category=WeaknessCategory.STATE_RECOVERY,
                severity=FindingSeverity.WARNING,
                title="Missing Monotonic Fencing Token on Resumed Task",
                description=f"Task '{task_id}' state mutation lacks monotonic fence; split-brain risk.",
                affected_nodes=(task_id,),
                remediation_hint="Acquire lease with next monotonic fencing token before resuming.",
            )
        return None

    def probe_wf_str_09_duplicated_authority(self, context: Any) -> SensorFinding | None:
        """WF-STR-09: Where does duplicated authority exist?"""
        if isinstance(context, dict) and context.get("duplicate_authority_detected"):
            auth_a = context.get("authority_a", "auth_a")
            auth_b = context.get("authority_b", "auth_b")
            return SensorFinding(
                finding_id="WF-STR-09",
                sensor_name=self.name,
                category=WeaknessCategory.AUTHORITY_ENVELOPE,
                severity=FindingSeverity.WARNING,
                title="Duplicated Decision Authority Detected",
                description=f"Overlapping decision authorities between '{auth_a}' and '{auth_b}'.",
                affected_nodes=(auth_a, auth_b),
                remediation_hint="Consolidate authority into single narrow waist or reference monitor.",
            )
        return None

    def probe_wf_str_10_human_defect_escape(self, context: Any) -> SensorFinding | None:
        """WF-STR-10: Where are humans discovering defects PAEOS should have discovered?"""
        if isinstance(context, dict) and context.get("human_discovered_defect"):
            defect_desc = context.get("defect_summary", "escaped defect")
            return SensorFinding(
                finding_id="WF-STR-10",
                sensor_name=self.name,
                category=WeaknessCategory.COMPLETENESS,
                severity=FindingSeverity.WARNING,
                title="Human-Discovered Defect Escaped Automated Canaries",
                description=f"Defect '{defect_desc}' required human remand rather than automated detection.",
                affected_nodes=(defect_desc,),
                remediation_hint="Author dedicated CANARY test reproducing the escaped defect condition.",
            )
        return None

    def probe_wf_str_11_superfluous_defensive_control(self, context: Any) -> SensorFinding | None:
        """WF-STR-11: Where are controls being added around a choice/state that could simply be removed?"""
        if isinstance(context, dict) and context.get("superfluous_control_detected"):
            control_id = context.get("control_id", "wrapper")
            return SensorFinding(
                finding_id="WF-STR-11",
                sensor_name=self.name,
                category=WeaknessCategory.ARCHITECTURE_DRIFT,
                severity=FindingSeverity.ADVISORY,
                title="Superfluous Defensive Wrapper Around Removable State",
                description=f"Defensive wrapper '{control_id}' protects against a state that should be eliminated.",
                affected_nodes=(control_id,),
                remediation_hint="Refactor to eliminate invalid state at compile-time instead of runtime guards.",
            )
        return None

    def probe_wf_str_12_diminishing_search_surface(self, context: Any) -> SensorFinding | None:
        """WF-STR-12: Where has the current architectural search surface reached diminishing returns?"""
        if isinstance(context, dict) and context.get("diminishing_returns_churn"):
            branch = context.get("branch_id", "branch")
            churn_count = context.get("churn_count", 0)
            return SensorFinding(
                finding_id="WF-STR-12",
                sensor_name=self.name,
                category=WeaknessCategory.REASONING_RESOURCE,
                severity=FindingSeverity.ADVISORY,
                title="Diminishing Returns on Architectural Search Surface",
                description=f"Branch '{branch}' has churned {churn_count} times without finding viable solution.",
                affected_nodes=(branch,),
                remediation_hint="Consolidate branch and re-evaluate at higher architectural abstraction level.",
            )
        return None
