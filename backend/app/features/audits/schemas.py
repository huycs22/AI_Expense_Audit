from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REPORT_VERSION = "v10-focused-cross-review"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    severity: Literal["high", "medium", "low"]
    kind: Literal["numerical", "evidence", "policy"]
    title: str
    explanation: str
    observation_ids: list[str] = Field(min_length=1)
    calculation_ids: list[str] = Field(default_factory=list)
    check_ids: list[str] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list)


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_document: str
    to_document: str
    status: Literal["supported", "conflicting", "unresolved"]
    observation_ids: list[str]
    explanation: str


class AuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[Finding]
    assessed_topics: list[str]
    unresolved_checks: list[str]
    not_applicable_topics: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)


class RelationshipResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    links: list[Link] = Field(max_length=6)
