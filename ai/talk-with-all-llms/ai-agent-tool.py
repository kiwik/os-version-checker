import tomllib

from httpx import AsyncClient
from pydantic_ai import Agent, ModelRetry, UnexpectedModelBehavior, \
    capture_run_messages
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

with open('config.toml', 'rb') as f:
    config_data = tomllib.load(f)

_headers = {'Authorization':
                'Bearer {}'.format(config_data['free-api-qwen']['api_key'])}

httpx_client = AsyncClient(
    # proxy=config_data['proxy']['url'],
    # verify=config_data['proxy']['verify'],
    headers=_headers)

model = OpenAIModel(config_data['free-api-qwen']['model_name'],
                    provider=OpenAIProvider(
                        base_url=config_data['free-api-qwen']['base_url'],
                        api_key=config_data['free-api-qwen']['api_key'],
                        http_client=httpx_client))

agent = Agent(model)


@agent.tool_plain
def calc_volume(size: int) -> int:
    if size == 42:
        return size ** 3
    else:
        raise ModelRetry('再试一次。')


with capture_run_messages() as messages:
    try:
        result = agent.run_sync(
            'Please get me the volume of a box with size 6.')
    except UnexpectedModelBehavior as e:
        print('An error occurred:', e)
        # > An error occurred: Tool exceeded max retries count of 1
        print('cause:', repr(e.__cause__))
        # > cause: ModelRetry('Please try again.')
        print('messages:', messages)
        """
        messages:
        [
            ModelRequest(
                parts=[
                    UserPromptPart(
                        content='Please get me the volume of a box with size 6.',
                        timestamp=datetime.datetime(...),
                    )
                ]
            ),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name='calc_volume',
                        args={'size': 6},
                        tool_call_id='pyd_ai_tool_call_id',
                    )
                ],
                usage=Usage(
                    requests=1, request_tokens=62, response_tokens=4, total_tokens=66
                ),
                model_name='gpt-4o',
                timestamp=datetime.datetime(...),
            ),
            ModelRequest(
                parts=[
                    RetryPromptPart(
                        content='Please try again.',
                        tool_name='calc_volume',
                        tool_call_id='pyd_ai_tool_call_id',
                        timestamp=datetime.datetime(...),
                    )
                ]
            ),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name='calc_volume',
                        args={'size': 6},
                        tool_call_id='pyd_ai_tool_call_id',
                    )
                ],
                usage=Usage(
                    requests=1, request_tokens=72, response_tokens=8, total_tokens=80
                ),
                model_name='gpt-4o',
                timestamp=datetime.datetime(...),
            ),
        ]
        """
    else:
        print(result.output)
