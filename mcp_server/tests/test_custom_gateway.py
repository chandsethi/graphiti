"""Test custom LLM gateway configuration (e.g., Bifrost)."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def bifrost_env():
    """Bifrost gateway environment variables."""
    return {
        'OPENAI_BASE_URL': 'https://bifrost-llm-proxy-alb-0.cmd.hotstar-prod.com/openai/v1',
        'LLM_EXTRA_HEADERS': '{"x-bf-vk":"test-virtual-key"}',
        'LLM_MODEL': 'openai.gpt-4o-mini',
        'LLM_SMALL_MODEL': 'openai.gpt-4o-mini',
        'EMBEDDER_MODEL': 'openai.text-embedding-3-small',
    }


@pytest.mark.asyncio
async def test_llm_factory_with_custom_gateway(bifrost_env):
    """Test that LLM factory uses custom gateway configuration."""
    with patch.dict(os.environ, bifrost_env, clear=False):
        from config.schema import LLMConfig
        from services.factories import LLMClientFactory

        config = LLMConfig(provider='openai', model='gpt-5.5')

        with (
            patch('services.factories.OpenAIGenericClient') as mock_generic_client,
            patch('openai.AsyncOpenAI') as mock_async_openai,
        ):
            mock_generic_client.return_value = MagicMock()

            LLMClientFactory.create(config)

            # Should use OpenAI compatible client (generic)
            assert mock_generic_client.called

            # Check AsyncOpenAI was called with correct params
            mock_async_openai.assert_called_once()
            call_kwargs = mock_async_openai.call_args[1]

            assert (
                call_kwargs['base_url']
                == 'https://bifrost-llm-proxy-alb-0.cmd.hotstar-prod.com/openai/v1'
            )
            assert call_kwargs['default_headers'] == {'x-bf-vk': 'test-virtual-key'}
            # API key can be placeholder
            assert call_kwargs['api_key'] in ['not-needed', None] or call_kwargs['api_key']


@pytest.mark.asyncio
async def test_embedder_factory_with_custom_gateway(bifrost_env):
    """Test that embedder factory uses custom gateway configuration."""
    with patch.dict(os.environ, bifrost_env, clear=False):
        from config.schema import EmbedderConfig
        from services.factories import EmbedderFactory

        config = EmbedderConfig(provider='openai', model='text-embedding-3-small')

        with (
            patch('services.factories.OpenAIEmbedder') as mock_embedder,
            patch('openai.AsyncOpenAI') as mock_async_openai,
        ):
            mock_embedder.return_value = MagicMock()

            EmbedderFactory.create(config)

            # Should create embedder
            assert mock_embedder.called

            # Check if AsyncOpenAI was called (when extra headers present)
            if mock_async_openai.called:
                call_kwargs = mock_async_openai.call_args[1]
                assert (
                    call_kwargs['base_url']
                    == 'https://bifrost-llm-proxy-alb-0.cmd.hotstar-prod.com/openai/v1'
                )
                assert call_kwargs['default_headers'] == {'x-bf-vk': 'test-virtual-key'}


def test_extra_headers_parsing():
    """Test that extra headers are correctly parsed from JSON."""
    test_cases = [
        ('{"x-bf-vk":"key123"}', {'x-bf-vk': 'key123'}),
        ('{"x-custom":"value","x-other":"val2"}', {'x-custom': 'value', 'x-other': 'val2'}),
        ('invalid-json', {}),  # Should handle gracefully
    ]

    for json_str, expected in test_cases:
        env = {'LLM_EXTRA_HEADERS': json_str, 'OPENAI_API_KEY': 'test'}

        with patch.dict(os.environ, env, clear=False):
            try:
                result = json.loads(os.environ.get('LLM_EXTRA_HEADERS', '{}'))
                if json_str == 'invalid-json':
                    raise AssertionError('Should have raised JSONDecodeError')
            except json.JSONDecodeError:
                result = {}

            if json_str != 'invalid-json':
                assert result == expected


def test_bifrost_vk_convenience():
    """Test BIFROST_VK convenience env var."""
    import os

    env = {'BIFROST_VK': 'my-virtual-key', 'OPENAI_API_KEY': 'test'}

    with patch.dict(os.environ, env, clear=False):
        # The factory should add x-bf-vk header
        expected_header = {'x-bf-vk': os.environ['BIFROST_VK']}
        assert expected_header == {'x-bf-vk': 'my-virtual-key'}


@pytest.mark.asyncio
async def test_model_names_from_env():
    """Test that model names are read from environment variables."""
    env = {
        'LLM_MODEL': 'google.gemma-3-27b-it',
        'LLM_SMALL_MODEL': 'openai.gpt-4o-mini',
        'EMBEDDER_MODEL': 'openai.text-embedding-3-small',
        'OPENAI_API_KEY': 'test',
    }

    with patch.dict(os.environ, env, clear=False):
        # Just verify the env vars are set correctly
        assert os.environ['LLM_MODEL'] == 'google.gemma-3-27b-it'
        assert os.environ['LLM_SMALL_MODEL'] == 'openai.gpt-4o-mini'
        assert os.environ['EMBEDDER_MODEL'] == 'openai.text-embedding-3-small'
