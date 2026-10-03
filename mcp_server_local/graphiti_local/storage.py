"""Local storage layer using Kuzu embedded database."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import kuzu

from .models import Entity, MemoryKind, PlanStatus, Relationship

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / '.graphiti-local'
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = str(DATA_DIR / 'kuzu.db')


class LocalStorage:
    """Embedded Kuzu storage for local knowledge graph."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self):
        """Initialize the Kuzu schema."""
        logger.info('Initializing Kuzu schema')

        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Entity (
                uuid STRING PRIMARY KEY,
                name STRING,
                entity_type STRING,
                summary STRING,
                created_at TIMESTAMP,
                group_id STRING
            )
        """)

        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Relationship (
                uuid STRING PRIMARY KEY,
                fact STRING,
                kind STRING,
                tags STRING,
                valid_at TIMESTAMP,
                invalid_at TIMESTAMP,
                superseded_by STRING,
                plan_status STRING,
                plan_owner STRING,
                plan_due_date TIMESTAMP,
                created_at TIMESTAMP,
                group_id STRING,
                conflict_flagged BOOLEAN,
                attributes STRING
            )
        """)

        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_SOURCE (
                FROM Relationship TO Entity
            )
        """)

        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_TARGET (
                FROM Relationship TO Entity
            )
        """)

        logger.info('Schema initialized')

    def add_entity(self, entity: Entity) -> Entity:
        """Add or get an existing entity by name."""
        existing = self._get_entity_by_name(entity.name, entity.group_id)
        if existing:
            logger.debug(f'Entity {entity.name} already exists')
            return existing

        logger.debug(f'Adding entity: {entity.name}')
        self.conn.execute(
            """
            CREATE (e:Entity {
                uuid: $uuid,
                name: $name,
                entity_type: $entity_type,
                summary: $summary,
                created_at: $created_at,
                group_id: $group_id
            })
            """,
            {
                'uuid': entity.uuid,
                'name': entity.name,
                'entity_type': entity.entity_type,
                'summary': entity.summary,
                'created_at': entity.created_at,
                'group_id': entity.group_id,
            },
        )
        return entity

    def _get_entity_by_name(self, name: str, group_id: str) -> Entity | None:
        """Get an entity by name."""
        result = self.conn.execute(
            """
            MATCH (e:Entity)
            WHERE e.name = $name AND e.group_id = $group_id
            RETURN e.*
            """,
            {'name': name, 'group_id': group_id},
        )
        rows = result.get_as_df()
        if len(rows) == 0:
            return None
        row = rows.iloc[0]
        return Entity(
            uuid=row['e.uuid'],
            name=row['e.name'],
            entity_type=row['e.entity_type'],
            summary=row['e.summary'],
            created_at=row['e.created_at'],
            group_id=row['e.group_id'],
        )

    def get_entity_by_uuid(self, uuid: str) -> Entity | None:
        """Get an entity by UUID."""
        result = self.conn.execute(
            """
            MATCH (e:Entity)
            WHERE e.uuid = $uuid
            RETURN e.*
            """,
            {'uuid': uuid},
        )
        rows = result.get_as_df()
        if len(rows) == 0:
            return None
        row = rows.iloc[0]
        return Entity(
            uuid=row['e.uuid'],
            name=row['e.name'],
            entity_type=row['e.entity_type'],
            summary=row['e.summary'],
            created_at=row['e.created_at'],
            group_id=row['e.group_id'],
        )

    def add_relationship(self, rel: Relationship) -> Relationship:
        """Add a relationship between two entities."""
        logger.debug(f'Adding relationship: {rel.fact}')

        source = self._get_entity_by_name(rel.source_entity, rel.group_id)
        target = self._get_entity_by_name(rel.target_entity, rel.group_id)

        if not source or not target:
            raise ValueError(f'Entities not found: {rel.source_entity}, {rel.target_entity}')

        tags_str = json.dumps(rel.tags)
        attrs_str = json.dumps(rel.attributes)

        self.conn.execute(
            """
            CREATE (r:Relationship {
                uuid: $uuid,
                fact: $fact,
                kind: $kind,
                tags: $tags,
                valid_at: $valid_at,
                invalid_at: $invalid_at,
                superseded_by: $superseded_by,
                plan_status: $plan_status,
                plan_owner: $plan_owner,
                plan_due_date: $plan_due_date,
                created_at: $created_at,
                group_id: $group_id,
                conflict_flagged: $conflict_flagged,
                attributes: $attributes
            })
            """,
            {
                'uuid': rel.uuid,
                'fact': rel.fact,
                'kind': rel.kind.value,
                'tags': tags_str,
                'valid_at': rel.valid_at,
                'invalid_at': rel.invalid_at,
                'superseded_by': rel.superseded_by,
                'plan_status': rel.plan_status.value if rel.plan_status else None,
                'plan_owner': rel.plan_owner,
                'plan_due_date': rel.plan_due_date,
                'created_at': rel.created_at,
                'group_id': rel.group_id,
                'conflict_flagged': rel.conflict_flagged,
                'attributes': attrs_str,
            },
        )

        self.conn.execute(
            """
            MATCH (r:Relationship), (s:Entity)
            WHERE r.uuid = $rel_uuid AND s.uuid = $source_uuid
            CREATE (r)-[:HAS_SOURCE]->(s)
            """,
            {'rel_uuid': rel.uuid, 'source_uuid': source.uuid},
        )

        self.conn.execute(
            """
            MATCH (r:Relationship), (t:Entity)
            WHERE r.uuid = $rel_uuid AND t.uuid = $target_uuid
            CREATE (r)-[:HAS_TARGET]->(t)
            """,
            {'rel_uuid': rel.uuid, 'target_uuid': target.uuid},
        )

        return rel

    def search_relationships(
        self,
        query: str,
        kind: MemoryKind | None = None,
        tags: list[str] | None = None,
        entity_type: str | None = None,
        entity_name: str | None = None,
        valid_after: datetime | None = None,
        valid_before: datetime | None = None,
        include_superseded: bool = False,
        limit: int = 10,
        group_id: str = 'default',
    ) -> list[tuple[Relationship, Entity, Entity]]:
        """Search relationships using BM25-like keyword matching and filters."""
        query_parts = query.lower().split()

        cypher_query = """
            MATCH (r:Relationship)-[:HAS_SOURCE]->(s:Entity)
            MATCH (r)-[:HAS_TARGET]->(t:Entity)
            WHERE r.group_id = $group_id
        """
        params: dict[str, Any] = {'group_id': group_id}

        if not include_superseded:
            cypher_query += ' AND r.superseded_by IS NULL AND r.invalid_at IS NULL'

        if kind:
            cypher_query += ' AND r.kind = $kind'
            params['kind'] = kind.value

        if valid_after:
            cypher_query += ' AND r.valid_at >= $valid_after'
            params['valid_after'] = valid_after

        if valid_before:
            cypher_query += ' AND r.valid_at <= $valid_before'
            params['valid_before'] = valid_before

        if entity_type:
            cypher_query += ' AND (s.entity_type = $entity_type OR t.entity_type = $entity_type)'
            params['entity_type'] = entity_type

        if entity_name:
            cypher_query += ' AND (s.name = $entity_name OR t.name = $entity_name)'
            params['entity_name'] = entity_name

        cypher_query += ' RETURN r.*, s.*, t.*'

        result = self.conn.execute(cypher_query, params)
        rows = result.get_as_df()

        if len(rows) == 0:
            return []

        scored_results = []
        for _, row in rows.iterrows():
            score = self._compute_bm25_score(row, query_parts, tags)
            rel = self._row_to_relationship(row, 'r')
            source = self._row_to_entity(row, 's')
            target = self._row_to_entity(row, 't')
            scored_results.append((score, rel, source, target))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [(r, s, t) for (score, r, s, t) in scored_results[:limit]]

    def _compute_bm25_score(
        self, row: Any, query_terms: list[str], tags: list[str] | None
    ) -> float:
        """Simple BM25-like scoring."""
        text = (row['r.fact'] + ' ' + row['s.name'] + ' ' + row['t.name']).lower()
        score = sum(1.0 for term in query_terms if term in text)

        if tags:
            row_tags = json.loads(row['r.tags']) if row['r.tags'] else []
            tag_matches = sum(1.0 for tag in tags if tag in row_tags)
            score += tag_matches * 2.0

        return score

    def _row_to_relationship(self, row: Any, prefix: str) -> Relationship:
        """Convert a row to a Relationship."""
        import pandas as pd
        
        plan_status_val = row[f'{prefix}.plan_status']
        plan_status = (
            PlanStatus(plan_status_val)
            if plan_status_val is not None and not pd.isna(plan_status_val)
            else None
        )

        invalid_at_val = row[f'{prefix}.invalid_at']
        invalid_at = invalid_at_val if not pd.isna(invalid_at_val) else None

        superseded_by_val = row[f'{prefix}.superseded_by']
        superseded_by = superseded_by_val if not pd.isna(superseded_by_val) else None

        plan_owner_val = row[f'{prefix}.plan_owner']
        plan_owner = plan_owner_val if not pd.isna(plan_owner_val) else None

        plan_due_date_val = row[f'{prefix}.plan_due_date']
        plan_due_date = plan_due_date_val if not pd.isna(plan_due_date_val) else None

        return Relationship(
            uuid=row[f'{prefix}.uuid'],
            source_entity='',
            target_entity='',
            fact=row[f'{prefix}.fact'],
            kind=MemoryKind(row[f'{prefix}.kind']),
            tags=json.loads(row[f'{prefix}.tags']) if row[f'{prefix}.tags'] else [],
            valid_at=row[f'{prefix}.valid_at'],
            invalid_at=invalid_at,
            superseded_by=superseded_by,
            plan_status=plan_status,
            plan_owner=plan_owner,
            plan_due_date=plan_due_date,
            created_at=row[f'{prefix}.created_at'],
            group_id=row[f'{prefix}.group_id'],
            conflict_flagged=row[f'{prefix}.conflict_flagged'],
            attributes=json.loads(row[f'{prefix}.attributes'])
            if row[f'{prefix}.attributes']
            else {},
        )

    def _row_to_entity(self, row: Any, prefix: str) -> Entity:
        """Convert a row to an Entity."""
        return Entity(
            uuid=row[f'{prefix}.uuid'],
            name=row[f'{prefix}.name'],
            entity_type=row[f'{prefix}.entity_type'],
            summary=row[f'{prefix}.summary'],
            created_at=row[f'{prefix}.created_at'],
            group_id=row[f'{prefix}.group_id'],
        )

    def get_relationship(self, uuid: str) -> tuple[Relationship, Entity, Entity] | None:
        """Get a relationship by UUID."""
        result = self.conn.execute(
            """
            MATCH (r:Relationship)-[:HAS_SOURCE]->(s:Entity)
            MATCH (r)-[:HAS_TARGET]->(t:Entity)
            WHERE r.uuid = $uuid
            RETURN r.*, s.*, t.*
            """,
            {'uuid': uuid},
        )
        rows = result.get_as_df()
        if len(rows) == 0:
            return None
        row = rows.iloc[0]
        rel = self._row_to_relationship(row, 'r')
        source = self._row_to_entity(row, 's')
        target = self._row_to_entity(row, 't')
        return (rel, source, target)

    def update_relationship(self, rel: Relationship):
        """Update a relationship."""
        logger.debug(f'Updating relationship: {rel.uuid}')
        tags_str = json.dumps(rel.tags)
        attrs_str = json.dumps(rel.attributes)

        self.conn.execute(
            """
            MATCH (r:Relationship)
            WHERE r.uuid = $uuid
            SET r.fact = $fact,
                r.kind = $kind,
                r.tags = $tags,
                r.invalid_at = $invalid_at,
                r.superseded_by = $superseded_by,
                r.plan_status = $plan_status,
                r.plan_owner = $plan_owner,
                r.plan_due_date = $plan_due_date,
                r.conflict_flagged = $conflict_flagged,
                r.attributes = $attributes
            """,
            {
                'uuid': rel.uuid,
                'fact': rel.fact,
                'kind': rel.kind.value,
                'tags': tags_str,
                'invalid_at': rel.invalid_at,
                'superseded_by': rel.superseded_by,
                'plan_status': rel.plan_status.value if rel.plan_status else None,
                'plan_owner': rel.plan_owner,
                'plan_due_date': rel.plan_due_date,
                'conflict_flagged': rel.conflict_flagged,
                'attributes': attrs_str,
            },
        )

    def list_recent(
        self, kind: MemoryKind | None = None, limit: int = 20, group_id: str = 'default'
    ) -> list[tuple[Relationship, Entity, Entity]]:
        """List recent relationships."""
        cypher_query = """
            MATCH (r:Relationship)-[:HAS_SOURCE]->(s:Entity)
            MATCH (r)-[:HAS_TARGET]->(t:Entity)
            WHERE r.group_id = $group_id
                AND r.superseded_by IS NULL
                AND r.invalid_at IS NULL
        """
        params: dict[str, Any] = {'group_id': group_id}

        if kind:
            cypher_query += ' AND r.kind = $kind'
            params['kind'] = kind.value

        cypher_query += ' RETURN r.*, s.*, t.* ORDER BY r.created_at DESC LIMIT $limit'
        params['limit'] = limit

        result = self.conn.execute(cypher_query, params)
        rows = result.get_as_df()

        results = []
        for _, row in rows.iterrows():
            rel = self._row_to_relationship(row, 'r')
            source = self._row_to_entity(row, 's')
            target = self._row_to_entity(row, 't')
            results.append((rel, source, target))

        return results

    def get_entity_neighborhood(
        self, entity_name: str, group_id: str = 'default'
    ) -> tuple[Entity, list[tuple[Relationship, Entity, Entity]]]:
        """Get an entity and its connected relationships."""
        entity = self._get_entity_by_name(entity_name, group_id)
        if not entity:
            raise ValueError(f'Entity not found: {entity_name}')

        result = self.conn.execute(
            """
            MATCH (r:Relationship)-[:HAS_SOURCE]->(s:Entity)
            MATCH (r)-[:HAS_TARGET]->(t:Entity)
            WHERE (s.uuid = $entity_uuid OR t.uuid = $entity_uuid)
                AND r.group_id = $group_id
                AND r.superseded_by IS NULL
                AND r.invalid_at IS NULL
            RETURN r.*, s.*, t.*
            """,
            {'entity_uuid': entity.uuid, 'group_id': group_id},
        )
        rows = result.get_as_df()

        relationships = []
        for _, row in rows.iterrows():
            rel = self._row_to_relationship(row, 'r')
            source = self._row_to_entity(row, 's')
            target = self._row_to_entity(row, 't')
            relationships.append((rel, source, target))

        return entity, relationships

    def clear_all(self, group_id: str = 'default'):
        """Clear all data for a group."""
        logger.warning(f'Clearing all data for group: {group_id}')
        self.conn.execute(
            """
            MATCH (r:Relationship)
            WHERE r.group_id = $group_id
            DETACH DELETE r
            """,
            {'group_id': group_id},
        )
        self.conn.execute(
            """
            MATCH (e:Entity)
            WHERE e.group_id = $group_id
            DELETE e
            """,
            {'group_id': group_id},
        )

    def close(self):
        """Close the database connection."""
        pass
