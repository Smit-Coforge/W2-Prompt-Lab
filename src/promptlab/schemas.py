from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TaskName = Literal["triage", "summarization", "extraction"]
FieldStatus = Literal["present", "absent", "ambiguous"]
DocumentStatus = Literal["valid", "contradictory", "superseded", "unsupported"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceField(StrictModel):
    value: str | list[str] | None
    status: FieldStatus
    citation: str | None = None


class TriageOutput(StrictModel):
    queue: Literal[
        "card_dispute",
        "fraud_report",
        "account_servicing",
        "lending",
        "complaint",
        "escalate",
        "unsupported",
    ]
    escalation_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    draft_reply: str
    human_review_required: Literal[True]
    customer_outcome: None = None


class SummarizationOutput(StrictModel):
    document_status: DocumentStatus
    title: EvidenceField
    version: EvidenceField
    effective_date: EvidenceField
    purpose: EvidenceField
    required_steps: EvidenceField
    exceptions: EvidenceField

    def evidence_fields(self) -> dict[str, EvidenceField]:
        return {
            "title": self.title,
            "version": self.version,
            "effective_date": self.effective_date,
            "purpose": self.purpose,
            "required_steps": self.required_steps,
            "exceptions": self.exceptions,
        }


class PolicyExtraction(StrictModel):
    document_status: DocumentStatus
    policy_name: EvidenceField
    version: EvidenceField
    effective_date: EvidenceField
    jurisdictions: EvidenceField
    beneficial_ownership_threshold: EvidenceField
    review_frequency: EvidenceField
    required_documents: EvidenceField

    def evidence_fields(self) -> dict[str, EvidenceField]:
        return {
            "policy_name": self.policy_name,
            "version": self.version,
            "effective_date": self.effective_date,
            "jurisdictions": self.jurisdictions,
            "beneficial_ownership_threshold": self.beneficial_ownership_threshold,
            "review_frequency": self.review_frequency,
            "required_documents": self.required_documents,
        }


OUTPUT_SCHEMAS: dict[TaskName, type[StrictModel]] = {
    "triage": TriageOutput,
    "summarization": SummarizationOutput,
    "extraction": PolicyExtraction,
}


def schema_description(model: type[BaseModel]) -> str:
    """Return a compact field map derived from the supplied Pydantic model."""
    schema: dict[str, Any] = model.model_json_schema()
    defs = schema.get("$defs", {})
    fields: dict[str, Any] = {}
    for name, spec in schema.get("properties", {}).items():
        if not isinstance(spec, dict):
            continue
        ref_name = str(spec.get("$ref", "")).rsplit("/", 1)[-1]
        if isinstance(defs, dict) and ref_name in defs:
            nested: dict[str, Any] = {}
            for key, prop in defs[ref_name].get("properties", {}).items():
                if not isinstance(prop, dict):
                    continue
                if "enum" in prop:
                    nested[key] = " | ".join(str(value) for value in prop["enum"])
                elif "anyOf" in prop:
                    nested[key] = " | ".join(
                        str(option.get("type", "value"))
                        for option in prop["anyOf"]
                        if isinstance(option, dict)
                    )
                else:
                    nested[key] = prop.get("type", "value")
            fields[name] = nested
        elif "enum" in spec:
            fields[name] = " | ".join(str(value) for value in spec["enum"])
        else:
            fields[name] = spec.get("type", "value")
    return json.dumps(fields, indent=2)

