"""Test that no network or API calls are made."""

import socket
from unittest.mock import patch

import pytest

from graphiti_local.models import Entity, MemoryKind, PlanStatus, Relationship
from graphiti_local.storage import LocalStorage


def block_network(*args, **kwargs):
    """Block all network calls."""
    raise RuntimeError('Network call attempted! API keys are not allowed.')


@pytest.fixture(autouse=True)
def no_network():
    """Block all socket calls to ensure no network access."""
    with patch('socket.socket', side_effect=block_network):
        with patch('socket.create_connection', side_effect=block_network):
            yield


def test_add_fact_no_api_calls(storage: LocalStorage):
    """Test adding a fact without any API calls."""
    user = Entity(name='Alice', entity_type='Person', summary='A user', group_id='test')
    tech = Entity(name='Python', entity_type='Technology', summary='A language', group_id='test')

    storage.add_entity(user)
    storage.add_entity(tech)

    fact = Relationship(
        source_entity='Alice',
        target_entity='Python',
        fact='Alice prefers Python for backend development',
        kind=MemoryKind.FACT,
        tags=['tech', 'preference'],
        group_id='test',
    )

    result = storage.add_relationship(fact)
    assert result.uuid
    assert result.kind == MemoryKind.FACT


def test_add_plan_no_api_calls(storage: LocalStorage):
    """Test adding a plan without any API calls."""
    team = Entity(name='Engineering Team', entity_type='Organization', group_id='test')
    api = Entity(name='REST API', entity_type='System', group_id='test')

    storage.add_entity(team)
    storage.add_entity(api)

    plan = Relationship(
        source_entity='Engineering Team',
        target_entity='REST API',
        fact='Migrate REST API to FastAPI by Q2',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        plan_owner='Alice',
        tags=['migration', 'api'],
        group_id='test',
    )

    result = storage.add_relationship(plan)
    assert result.uuid
    assert result.kind == MemoryKind.PLAN
    assert result.plan_status == PlanStatus.ACTIVE


def test_add_idea_no_api_calls(storage: LocalStorage):
    """Test adding an idea without any API calls."""
    ui = Entity(name='Frontend', entity_type='System', group_id='test')
    tech = Entity(name='HTMX', entity_type='Technology', group_id='test')

    storage.add_entity(ui)
    storage.add_entity(tech)

    idea = Relationship(
        source_entity='Frontend',
        target_entity='HTMX',
        fact='What if we used HTMX instead of React?',
        kind=MemoryKind.IDEA,
        tags=['frontend', 'exploration'],
        group_id='test',
    )

    result = storage.add_relationship(idea)
    assert result.uuid
    assert result.kind == MemoryKind.IDEA


def test_search_no_api_calls(storage: LocalStorage):
    """Test search without any API calls (no embeddings)."""
    user = Entity(name='Bob', entity_type='Person', group_id='test')
    tech = Entity(name='JavaScript', entity_type='Technology', group_id='test')

    storage.add_entity(user)
    storage.add_entity(tech)

    fact = Relationship(
        source_entity='Bob',
        target_entity='JavaScript',
        fact='Bob dislikes JavaScript for large projects',
        kind=MemoryKind.FACT,
        tags=['tech', 'opinion'],
        group_id='test',
    )
    storage.add_relationship(fact)

    results = storage.search_relationships(
        query='JavaScript projects',
        kind=MemoryKind.FACT,
        group_id='test',
        limit=10,
    )

    assert len(results) > 0
    rel, source, target = results[0]
    assert 'JavaScript' in rel.fact


def test_supersede_plan_no_api_calls(storage: LocalStorage):
    """Test superseding a plan without any API calls."""
    team = Entity(name='Team', entity_type='Organization', group_id='test')
    project = Entity(name='Project', entity_type='System', group_id='test')

    storage.add_entity(team)
    storage.add_entity(project)

    old_plan = Relationship(
        source_entity='Team',
        target_entity='Project',
        fact='Complete project by Q1',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        group_id='test',
    )
    old_plan = storage.add_relationship(old_plan)

    new_plan = Relationship(
        source_entity='Team',
        target_entity='Project',
        fact='Complete project by Q2',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        group_id='test',
    )
    new_plan = storage.add_relationship(new_plan)

    old_plan.superseded_by = new_plan.uuid
    storage.update_relationship(old_plan)

    result = storage.get_relationship(old_plan.uuid)
    assert result is not None
    rel, _, _ = result
    assert rel.superseded_by == new_plan.uuid


