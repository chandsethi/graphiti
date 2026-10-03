"""Test semantic requirements for fact/plan/idea lifecycle."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from graphiti_local.models import Entity, MemoryKind, PlanStatus, Relationship
from graphiti_local.storage import LocalStorage


def block_network(*args, **kwargs):
    """Block all network calls."""
    raise RuntimeError('Network call attempted!')


@pytest.fixture(autouse=True)
def no_network():
    """Block all socket calls."""
    with patch('socket.socket', side_effect=block_network):
        with patch('socket.create_connection', side_effect=block_network):
            yield


def test_contradicting_facts_both_kept(storage: LocalStorage):
    """Test that contradicting facts are both kept and flagged."""
    # Add first fact
    user = Entity(name='Alice', entity_type='Person', group_id='test')
    city1 = Entity(name='New York', entity_type='Location', group_id='test')
    storage.add_entity(user)
    storage.add_entity(city1)

    fact1 = Relationship(
        source_entity='Alice',
        target_entity='New York',
        fact='Alice lives in New York',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    fact1 = storage.add_relationship(fact1)

    # Add contradicting fact
    city2 = Entity(name='San Francisco', entity_type='Location', group_id='test')
    storage.add_entity(city2)

    fact2 = Relationship(
        source_entity='Alice',
        target_entity='San Francisco',
        fact='Alice lives in San Francisco',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    fact2 = storage.add_relationship(fact2)

    # Both facts should exist
    results = storage.search_relationships(query='Alice lives', group_id='test', limit=10)
    assert len(results) == 2

    # Neither should be automatically invalidated
    result1 = storage.get_relationship(fact1.uuid)
    assert result1 is not None
    rel1, _, _ = result1
    assert rel1.invalid_at is None

    result2 = storage.get_relationship(fact2.uuid)
    assert result2 is not None
    rel2, _, _ = result2
    assert rel2.invalid_at is None


def test_marked_fact_correction_flags_conflict(storage: LocalStorage):
    """Test that explicitly marking a fact correction flags the old fact."""
    user = Entity(name='Bob', entity_type='Person', group_id='test')
    city1 = Entity(name='Boston', entity_type='Location', group_id='test')
    storage.add_entity(user)
    storage.add_entity(city1)

    old_fact = Relationship(
        source_entity='Bob',
        target_entity='Boston',
        fact='Bob lives in Boston',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    old_fact = storage.add_relationship(old_fact)

    city2 = Entity(name='Seattle', entity_type='Location', group_id='test')
    storage.add_entity(city2)

    new_fact = Relationship(
        source_entity='Bob',
        target_entity='Seattle',
        fact='Bob lives in Seattle',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    new_fact = storage.add_relationship(new_fact)

    # Mark old fact as corrected
    old_fact.conflict_flagged = True
    old_fact.attributes['corrected_by'] = new_fact.uuid
    storage.update_relationship(old_fact)

    # Old fact should be flagged
    result = storage.get_relationship(old_fact.uuid)
    assert result is not None
    rel, _, _ = result
    assert rel.conflict_flagged is True
    assert rel.attributes['corrected_by'] == new_fact.uuid

    # New fact should not be flagged
    result = storage.get_relationship(new_fact.uuid)
    assert result is not None
    rel, _, _ = result
    assert rel.conflict_flagged is False


def test_search_plans_excludes_superseded_by_default(storage: LocalStorage):
    """Test that searching plans excludes superseded plans by default."""
    team = Entity(name='Team', entity_type='Organization', group_id='test')
    project = Entity(name='Project', entity_type='System', group_id='test')
    storage.add_entity(team)
    storage.add_entity(project)

    # Add active plan
    active_plan = Relationship(
        source_entity='Team',
        target_entity='Project',
        fact='Complete project by Q1',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        group_id='test',
    )
    active_plan = storage.add_relationship(active_plan)

    # Add superseded plan
    old_plan = Relationship(
        source_entity='Team',
        target_entity='Project',
        fact='Complete project by Q4 last year',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        group_id='test',
    )
    old_plan = storage.add_relationship(old_plan)
    old_plan.superseded_by = active_plan.uuid
    old_plan.invalid_at = datetime.now(timezone.utc)
    storage.update_relationship(old_plan)

    # Search without include_superseded should only return active
    results = storage.search_relationships(
        query='project',
        kind=MemoryKind.PLAN,
        include_superseded=False,
        group_id='test',
    )

    assert len(results) == 1
    rel, _, _ = results[0]
    assert rel.uuid == active_plan.uuid
    assert rel.superseded_by is None


def test_search_plans_excludes_done_and_dropped_by_default(storage: LocalStorage):
    """Test that searching plans excludes done/dropped plans by default."""
    team = Entity(name='DevTeam', entity_type='Organization', group_id='test')
    feature = Entity(name='Feature', entity_type='System', group_id='test')
    storage.add_entity(team)
    storage.add_entity(feature)

    # Add active plan
    active_plan = Relationship(
        source_entity='DevTeam',
        target_entity='Feature',
        fact='Build new feature',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        group_id='test',
    )
    active_plan = storage.add_relationship(active_plan)

    # Add proposed plan
    proposed_plan = Relationship(
        source_entity='DevTeam',
        target_entity='Feature',
        fact='Plan new feature architecture',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.PROPOSED,
        group_id='test',
    )
    proposed_plan = storage.add_relationship(proposed_plan)

    # Add done plan
    done_plan = Relationship(
        source_entity='DevTeam',
        target_entity='Feature',
        fact='Design feature mockups',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.DONE,
        group_id='test',
    )
    done_plan = storage.add_relationship(done_plan)

    # Add dropped plan
    dropped_plan = Relationship(
        source_entity='DevTeam',
        target_entity='Feature',
        fact='Use alternative approach',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.DROPPED,
        group_id='test',
    )
    dropped_plan = storage.add_relationship(dropped_plan)

    # Search without include_superseded should only return active and proposed
    results = storage.search_relationships(
        query='feature',
        kind=MemoryKind.PLAN,
        include_superseded=False,
        group_id='test',
    )

    assert len(results) == 2
    uuids = {r[0].uuid for r in results}
    assert active_plan.uuid in uuids
    assert proposed_plan.uuid in uuids
    assert done_plan.uuid not in uuids
    assert dropped_plan.uuid not in uuids


def test_search_plans_includes_done_and_dropped_when_requested(storage: LocalStorage):
    """Test that include_superseded=True shows all plans."""
    team = Entity(name='QATeam', entity_type='Organization', group_id='test')
    test = Entity(name='Test', entity_type='System', group_id='test')
    storage.add_entity(team)
    storage.add_entity(test)

    # Add plans with various statuses
    active_plan = Relationship(
        source_entity='QATeam',
        target_entity='Test',
        fact='Run integration tests',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        group_id='test',
    )
    storage.add_relationship(active_plan)

    done_plan = Relationship(
        source_entity='QATeam',
        target_entity='Test',
        fact='Run unit tests',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.DONE,
        group_id='test',
    )
    storage.add_relationship(done_plan)

    # Search with include_superseded=True should return all
    results = storage.search_relationships(
        query='tests',
        kind=MemoryKind.PLAN,
        include_superseded=True,
        group_id='test',
    )

    assert len(results) == 2


def test_ideas_never_invalidate_facts(storage: LocalStorage):
    """Test that ideas never invalidate facts."""
    user = Entity(name='Charlie', entity_type='Person', group_id='test')
    tech1 = Entity(name='React', entity_type='Technology', group_id='test')
    tech2 = Entity(name='Vue', entity_type='Technology', group_id='test')
    storage.add_entity(user)
    storage.add_entity(tech1)
    storage.add_entity(tech2)

    # Add a fact
    fact = Relationship(
        source_entity='Charlie',
        target_entity='React',
        fact='Charlie uses React for frontend',
        kind=MemoryKind.FACT,
        group_id='test',
    )
    fact = storage.add_relationship(fact)

    # Add a contradicting idea
    idea = Relationship(
        source_entity='Charlie',
        target_entity='Vue',
        fact='What if Charlie used Vue instead?',
        kind=MemoryKind.IDEA,
        group_id='test',
    )
    idea = storage.add_relationship(idea)

    # Fact should still be valid
    result = storage.get_relationship(fact.uuid)
    assert result is not None
    rel, _, _ = result
    assert rel.invalid_at is None
    assert rel.superseded_by is None
    assert not rel.conflict_flagged

    # Both should exist
    results = storage.search_relationships(query='frontend', group_id='test')
    assert len(results) == 2


def test_ideas_never_invalidate_plans(storage: LocalStorage):
    """Test that ideas never invalidate plans."""
    team = Entity(name='Backend', entity_type='Organization', group_id='test')
    api = Entity(name='API', entity_type='System', group_id='test')
    storage.add_entity(team)
    storage.add_entity(api)

    # Add a plan
    plan = Relationship(
        source_entity='Backend',
        target_entity='API',
        fact='Migrate API to FastAPI',
        kind=MemoryKind.PLAN,
        plan_status=PlanStatus.ACTIVE,
        group_id='test',
    )
    plan = storage.add_relationship(plan)

    # Add an alternative idea
    idea = Relationship(
        source_entity='Backend',
        target_entity='API',
        fact='What if we used GraphQL instead?',
        kind=MemoryKind.IDEA,
        group_id='test',
    )
    idea = storage.add_relationship(idea)

    # Plan should still be active
    result = storage.get_relationship(plan.uuid)
    assert result is not None
    rel, _, _ = result
    assert rel.plan_status == PlanStatus.ACTIVE
    assert rel.invalid_at is None
    assert rel.superseded_by is None

    # Both should exist
    results = storage.search_relationships(query='API', group_id='test')
    assert len(results) == 2
