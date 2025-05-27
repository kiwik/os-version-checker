import asyncio
import tomllib

from httpx import AsyncClient

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

with open('config.toml', 'rb') as f:
    config_data = tomllib.load(f)

httpx_client = AsyncClient(proxy=config_data['proxy']['url'],
                           verify=config_data['proxy']['verify'])

_provider = config_data['openrouter']
_model_name = _provider['model_name']
_api_key = _provider['api_key']

model = OpenAIModel(_model_name,
                    provider=OpenRouterProvider(api_key=_api_key,
                                                http_client=httpx_client))

_system_prompt = ("Use the `roulette_wheel` function to see if the customer "
                  "has won based on the number they provide.")
roulette_agent = Agent(model,
                       deps_type=int, output_type=bool,
                       system_prompt=_system_prompt,)


@roulette_agent.tool
async def roulette_wheel(ctx: RunContext[int], square: int) -> str:
    """check if the square is a winner"""
    return 'winner' if square == ctx.deps else 'loser'


async def main():
    # Run the agent
    nodes = []
    success_number = 18
    async with roulette_agent.iter('Put my money on square eighteen',
                                   deps=success_number) as agent_run:
        async for node in agent_run:
            nodes.append(node)
    print(nodes)


asyncio.run(main())
