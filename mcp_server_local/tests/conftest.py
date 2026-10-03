"""Pytest configuration for Graphiti Local tests."""

import tempfile
from pathlib import Path

import pytest

from graphiti_local.storage import LocalStorage


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / 'test.db')
        storage = LocalStorage(db_path)
        yield storage
        storage.close()


@pytest.fixture
def storage(temp_db):
    """Alias for temp_db fixture."""
    return temp_db
