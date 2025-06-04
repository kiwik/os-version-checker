import tomllib
from httpx import AsyncClient

from pydantic import BaseModel
from pydantic_ai import Agent
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


class Box(BaseModel):
    width: int
    height: int
    depth: int
    units: str


agent = Agent(
    model,
    model_settings=OpenAIModelSettings(temperature=0.0),
    output_type=[Box, str],
    system_prompt=(
        "Extract me the dimensions of a box, "
        "if you can't extract all data, ask the user to try again."
    ),
)

result = agent.run_sync('The box is 10x20x30')
print(result.output)
# > Please provide the units for the dimensions (e.g., cm, in, m).

result = agent.run_sync('The box is 10x20x30 cm')
print(result.output)
# > width=10 height=20 depth=30 units='cm'
