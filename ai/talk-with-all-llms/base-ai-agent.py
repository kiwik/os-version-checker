# Please install OpenAI SDK first: `pip3 install openai`

import httpx
import tomllib
from openai import OpenAI, DefaultHttpxClient


with open('config.toml', 'rb') as f:
    config_data = tomllib.load(f)

proxy_httpx_client = DefaultHttpxClient(
    proxy=config_data['proxy']['base_url'],
    transport=httpx.HTTPTransport(local_address='0.0.0.0'),
    verify=config_data['proxy']['verify'])

client = OpenAI(api_key=config_data['llm']['api_key'],
                base_url=config_data['llm']['base_url'],
                http_client=proxy_httpx_client)

conversation = [{'role': 'user',
                 'content': '深度思考模式，每次输出以<think>\n开头。'
                            '输出不要使用markdown格式。'
                            '简洁回答，有启发性。'
                 }]
while True:
    content = input('Input: ')

    if content == 'exit':
        exit(0)

    conversation.append({'role': 'user',
                         'content': content})

    response = client.chat.completions.create(
        model='deepseek/deepseek-r1:free',
        temperature=0.6,
        messages=conversation,
        stream=True
    )

    chunk_content = []

    print('Output:')
    for chunk in response:
        delta_content = chunk.choices[0].delta.content
        if delta_content:
            chunk_content.append(delta_content)
            print(f'{delta_content}', end='')
    print()

    conversation.append(
        {'role': 'assistant', 'content': ''.join(chunk_content)}
    )
