"""Local storage layer using Kuzu embedded database."""

import json
import logging
import math
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import kuzu

from .models import Entity, MemoryKind, PlanStatus, Relationship

logger = logging.getLogger(__name__)

def get_data_dir() -> Path:
    """Get the data directory, creating it if needed."""
    data_dir = Path(os.environ.get('GRAPHITI_LOCAL_DIR', str(Path.home() / '.graphiti-local')))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_default_db_path() -> str:
    """Get the default database path."""
    return str(get_data_dir() / 'kuzu.db')


class LocalStorage:
    """Embedded Kuzu storage for local knowledge graph."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_default_db_path()
        self.db = kuzu.Database(self.db_path)
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
        """Search relationships using BM25 keyword ranking and filters."""
        query_parts = query.lower().split() if query else []

        cypher_query = """
            MATCH (r:Relationship)-[:HAS_SOURCE]->(s:Entity)
            MATCH (r)-[:HAS_TARGET]->(t:Entity)
            WHERE r.group_id = $group_id
        """
        params: dict[str, Any] = {'group_id': group_id}

        # For plans, exclude superseded/done/dropped by default
        if not include_superseded:
            cypher_query += ' AND r.superseded_by IS NULL'
            if kind == MemoryKind.PLAN:
                cypher_query += (
                    ' AND (r.plan_status IS NULL OR '
                    '(r.plan_status <> $done_status AND r.plan_status <> $dropped_status))'
                )
                params['done_status'] = PlanStatus.DONE.value
                params['dropped_status'] = PlanStatus.DROPPED.value

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

        # Compute BM25 scores
        all_docs = []
        for _, row in rows.iterrows():
            doc_text = self._build_document_text(row)
            all_docs.append(doc_text)

        scored_results = []
        for idx, row in rows.iterrows():
            score = self._compute_bm25_score(all_docs[idx], query_parts, all_docs, tags, row)
            rel = self._row_to_relationship(row, 'r')
            source = self._row_to_entity(row, 's')
            target = self._row_to_entity(row, 't')
            scored_results.append((score, rel, source, target))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [(r, s, t) for (score, r, s, t) in scored_results[:limit]]

    def _build_document_text(self, row: Any) -> str:
        """Build searchable text from a row."""
        parts = [
            row['r.fact'],
            row['s.name'],
            row['s.summary'],
            row['t.name'],
            row['t.summary'],
        ]
        return ' '.join(str(p) for p in parts if p).lower()

    def _compute_bm25_score(
        self,
        doc_text: str,
        query_terms: list[str],
        all_docs: list[str],
        tags: list[str] | None,
        row: Any,
    ) -> float:
        """Compute BM25 score with term frequency, IDF, and length normalization.
        
        BM25 formula: sum over query terms of:
            IDF(term) * (TF(term) * (k1 + 1)) / (TF(term) + k1 * (1 - b + b * (doclen / avgdoclen)))
        
        Parameters:
            k1 = 1.5 (term frequency saturation)
            b = 0.75 (length normalization)
        """
        if not query_terms:
            # No query, sort by recency or relevance of tags
            score = 0.0
            if tags:
                row_tags = json.loads(row['r.tags']) if row['r.tags'] else []
                score = sum(5.0 for tag in tags if tag in row_tags)
            return score

        # BM25 parameters
        k1 = 1.5
        b = 0.75

        # Document length normalization
        doc_words = doc_text.split()
        doc_len = len(doc_words)
        avg_doc_len = sum(len(d.split()) for d in all_docs) / max(len(all_docs), 1)

        # Term frequencies in this document
        doc_term_freq = Counter(doc_words)

        # Compute BM25 score
        score = 0.0
        for term in query_terms:
            if term not in doc_term_freq:
                continue

            # Term frequency in this document
            tf = doc_term_freq[term]

            # Inverse document frequency
            docs_with_term = sum(1 for d in all_docs if term in d.split())
            idf = math.log((len(all_docs) - docs_with_term + 0.5) / (docs_with_term + 0.5) + 1.0)

            # BM25 component for this term
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
            score += idf * (numerator / denominator)

        # Boost for exact tag matches
        if tags:
            row_tags = json.loads(row['r.tags']) if row['r.tags'] else []
            tag_matches = sum(1 for tag in tags if tag in row_tags)
            score += tag_matches * 5.0

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
