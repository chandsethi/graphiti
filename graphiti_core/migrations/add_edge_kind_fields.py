"""
Migration to add kind, superseded_by, and conflicts_with fields to existing edges.

This migration script adds the new edge fields introduced for memory kind tracking:
- kind: str (default 'fact')
- superseded_by: str | None
- conflicts_with: list[str]

Run this script after upgrading graphiti_core to ensure existing edges work correctly.
"""

import asyncio
import logging
from typing import Any

from graphiti_core.driver.driver import GraphDriver, GraphProvider

logger = logging.getLogger(__name__)


async def migrate_edges(driver: GraphDriver) -> dict[str, Any]:
    """Add kind, superseded_by, and conflicts_with fields to existing edges.

    This migration sets default values for edges that don't have these fields:
    - kind: 'fact' (default)
    - superseded_by: null
    - conflicts_with: [] (empty list)

    Args:
        driver: GraphDriver instance connected to the database

    Returns:
        dict with migration statistics (edges_updated count)
    """
    logger.info('Starting edge kind fields migration')

    if driver.provider == GraphProvider.KUZU:
        # Kuzu stores conflicts_with as JSON string
        query = """
            MATCH (n:Entity)-[:RELATES_TO]->(e:RelatesToNode_)-[:RELATES_TO]->(m:Entity)
            WHERE e.kind IS NULL
            SET
                e.kind = CASE WHEN e.kind IS NULL THEN 'fact' ELSE e.kind END,
                e.superseded_by = CASE WHEN e.superseded_by IS NULL THEN NULL ELSE e.superseded_by END,
                e.conflicts_with = CASE WHEN e.conflicts_with IS NULL THEN '[]' ELSE e.conflicts_with END
            RETURN count(e) AS updated_count
        """
    else:
        # Neo4j, FalkorDB, Neptune
        query = """
            MATCH (n:Entity)-[e:RELATES_TO]->(m:Entity)
            WHERE e.kind IS NULL
            SET
                e.kind = CASE WHEN e.kind IS NULL THEN 'fact' ELSE e.kind END,
                e.superseded_by = CASE WHEN e.superseded_by IS NULL THEN null ELSE e.superseded_by END,
                e.conflicts_with = CASE WHEN e.conflicts_with IS NULL THEN [] ELSE e.conflicts_with END
            RETURN count(e) AS updated_count
        """

    try:
        records, _, _ = await driver.execute_query(query)
        updated_count = records[0]['updated_count'] if records else 0
        logger.info(f'Migration complete: updated {updated_count} edges')
        return {'edges_updated': updated_count}
    except Exception as e:
        logger.error(f'Migration failed: {e}')
        raise


async def main():
    """Example usage of the migration."""
    # This is a standalone script example - in practice, you'd pass your configured driver
    from graphiti_core.driver.neo4j_driver import Neo4jDriver

    driver = Neo4jDriver(
        uri='bolt://localhost:7687',
        user='neo4j',
        password='password',
    )

    try:
        stats = await migrate_edges(driver)
        print(f'Migration completed: {stats}')
    finally:
        await driver.close()


if __name__ == '__main__':
    asyncio.run(main())
