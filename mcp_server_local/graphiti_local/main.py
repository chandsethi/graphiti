#!/usr/bin/env python3
"""Graphiti Local MCP Server - stdio transport."""

import argparse
import logging
import sys
from datetime import datetime, timezone

from mcp.server.stdio import stdio_server


def utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc)
from mcp.server import Server
from mcp.types import Tool, TextContent

from .models import (
    AddMemoryRequest,
    Entity,
    ListRecentRequest,
    MarkFactCorrectionRequest,
    MemoryKind,
    PlanStatus,
    PromoteIdeaRequest,
    Relationship,
    SearchMemoryRequest,
    SupersedePlanRequest,
    UpdatePlanStatusRequest,
)
from .storage import LocalStorage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)

server = Server('graphiti-local')
storage = LocalStorage()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name='add_memory',
            description=(
                'Add a new memory (fact, plan, or idea) to the knowledge graph. '
                'You (Codex) provide the structured entities and relationships. '
                'Facts: stable truths. Plans: versioned, track status. Ideas: not treated as truth.'
            ),
            inputSchema={
                'type': 'object',
                'required': ['entities', 'relationships', 'kind'],
                'properties': {
                    'entities': {
                        'type': 'array',
                        'description': 'List of entities [{"name": "X", "type": "Person", "summary": "..."}]',
                        'items': {
                            'type': 'object',
                            'required': ['name', 'type'],
                            'properties': {
                                'name': {'type': 'string'},
                                'type': {'type': 'string'},
                                'summary': {'type': 'string', 'default': ''},
                            },
                        },
                    },
                    'relationships': {
                        'type': 'array',
                        'description': 'List of relationships [{"source": "X", "target": "Y", "fact": "X knows Y"}]',
                        'items': {
                            'type': 'object',
                            'required': ['source', 'target', 'fact'],
                            'properties': {
                                'source': {'type': 'string'},
                                'target': {'type': 'string'},
                                'fact': {'type': 'string'},
                            },
                        },
                    },
                    'kind': {
                        'type': 'string',
                        'enum': ['fact', 'plan', 'idea'],
                        'description': 'fact: stable truth | plan: versioned action | idea: just an idea',
                    },
                    'tags': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Optional tags for filtering',
                        'default': [],
                    },
                    'plan_status': {
                        'type': 'string',
                        'enum': ['proposed', 'active', 'done', 'dropped'],
                        'description': 'Required for plans',
                    },
                    'plan_owner': {'type': 'string', 'description': 'Owner of the plan'},
                    'plan_due_date': {'type': 'string', 'format': 'date-time'},
                    'reference_time': {'type': 'string', 'format': 'date-time'},
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
        Tool(
            name='search_memory',
            description=(
                'Search memories by text query, kind, tags, entity type/name, and time range. '
                'Uses BM25 keyword matching + graph traversal (no embeddings). '
                'Returns fact/plan/idea relationships with connected entities.'
            ),
            inputSchema={
                'type': 'object',
                'required': ['query'],
                'properties': {
                    'query': {'type': 'string', 'description': 'Search query text'},
                    'kind': {
                        'type': 'string',
                        'enum': ['fact', 'plan', 'idea'],
                        'description': 'Filter by memory kind',
                    },
                    'tags': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Filter by tags',
                    },
                    'entity_type': {
                        'type': 'string',
                        'description': 'Filter by entity type (Person, Organization, etc.)',
                    },
                    'entity_name': {'type': 'string', 'description': 'Filter by entity name'},
                    'valid_after': {'type': 'string', 'format': 'date-time'},
                    'valid_before': {'type': 'string', 'format': 'date-time'},
                    'include_superseded': {
                        'type': 'boolean',
                        'default': False,
                        'description': 'Include superseded plans',
                    },
                    'limit': {'type': 'integer', 'default': 10},
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
        Tool(
            name='get_entity_neighborhood',
            description=(
                'Get an entity and all its connected relationships (its neighborhood in the graph). '
                'Useful for exploring what is known about a specific entity.'
            ),
            inputSchema={
                'type': 'object',
                'required': ['entity_name'],
                'properties': {
                    'entity_name': {'type': 'string', 'description': 'Name of the entity'},
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
        Tool(
            name='update_plan_status',
            description=(
                'Update the status of a plan (proposed -> active -> done/dropped). '
                'Use this to mark plans as complete or abandoned.'
            ),
            inputSchema={
                'type': 'object',
                'required': ['relationship_uuid', 'status'],
                'properties': {
                    'relationship_uuid': {
                        'type': 'string',
                        'description': 'UUID of the plan relationship',
                    },
                    'status': {
                        'type': 'string',
                        'enum': ['proposed', 'active', 'done', 'dropped'],
                    },
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
        Tool(
            name='supersede_plan',
            description=(
                'Supersede an old plan with a new version. The old plan is marked invalid '
                'and linked to the new plan. Preserves history.'
            ),
            inputSchema={
                'type': 'object',
                'required': ['old_relationship_uuid', 'new_relationship'],
                'properties': {
                    'old_relationship_uuid': {
                        'type': 'string',
                        'description': 'UUID of the old plan',
                    },
                    'new_relationship': {
                        'type': 'object',
                        'required': ['source', 'target', 'fact'],
                        'properties': {
                            'source': {'type': 'string'},
                            'target': {'type': 'string'},
                            'fact': {'type': 'string'},
                        },
                        'description': 'The new plan details',
                    },
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
        Tool(
            name='promote_idea',
            description=(
                'Promote an idea to a fact or plan. Changes the kind and optionally sets plan metadata.'
            ),
            inputSchema={
                'type': 'object',
                'required': ['relationship_uuid', 'new_kind'],
                'properties': {
                    'relationship_uuid': {
                        'type': 'string',
                        'description': 'UUID of the idea relationship',
                    },
                    'new_kind': {
                        'type': 'string',
                        'enum': ['fact', 'plan'],
                        'description': 'Promote to fact or plan',
                    },
                    'plan_status': {
                        'type': 'string',
                        'enum': ['proposed', 'active', 'done', 'dropped'],
                    },
                    'plan_owner': {'type': 'string'},
                    'plan_due_date': {'type': 'string', 'format': 'date-time'},
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
        Tool(
            name='mark_fact_correction',
            description=(
                'Flag a fact as corrected by newer information. The old fact is not deleted '
                'but marked as conflicting. Use when new information contradicts an old fact.'
            ),
            inputSchema={
                'type': 'object',
                'required': ['fact_uuid', 'correcting_fact_uuid'],
                'properties': {
                    'fact_uuid': {'type': 'string', 'description': 'UUID of the old fact'},
                    'correcting_fact_uuid': {
                        'type': 'string',
                        'description': 'UUID of the new, correcting fact',
                    },
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
        Tool(
            name='list_recent',
            description=(
                'List recent memories, optionally filtered by kind. Sorted by creation time (newest first).'
            ),
            inputSchema={
                'type': 'object',
                'properties': {
                    'kind': {
                        'type': 'string',
                        'enum': ['fact', 'plan', 'idea'],
                        'description': 'Filter by memory kind',
                    },
                    'limit': {'type': 'integer', 'default': 20},
                    'group_id': {'type': 'string', 'default': 'default'},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle MCP tool calls."""
    try:
        if name == 'add_memory':
            return await _add_memory(arguments)
        elif name == 'search_memory':
            return await _search_memory(arguments)
        elif name == 'get_entity_neighborhood':
            return await _get_entity_neighborhood(arguments)
        elif name == 'update_plan_status':
            return await _update_plan_status(arguments)
        elif name == 'supersede_plan':
            return await _supersede_plan(arguments)
        elif name == 'promote_idea':
            return await _promote_idea(arguments)
        elif name == 'mark_fact_correction':
            return await _mark_fact_correction(arguments)
        elif name == 'list_recent':
            return await _list_recent(arguments)
        else:
            return [TextContent(type='text', text=f'Unknown tool: {name}')]
    except Exception as e:
        logger.error(f'Error in {name}: {e}', exc_info=True)
        return [TextContent(type='text', text=f'Error: {str(e)}')]


async def _add_memory(args: dict) -> list[TextContent]:
    """Add a memory."""
    req = AddMemoryRequest(**args)

    entities = []
    for e in req.entities:
        entity = Entity(
            name=e['name'],
            entity_type=e.get('type', 'Object'),
            summary=e.get('summary', ''),
            group_id=req.group_id,
        )
        entities.append(storage.add_entity(entity))

    relationships = []
    for r in req.relationships:
        rel = Relationship(
            source_entity=r['source'],
            target_entity=r['target'],
            fact=r['fact'],
            kind=req.kind,
            tags=req.tags,
            valid_at=req.reference_time or utc_now(),
            plan_status=req.plan_status,
            plan_owner=req.plan_owner,
            plan_due_date=req.plan_due_date,
            group_id=req.group_id,
        )
        relationships.append(storage.add_relationship(rel))

    result = {
        'status': 'success',
        'entities_created': len(entities),
        'relationships_created': len(relationships),
        'entity_names': [e.name for e in entities],
        'relationship_uuids': [r.uuid for r in relationships],
    }

    return [TextContent(type='text', text=str(result))]


async def _search_memory(args: dict) -> list[TextContent]:
    """Search memories."""
    req = SearchMemoryRequest(**args)

    results = storage.search_relationships(
        query=req.query,
        kind=req.kind,
        tags=req.tags,
        entity_type=req.entity_type,
        entity_name=req.entity_name,
        valid_after=req.valid_after,
        valid_before=req.valid_before,
        include_superseded=req.include_superseded,
        limit=req.limit,
        group_id=req.group_id,
    )

    formatted = []
    for rel, source, target in results:
        status_str = f' [{rel.plan_status.value}]' if rel.plan_status else ''
        superseded_str = ' (superseded)' if rel.superseded_by else ''
        conflict_str = ' (conflicted)' if rel.conflict_flagged else ''
        tags_str = f' tags:{rel.tags}' if rel.tags else ''

        formatted.append(
            f'[{rel.kind.value}{status_str}] {source.name} → {target.name}: {rel.fact}'
            f'{superseded_str}{conflict_str}{tags_str} (uuid: {rel.uuid}, valid: {rel.valid_at})'
        )

    result = f'Found {len(results)} memories:\n\n' + '\n'.join(formatted)
    return [TextContent(type='text', text=result)]


async def _get_entity_neighborhood(args: dict) -> list[TextContent]:
    """Get entity neighborhood."""
    entity_name = args['entity_name']
    group_id = args.get('group_id', 'default')

    entity, relationships = storage.get_entity_neighborhood(entity_name, group_id)

    lines = [
        f'Entity: {entity.name} ({entity.entity_type})',
        f'Summary: {entity.summary}',
        f'Created: {entity.created_at}',
        f'',
        f'Connected relationships ({len(relationships)}):',
    ]

    for rel, source, target in relationships:
        status_str = f' [{rel.plan_status.value}]' if rel.plan_status else ''
        lines.append(
            f'  [{rel.kind.value}{status_str}] {source.name} → {target.name}: {rel.fact}'
        )

    return [TextContent(type='text', text='\n'.join(lines))]


async def _update_plan_status(args: dict) -> list[TextContent]:
    """Update plan status."""
    req = UpdatePlanStatusRequest(**args)

    result = storage.get_relationship(req.relationship_uuid)
    if not result:
        return [TextContent(type='text', text=f'Relationship not found: {req.relationship_uuid}')]

    rel, _, _ = result

    if rel.kind != MemoryKind.PLAN:
        return [TextContent(type='text', text='Error: Can only update status of plans')]

    rel.plan_status = req.status
    storage.update_relationship(rel)

    return [
        TextContent(type='text', text=f'Plan status updated to: {req.status.value} (uuid: {rel.uuid})')
    ]


async def _supersede_plan(args: dict) -> list[TextContent]:
    """Supersede a plan."""
    req = SupersedePlanRequest(**args)

    old_result = storage.get_relationship(req.old_relationship_uuid)
    if not old_result:
        return [
            TextContent(type='text', text=f'Old relationship not found: {req.old_relationship_uuid}')
        ]

    old_rel, _, _ = old_result

    if old_rel.kind != MemoryKind.PLAN:
        return [TextContent(type='text', text='Error: Can only supersede plans')]

    new_rel = Relationship(
        source_entity=req.new_relationship['source'],
        target_entity=req.new_relationship['target'],
        fact=req.new_relationship['fact'],
        kind=MemoryKind.PLAN,
        tags=old_rel.tags,
        valid_at=utc_now(),
        plan_status=old_rel.plan_status or PlanStatus.ACTIVE,
        plan_owner=old_rel.plan_owner,
        plan_due_date=old_rel.plan_due_date,
        group_id=req.group_id,
    )
    new_rel = storage.add_relationship(new_rel)

    old_rel.invalid_at = utc_now()
    old_rel.superseded_by = new_rel.uuid
    storage.update_relationship(old_rel)

    return [
        TextContent(
            type='text',
            text=f'Plan superseded. Old: {req.old_relationship_uuid}, New: {new_rel.uuid}',
        )
    ]


async def _promote_idea(args: dict) -> list[TextContent]:
    """Promote an idea."""
    req = PromoteIdeaRequest(**args)

    result = storage.get_relationship(req.relationship_uuid)
    if not result:
        return [TextContent(type='text', text=f'Relationship not found: {req.relationship_uuid}')]

    rel, _, _ = result

    if rel.kind != MemoryKind.IDEA:
        return [TextContent(type='text', text='Error: Can only promote ideas')]

    rel.kind = req.new_kind
    if req.new_kind == MemoryKind.PLAN:
        rel.plan_status = req.plan_status or PlanStatus.PROPOSED
        rel.plan_owner = req.plan_owner
        rel.plan_due_date = req.plan_due_date

    storage.update_relationship(rel)

    return [
        TextContent(
            type='text', text=f'Idea promoted to {req.new_kind.value} (uuid: {rel.uuid})'
        )
    ]


async def _mark_fact_correction(args: dict) -> list[TextContent]:
    """Mark a fact as corrected."""
    req = MarkFactCorrectionRequest(**args)

    old_fact_result = storage.get_relationship(req.fact_uuid)
    if not old_fact_result:
        return [TextContent(type='text', text=f'Old fact not found: {req.fact_uuid}')]

    new_fact_result = storage.get_relationship(req.correcting_fact_uuid)
    if not new_fact_result:
        return [TextContent(type='text', text=f'New fact not found: {req.correcting_fact_uuid}')]

    old_rel, _, _ = old_fact_result

    if old_rel.kind != MemoryKind.FACT:
        return [TextContent(type='text', text='Error: Can only correct facts')]

    old_rel.conflict_flagged = True
    old_rel.attributes['corrected_by'] = req.correcting_fact_uuid
    storage.update_relationship(old_rel)

    return [
        TextContent(
            type='text',
            text=f'Fact {req.fact_uuid} flagged as corrected by {req.correcting_fact_uuid}',
        )
    ]


async def _list_recent(args: dict) -> list[TextContent]:
    """List recent memories."""
    req = ListRecentRequest(**args)

    results = storage.list_recent(kind=req.kind, limit=req.limit, group_id=req.group_id)

    if not results:
        kind_str = f' {req.kind.value}' if req.kind else ''
        return [TextContent(type='text', text=f'No recent{kind_str} memories found')]

    formatted = []
    for rel, source, target in results:
        status_str = f' [{rel.plan_status.value}]' if rel.plan_status else ''
        tags_str = f' tags:{rel.tags}' if rel.tags else ''
        formatted.append(
            f'[{rel.kind.value}{status_str}] {source.name} → {target.name}: {rel.fact}'
            f'{tags_str} (uuid: {rel.uuid}, {rel.created_at})'
        )

    kind_str = req.kind.value if req.kind else 'all'
    result = f'Recent {kind_str} memories ({len(results)}):\n\n' + '\n'.join(formatted)
    return [TextContent(type='text', text=result)]


def main():
    """Run the MCP server or CLI commands."""
    parser = argparse.ArgumentParser(description='Graphiti Local Memory MCP Server')
    parser.add_argument(
        'command',
        nargs='?',
        choices=['serve', 'reset'],
        default='serve',
        help='Command to run (default: serve)',
    )
    parser.add_argument(
        '--group-id',
        default='default',
        help='Group ID for operations (default: default)',
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Confirm destructive operations without prompting',
    )

    args = parser.parse_args()

    if args.command == 'reset':
        if not args.yes:
            print('This will DELETE ALL DATA for the group. Use --yes to confirm.')
            sys.exit(1)

        storage.clear_all(args.group_id)
        print(f'All data cleared for group: {args.group_id}')
        sys.exit(0)

    # Default: run MCP server
    import asyncio

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == '__main__':
    main()
