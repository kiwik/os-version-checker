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


_system_prompt = ("使用`roulette_wheel`函数，通过用户输入的数字检查他们是否获胜。"
                  "使用中文回答。")
roulette_agent = Agent(model,
                       deps_type=int, output_type=bool,
                       system_prompt=_system_prompt, )


@roulette_agent.tool
async def roulette_wheel(ctx: RunContext[int], square: int) -> str:
    """检查输入的点数是否获胜"""
    return 'winner' if square == ctx.deps else 'loser'


# 运行Agent
success_number = 18
result = roulette_agent.run_sync('在18点下注', deps=success_number)
print(result.output)
print(result.all_messages())
