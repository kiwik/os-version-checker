import tomllib

from datetime import date
from httpx import AsyncClient

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

with open('config.toml', 'rb') as f:
    config_data = tomllib.load(f)

_provider = config_data['free-api-qwen']
_model_name = _provider['model_name']
_base_url = _provider['base_url']
_api_key = _provider['api_key']
_httpx_heads = {'Authorization': 'Bearer {}'.format(_api_key)}

httpx_client = AsyncClient(proxy=config_data['proxy']['url'],
                           verify=config_data['proxy']['verify'],
                           headers=_httpx_heads)

model = OpenAIModel(_model_name,
                    provider=OpenAIProvider(base_url=_base_url,
                                            api_key=_api_key,
                                            http_client=httpx_client))

agent = Agent(
    model,
    deps_type=str,
    instructions="使用用户的名字回答问题。",
)


@agent.instructions
def add_the_users_name(ctx: RunContext[str]) -> str:
    return f"用户的名字是 {ctx.deps}."


@agent.instructions
def add_the_date() -> str:
    return f'日期是 {date.today()}.'


result = agent.run_sync('今天是几月几日？', deps='someone')
print(result.output)
print(result.all_messages())
