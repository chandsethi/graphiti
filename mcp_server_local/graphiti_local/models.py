"""Data models for Graphiti Local."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc)


class MemoryKind(str, Enum):
    """The type of knowledge stored in a memory."""

    FACT = 'fact'
    PLAN = 'plan'
    IDEA = 'idea'


class PlanStatus(str, Enum):
    """Status of a plan."""

    PROPOSED = 'proposed'
    ACTIVE = 'active'
    DONE = 'done'
    DROPPED = 'dropped'


class Entity(BaseModel):
    """An entity in the knowledge graph."""

    uuid: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    entity_type: str
    summary: str = ''
    created_at: datetime = Field(default_factory=utc_now)
    group_id: str = 'default'


class Relationship(BaseModel):
    """A relationship between two entities."""

    uuid: str = Field(default_factory=lambda: str(uuid4()))
    source_entity: str  # entity name or uuid
    target_entity: str  # entity name or uuid
    fact: str
    kind: MemoryKind
    tags: list[str] = Field(default_factory=list)
    valid_at: datetime = Field(default_factory=utc_now)
    invalid_at: datetime | None = None
    superseded_by: str | None = None
    plan_status: PlanStatus | None = None
    plan_owner: str | None = None
    plan_due_date: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    group_id: str = 'default'
    conflict_flagged: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)


class AddMemoryRequest(BaseModel):
    """Request to add a new memory."""

    entities: list[dict[str, str]]  # [{"name": "X", "type": "Person", "summary": "..."}]
    relationships: list[dict[str, Any]]  # [{"source": "X", "target": "Y", "fact": "...", ...}]
    kind: MemoryKind
    tags: list[str] = Field(default_factory=list)
    group_id: str = 'default'
    reference_time: datetime | None = None
    plan_status: PlanStatus | None = None
    plan_owner: str | None = None
    plan_due_date: datetime | None = None


class SearchMemoryRequest(BaseModel):
    """Request to search memories."""

    query: str
    kind: MemoryKind | None = None
    tags: list[str] | None = None
    entity_type: str | None = None
    entity_name: str | None = None
    valid_after: datetime | None = None
    valid_before: datetime | None = None
    include_superseded: bool = False
    limit: int = 10
    group_id: str = 'default'


class UpdatePlanStatusRequest(BaseModel):
    """Request to update a plan's status."""

    relationship_uuid: str
    status: PlanStatus
    group_id: str = 'default'


class SupersedePlanRequest(BaseModel):
    """Request to supersede an old plan with a new one."""

    old_relationship_uuid: str
    new_relationship: dict[str, Any]
    group_id: str = 'default'


class PromoteIdeaRequest(BaseModel):
    """Request to promote an idea to fact or plan."""

    relationship_uuid: str
    new_kind: MemoryKind
    plan_status: PlanStatus | None = None
    plan_owner: str | None = None
    plan_due_date: datetime | None = None
    group_id: str = 'default'


class MarkFactCorrectionRequest(BaseModel):
    """Request to flag a fact as corrected by newer information."""

    fact_uuid: str
    correcting_fact_uuid: str
    group_id: str = 'default'


class ListRecentRequest(BaseModel):
    """Request to list recent memories."""

    kind: MemoryKind | None = None
    limit: int = 20
    group_id: str = 'default'


class MemorySearchResult(BaseModel):
    """A search result."""

    relationship: Relationship
    source_entity: Entity
    target_entity: Entity
    score: float = 0.0
