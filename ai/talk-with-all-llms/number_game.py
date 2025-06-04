import random
import tomllib

from httpx import AsyncClient

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel, OpenAIModelSettings
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

agent = Agent(
    model,
    model_settings=OpenAIModelSettings(temperature=0.0),
    deps_type=str,
    system_prompt='你是一个色子游戏，通过调用外部工具函数生成一个数字，'
                  '检查玩家猜的数字与色子随机生成的数字是否相同，如果相同告诉玩家'
                  '他赢了，如果不相同，告诉玩家太弱了，回答中带上玩家的名字。'
                  '使用中文回答',
)


@agent.tool_plain
def roll_die() -> str:
    """6面色子，随机生成一个1~6的数字"""
    die_number = str(random.randint(1, 6))
    # print(die_number)
    return die_number


@agent.tool
def get_player_name(ctx: RunContext[str]) -> str:
    """函数返回玩家的名字"""
    # print(ctx.deps)
    return ctx.deps


dice_result = agent.run_sync('我猜是4', deps='马斯克')
print(dice_result.output)
# print(dice_result.all_messages_json())
