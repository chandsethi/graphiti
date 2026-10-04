"""
Unit tests for kind-aware edge resolution.

Tests the different resolution rules for facts, plans, and ideas.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EpisodicNode
from graphiti_core.prompts.dedupe_edges import EdgeDuplicate
from graphiti_core.utils.maintenance.edge_operations import (
    resolve_edge_contradictions,
    resolve_extracted_edge,
)


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns deterministic responses."""
    client = AsyncMock()

    # Default: no duplicates, no contradictions
    client.generate_response = AsyncMock(
        return_value={
            'duplicate_facts': [],
            'contradicted_facts': [],
            'is_correction': False,
        }
    )
    return client


@pytest.fixture
def mock_episode():
    """Create a mock episode for testing."""
    from graphiti_core.nodes import EpisodeType

    return EpisodicNode(
        uuid=str(uuid4()),
        name='Test Episode',
        group_id='test_group',
        source=EpisodeType.text,
        source_description='test',
        content='test content',
        valid_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )


def create_edge(
    kind: str = 'fact',
    fact: str = 'test fact',
    uuid: str | None = None,
    source: str | None = None,
    target: str | None = None,
) -> EntityEdge:
    """Helper to create a test edge."""
    return EntityEdge(
        uuid=uuid or str(uuid4()),
        source_node_uuid=source or str(uuid4()),
        target_node_uuid=target or str(uuid4()),
        name='TEST_RELATION',
        fact=fact,
        kind=kind,
        group_id='test_group',
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_fact_correction_invalidates_old_fact(mock_llm_client, mock_episode):
    """Test that a fact correction invalidates the old fact."""
    old_fact = create_edge(kind='fact', fact='Alice works at Company A')
    new_fact = create_edge(kind='fact', fact='Alice works at Company B')

    # Mock LLM to return a contradiction that is a correction
    mock_llm_client.generate_response = AsyncMock(
        return_value={
            'duplicate_facts': [],
            'contradicted_facts': [0],
            'is_correction': True,
        }
    )

    resolved, invalidated, _ = await resolve_extracted_edge(
        mock_llm_client,
        new_fact,
        related_edges=[old_fact],
        existing_edges=[],
        episode=mock_episode,
    )

    assert len(invalidated) == 1
    assert invalidated[0].uuid == old_fact.uuid
    assert invalidated[0].invalid_at is not None
    assert invalidated[0].expired_at is not None
    assert old_fact.conflicts_with == []  # Not a conflict, an invalidation


@pytest.mark.asyncio
async def test_fact_conflict_keeps_both_and_marks_conflict(mock_llm_client, mock_episode):
    """Test that contradictory facts keep both and mark them as conflicting."""
    source1 = create_edge(kind='fact', fact='Source 1 says the capital is City A')
    source2 = create_edge(kind='fact', fact='Source 2 says the capital is City B')

    # Mock LLM to return a contradiction that is NOT a correction
    mock_llm_client.generate_response = AsyncMock(
        return_value={
            'duplicate_facts': [],
            'contradicted_facts': [0],
            'is_correction': False,
        }
    )

    resolved, invalidated, _ = await resolve_extracted_edge(
        mock_llm_client,
        source2,
        related_edges=[source1],
        existing_edges=[],
        episode=mock_episode,
    )

    # Both edges are kept, but marked as conflicting
    assert len(invalidated) == 1
    assert invalidated[0].uuid == source1.uuid
    assert source1.uuid in source2.conflicts_with
    assert source2.uuid in source1.conflicts_with


@pytest.mark.asyncio
async def test_plan_supersedes_older_plan(mock_llm_client, mock_episode):
    """Test that a new plan supersedes an older plan."""
    old_plan = create_edge(kind='plan', fact='Bob plans to interview candidates on Tuesday')
    new_plan = create_edge(kind='plan', fact='Bob plans to interview candidates on Friday')

    # Mock LLM to return a contradiction for plans
    mock_llm_client.generate_response = AsyncMock(
        return_value={
            'duplicate_facts': [],
            'contradicted_facts': [0],
            'is_correction': True,
        }
    )

    resolved, invalidated, _ = await resolve_extracted_edge(
        mock_llm_client,
        new_plan,
        related_edges=[old_plan],
        existing_edges=[],
        episode=mock_episode,
    )

    assert len(invalidated) == 1
    assert invalidated[0].uuid == old_plan.uuid
    assert invalidated[0].superseded_by == new_plan.uuid
    assert invalidated[0].invalid_at is not None
    assert invalidated[0].expired_at is not None


@pytest.mark.asyncio
async def test_idea_never_invalidates_fact(mock_llm_client, mock_episode):
    """Test that an idea never invalidates a fact."""
    fact = create_edge(kind='fact', fact='Alice works at Company A')
    idea = create_edge(kind='idea', fact='Alice is considering switching to Company B')

    # Mock LLM to return no contradictions (as expected for idea vs fact)
    mock_llm_client.generate_response = AsyncMock(
        return_value={
            'duplicate_facts': [],
            'contradicted_facts': [],
            'is_correction': False,
        }
    )

    resolved, invalidated, _ = await resolve_extracted_edge(
        mock_llm_client,
        idea,
        related_edges=[fact],
        existing_edges=[],
        episode=mock_episode,
    )

    assert len(invalidated) == 0


@pytest.mark.asyncio
async def test_fact_never_invalidates_idea(mock_llm_client, mock_episode):
    """Test that a fact never invalidates an idea."""
    idea = create_edge(kind='idea', fact='Bob might travel to Japan')
    fact = create_edge(kind='fact', fact='Bob will travel to France')

    # Mock LLM to return no contradictions (as expected for fact vs idea)
    mock_llm_client.generate_response = AsyncMock(
        return_value={
            'duplicate_facts': [],
            'contradicted_facts': [],
            'is_correction': False,
        }
    )

    resolved, invalidated, _ = await resolve_extracted_edge(
        mock_llm_client,
        fact,
        related_edges=[idea],
        existing_edges=[],
        episode=mock_episode,
    )

    assert len(invalidated) == 0


@pytest.mark.asyncio
async def test_idea_can_duplicate_identical_idea(mock_llm_client, mock_episode):
    """Test that an idea can duplicate another identical idea."""
    idea1 = create_edge(kind='idea', fact='The team discussed possibly trying React')
    idea2 = create_edge(kind='idea', fact='The team discussed possibly trying React')

    # Mock LLM to return a duplicate
    mock_llm_client.generate_response = AsyncMock(
        return_value={
            'duplicate_facts': [0],
            'contradicted_facts': [],
            'is_correction': False,
        }
    )

    resolved, invalidated, duplicates = await resolve_extracted_edge(
        mock_llm_client,
        idea2,
        related_edges=[idea1],
        existing_edges=[],
        episode=mock_episode,
    )

    assert resolved.uuid == idea1.uuid  # Resolved to the existing idea
    assert len(duplicates) == 1
    assert len(invalidated) == 0


def test_resolve_edge_contradictions_fact_correction():
    """Test that fact corrections invalidate old facts."""
    old_fact = create_edge(kind='fact', fact='Old fact')
    new_fact = create_edge(kind='fact', fact='New fact')

    invalidated = resolve_edge_contradictions(new_fact, [old_fact], is_correction=True)

    assert len(invalidated) == 1
    assert invalidated[0].uuid == old_fact.uuid
    assert invalidated[0].invalid_at is not None


def test_resolve_edge_contradictions_fact_conflict():
    """Test that fact conflicts mark both as conflicting."""
    fact1 = create_edge(kind='fact', fact='Fact from source 1')
    fact2 = create_edge(kind='fact', fact='Fact from source 2')

    invalidated = resolve_edge_contradictions(fact2, [fact1], is_correction=False)

    assert len(invalidated) == 1
    assert fact1.uuid in fact2.conflicts_with
    assert fact2.uuid in fact1.conflicts_with


def test_resolve_edge_contradictions_plan_supersedes():
    """Test that new plans supersede old plans."""
    old_plan = create_edge(kind='plan', fact='Old plan')
    new_plan = create_edge(kind='plan', fact='New plan')

    invalidated = resolve_edge_contradictions(new_plan, [old_plan], is_correction=True)

    assert len(invalidated) == 1
    assert invalidated[0].superseded_by == new_plan.uuid
    assert invalidated[0].invalid_at is not None


def test_resolve_edge_contradictions_idea_never_conflicts():
    """Test that ideas never conflict with anything."""
    fact = create_edge(kind='fact', fact='A fact')
    idea = create_edge(kind='idea', fact='An idea')

    # Idea as new edge
    invalidated = resolve_edge_contradictions(idea, [fact], is_correction=False)
    assert len(invalidated) == 0

    # Idea as existing edge
    invalidated = resolve_edge_contradictions(fact, [idea], is_correction=False)
    assert len(invalidated) == 0