def test_promote_idea_no_api_calls(storage: LocalStorage):
    """Test promoting an idea without any API calls."""
    system = Entity(name='System', entity_type='System', group_id='test')
    feature = Entity(name='Feature', entity_type='Concept', group_id='test')

    storage.add_entity(system)
    storage.add_entity(feature)

    idea = Relationship(
        source_entity='System',
        target_entity='Feature',
        fact='Add dark mode support',
        kind=MemoryKind.IDEA,
        group_id='test',
    )
    idea = storage.add_relationship(idea)

    idea.kind = MemoryKind.PLAN
    idea.plan_status = PlanStatus.PROPOSED
    storage.update_relationship(idea)

    result = storage.get_relationship(idea.uuid)
    assert result is not None
    rel, _, _ = result
    assert rel.kind == MemoryKind.PLAN
    assert rel.plan_status == PlanStatus.PROPOSED


def test_mark_fact_correction_no_api_calls(storage: LocalStorage):
    """Test marking a fact as corrected without any API calls."""
    user = Entity(name='Charlie', entity_type='Person', group_id='test')
    city = Entity(name='City', entity_type='Location', group_id='test')

    storage.add_entity(user)
    storage.add_entity(city)

    old_fact = Relationship(
        source_entity='Charlie',
        target_entity='City',
        fact='Charlie lives in New York',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    old_fact = storage.add_relationship(old_fact)

    city2 = Entity(name='San Francisco', entity_type='Location', group_id='test')
    storage.add_entity(city2)

    new_fact = Relationship(
        source_entity='Charlie',
        target_entity='San Francisco',
        fact='Charlie lives in San Francisco',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    new_fact = storage.add_relationship(new_fact)

    old_fact.conflict_flagged = True
    old_fact.attributes['corrected_by'] = new_fact.uuid
    storage.update_relationship(old_fact)

    result = storage.get_relationship(old_fact.uuid)
    assert result is not None
    rel, _, _ = result
    assert rel.conflict_flagged is True
    assert rel.attributes['corrected_by'] == new_fact.uuid


def test_list_recent_no_api_calls(storage: LocalStorage):
    """Test listing recent memories without any API calls."""
    for i in range(5):
        entity1 = Entity(name=f'Entity{i}A', entity_type='Test', group_id='test')
        entity2 = Entity(name=f'Entity{i}B', entity_type='Test', group_id='test')
        storage.add_entity(entity1)
        storage.add_entity(entity2)

        rel = Relationship(
            source_entity=entity1.name,
            target_entity=entity2.name,
            fact=f'Test fact {i}',
            kind=MemoryKind.FACT,
            group_id='test',
        )
        storage.add_relationship(rel)

    results = storage.list_recent(kind=MemoryKind.FACT, limit=3, group_id='test')
    assert len(results) == 3


def test_entity_neighborhood_no_api_calls(storage: LocalStorage):
    """Test getting entity neighborhood without any API calls."""
    center = Entity(name='CenterEntity', entity_type='Person', group_id='test')
    storage.add_entity(center)

    for i in range(3):
        other = Entity(name=f'Other{i}', entity_type='Person', group_id='test')
        storage.add_entity(other)

        rel = Relationship(
            source_entity='CenterEntity',
            target_entity=other.name,
            fact=f'CenterEntity knows Other{i}',
            kind=MemoryKind.FACT,
            group_id='test',
        )
        storage.add_relationship(rel)

    entity, relationships = storage.get_entity_neighborhood('CenterEntity', group_id='test')
    assert entity.name == 'CenterEntity'
    assert len(relationships) == 3


def test_clear_all_no_api_calls(storage: LocalStorage):
    """Test clearing all data without any API calls."""
    user = Entity(name='TestUser', entity_type='Person', group_id='test')
    storage.add_entity(user)

    other = Entity(name='TestOther', entity_type='Person', group_id='test')
    storage.add_entity(other)

    rel = Relationship(
        source_entity='TestUser',
        target_entity='TestOther',
        fact='Test relationship',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    storage.add_relationship(rel)

    storage.clear_all(group_id='test')

    results = storage.search_relationships(query='Test', group_id='test')
    assert len(results) == 0
