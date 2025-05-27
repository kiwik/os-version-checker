import asyncio
import tomllib

from httpx import AsyncClient

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

with open('config.toml', 'rb') as f:
    config_data = tomllib.load(f)

httpx_client = AsyncClient(proxy=config_data['proxy']['url'],
                           verify=config_data['proxy']['verify'])

model = OpenAIModel(config_data['openrouter']['model_name'],
                    provider=OpenRouterProvider(
                        api_key=config_data['openrouter']['api_key'],
                        http_client=httpx_client))

agent = Agent(model)


async def main():
    result = await agent.run('时间是否真的存在？')
    print(result)


asyncio.run(main())
