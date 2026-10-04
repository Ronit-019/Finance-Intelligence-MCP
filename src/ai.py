import json
import os

from dotenv import load_dotenv
from groq import AsyncGroq
from fastmcp import Client

load_dotenv()

client = AsyncGroq(
    api_key=os.getenv("GROQ_API_KEY")
)

MCP_URL = os.getenv(
    "MCP_URL",
    "http://127.0.0.1:8000/mcp"
)

MODEL = "openai/gpt-oss-120b"


SYSTEM_PROMPT = """
You are Finance Intelligence, a personal finance assistant.

You help users understand and manage their expenses,
budgets, spending and financial health.

You have access to MCP tools that operate on the user's
financial data.

Use an MCP tool whenever the user's question requires
actual financial data or an action.

Never invent financial numbers.

IMPORTANT TOOL RULES:

1. Always provide valid values for required MCP tool parameters.

2. Never send null for a parameter that expects a string,
   number, boolean, or other concrete value.

3. If a tool parameter is optional and the user did not provide
   it, omit the parameter instead of sending null.

4. For financial_health_score:
   - reference_month must use YYYY-MM format.
   - If the user asks about their current financial health
     without specifying a month, use the current month.
   - Do not pass reference_month as null.

5. If the user does not specify a date for an expense query,
   interpret "today" as today's date when appropriate.

Never invent financial numbers.

After receiving tool results, explain them clearly and
concisely to the user.

For destructive actions such as deleting expenses,
only execute the tool when the user clearly requested it.

RESPONSE FORMAT:

Always format your final response using Markdown.

Use:
- **bold** for important values and conclusions
- headings for sections
- numbered lists for steps or recommendations
- bullet lists for related items
- Markdown tables when comparing multiple metrics
- short paragraphs for explanations

Do not return Markdown syntax as escaped text.
Do not wrap the entire response in a code block.

"""

async def chat_with_finance(user_message: str, auth_token: str):

    async with Client(MCP_URL) as mcp:

        tools_result = await mcp.list_tools()

        groq_tools = []

        for tool in tools_result:

            groq_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                }
            })

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_message
            }
        ]

        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=groq_tools,
            tool_choice="auto",
            temperature=0
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            return assistant_message.content

        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in assistant_message.tool_calls
            ],
        })

        for tool_call in assistant_message.tool_calls:

            tool_name = tool_call.function.name

            arguments = json.loads(
                tool_call.function.arguments
            )

            arguments["auth_token"] = auth_token

            result = await mcp.call_tool(
                tool_name,
                arguments
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": str(result)
            })

        final_response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=groq_tools,
            tool_choice="none",
            temperature=0
        )
    
        return final_response.choices[0].message.content