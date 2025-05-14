import tomllib

from httpx import AsyncClient

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

with open('config.toml', 'rb') as f:
    config_data = tomllib.load(f)

httpx_client = AsyncClient(proxy=config_data['proxy']['url'],
                           verify=config_data['proxy']['verify'])

model = OpenAIModel("deepseek/deepseek-r1:free",
                    provider=OpenAIProvider(
                        base_url=config_data['llm']['base_url'],
                        api_key=config_data['llm']['api_key'],
                        http_client=httpx_client))

agent = Agent(model)
result = agent.run_sync('生命的意义是什么？')
print(result)
