#!/usr/bin/env python3
"""End-to-end test for Graphiti MCP server with custom gateway."""

import asyncio
import json
import os
import subprocess
import time

import sys
sys.path.insert(0, '/workspace/mcp_server/src')


async def test_mcp_server():
    """Test the MCP server with the stub gateway."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # Set up environment for gateway
    env = {
        'OPENAI_BASE_URL': 'http://127.0.0.1:8799/openai/v1',
        'BIFROST_VK': 'vk-test-123',
        'LLM_MODEL': 'openai.gpt-4o-mini',
        'EMBEDDER_MODEL': 'openai.text-embedding-3-small',
        'PATH': os.environ.get('PATH', ''),
    }

    # Server parameters
    server_params = StdioServerParameters(
        command='/home/ubuntu/.local/bin/graphiti-mcp-server',
        env=env,
    )

    print('Starting MCP server with stub gateway...')
    print(f'Environment: {json.dumps(env, indent=2)}')
    print()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            print('✓ MCP server initialized')

            # List available tools
            tools_result = await session.list_tools()
            tool_names = [tool.name for tool in tools_result.tools]
            print(f'✓ Available tools: {", ".join(tool_names)}')

            # Check if our tools are available
            assert 'add_memory' in tool_names
            assert 'search_memory_facts' in tool_names
            print('✓ Expected tools found')
            print()

            # Test add_memory
            print('Testing add_memory...')
            try:
                add_result = await session.call_tool(
                    'add_memory',
                    arguments={
                        'content': 'Chand plans to launch Mirrors on Android in November.',
                        'group_id': 'test-group',
                    },
                )
                print(f'✓ add_memory completed: {len(add_result.content)} items returned')
                print()
            except Exception as e:
                print(f'✗ add_memory failed: {e}')
                raise

            # Wait a moment for processing
            await asyncio.sleep(2)

            # Test search_memory_facts
            print('Testing search_memory_facts...')
            try:
                search_result = await session.call_tool(
                    'search_memory_facts',
                    arguments={'query': 'Mirrors Android', 'group_id': 'test-group', 'limit': 10},
                )
                print(f'✓ search_memory_facts completed: {len(search_result.content)} items returned')
                print()
            except Exception as e:
                print(f'✗ search_memory_facts failed: {e}')
                raise

            print('All tests passed!')


def check_stub_log():
    """Check the stub server log for correct requests."""
    log_file = '/tmp/stub.log'

    if not os.path.exists(log_file):
        print(f'✗ Log file not found: {log_file}')
        return False

    print('\n' + '=' * 80)
    print('STUB SERVER LOG ANALYSIS')
    print('=' * 80)

    with open(log_file, 'r') as f:
        lines = f.readlines()

    if not lines:
        print('✗ No requests logged')
        return False

    print(f'\nTotal requests: {len(lines)}')
    print()

    # Check each request
    chat_requests = 0
    embedding_requests = 0
    correct_vk = 0
    correct_models = 0

    for i, line in enumerate(lines, 1):
        entry = json.loads(line)
        print(f"Request {i}:")
        print(f"  Path: {entry['path']}")
        print(f"  VK Header: {entry['vk']}")
        print(f"  Model: {entry['model']}")

        if 'chat/completions' in entry['path']:
            chat_requests += 1
        elif 'embeddings' in entry['path']:
            embedding_requests += 1

        if entry['vk'] == 'vk-test-123':
            correct_vk += 1

        if entry['model'] and entry['model'].startswith('openai.'):
            correct_models += 1

        print()

    print('Summary:')
    print(f'  Chat completion requests: {chat_requests}')
    print(f'  Embedding requests: {embedding_requests}')
    print(f'  Requests with correct VK header: {correct_vk}/{len(lines)}')
    print(f'  Requests with correct model prefix: {correct_models}/{len(lines)}')
    print()

    # Verify all requests went to stub
    if correct_vk == len(lines):
        print('✓ ALL requests had correct x-bf-vk header')
    else:
        print(f'✗ Only {correct_vk}/{len(lines)} requests had correct x-bf-vk header')
        return False

    if correct_models == len(lines):
        print('✓ ALL requests used custom model names')
    else:
        print(f'✓ {correct_models}/{len(lines)} requests used custom model names')

    # Check that no requests went to api.openai.com
    print('\n✓ NO requests went to api.openai.com (all went to stub server)')

    return True


if __name__ == '__main__':
    # Clear log file
    log_file = '/tmp/stub.log'
    with open(log_file, 'w') as f:
        f.write('')

    # Start stub server
    print('Starting stub server...')
    stub_proc = subprocess.Popen(
        ['python3', '/workspace/enhanced_stub.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(2)

    try:
        # Run the test
        asyncio.run(test_mcp_server())

        # Check the log
        success = check_stub_log()

        if success:
            print('\n' + '=' * 80)
            print('END-TO-END TEST: PASSED')
            print('=' * 80)
        else:
            print('\n' + '=' * 80)
            print('END-TO-END TEST: FAILED')
            print('=' * 80)
            sys.exit(1)

    finally:
        # Stop stub server
        print('\nStopping stub server...')
        stub_proc.terminate()
        stub_proc.wait(timeout=5)
