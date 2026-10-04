#!/usr/bin/env python3
"""Enhanced OpenAI-compatible stub server for testing Graphiti with custom gateways."""

import http.server
import json
from datetime import datetime

# Log file path
LOG_FILE = '/tmp/stub.log'


class EnhancedStubHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        # Read request body
        content_length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        request_data = json.loads(body)

        # Log the request
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'path': self.path,
            'vk': self.headers.get('x-bf-vk'),
            'auth': self.headers.get('authorization'),
            'model': request_data.get('model'),
            'messages': len(request_data.get('messages', []))
            if 'messages' in request_data
            else None,
        }

        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Generate appropriate response
        if 'embeddings' in self.path:
            # Embedding response
            inp = request_data.get('input')
            inp = inp if isinstance(inp, list) else [inp]
            response = {
                'object': 'list',
                'data': [
                    {'object': 'embedding', 'index': i, 'embedding': [0.01] * 1024}
                    for i, _ in enumerate(inp)
                ],
                'model': request_data.get('model', 'test-embedding'),
                'usage': {'prompt_tokens': len(inp), 'total_tokens': len(inp)},
            }
        else:
            # Chat completion response
            messages = request_data.get('messages', [])
            response_format = request_data.get('response_format', {})

            # Check if structured output is requested
            if response_format.get('type') == 'json_schema':
                # Return a minimal valid JSON that matches common Graphiti schemas
                # This is a generic response that should work for most Graphiti prompts
                content = json.dumps(
                    {
                        'nodes': [],
                        'edges': [],
                        'episodes': [],
                        'entities': [],
                        'facts': [],
                    }
                )
            elif request_data.get('response_format', {}).get('type') == 'json_object':
                # JSON mode
                content = json.dumps({'result': 'success', 'data': []})
            else:
                # Plain text
                content = 'Test response'

            response = {
                'id': f'chatcmpl-test-{datetime.utcnow().timestamp()}',
                'object': 'chat.completion',
                'created': int(datetime.utcnow().timestamp()),
                'model': request_data.get('model', 'test-model'),
                'choices': [
                    {
                        'index': 0,
                        'message': {'role': 'assistant', 'content': content},
                        'finish_reason': 'stop',
                        'logprobs': {
                            'content': [
                                {
                                    'token': 'True',
                                    'logprob': -0.1,
                                    'top_logprobs': [
                                        {'token': 'True', 'logprob': -0.1},
                                        {'token': 'False', 'logprob': -2.3},
                                    ],
                                }
                            ]
                        }
                        if request_data.get('logprobs')
                        else None,
                    }
                ],
                'usage': {
                    'prompt_tokens': sum(len(m.get('content', '')) for m in messages) // 4,
                    'completion_tokens': len(content) // 4,
                    'total_tokens': (
                        sum(len(m.get('content', '')) for m in messages) // 4 + len(content) // 4
                    ),
                },
            }

        # Send response
        response_data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header('content-type', 'application/json')
        self.send_header('content-length', str(len(response_data)))
        self.end_headers()
        self.wfile.write(response_data)

    def log_message(self, *args):
        # Suppress default logging
        pass


if __name__ == '__main__':
    # Clear log file
    with open(LOG_FILE, 'w') as f:
        f.write('')

    print(f'Starting stub server on http://127.0.0.1:8799')
    print(f'Logging to {LOG_FILE}')
    print('Press Ctrl+C to stop')

    try:
        http.server.HTTPServer(('127.0.0.1', 8799), EnhancedStubHandler).serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
