from openai import OpenAI
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with SGLang server for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage - CRITICAL RULES:
- **ALWAYS use the search tool for ANY question that could relate to the course materials**
- This includes questions about: courses, lessons, topics, concepts, examples, assignments, or any educational content
- **One search per query maximum**
- Only skip searching for purely procedural questions (e.g., "how do I use this chatbot?")
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **ALWAYS search first** unless the question is clearly not about course content
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results" or "according to the search"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, base_url: str, model: str):
        self.client = OpenAI(
            base_url=base_url,
            api_key="EMPTY"  # SGLang doesn't require API key
        )
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0.1,  # Slightly higher to help with tool usage
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build messages list with system prompt
        messages = []

        # Add system prompt and conversation history
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )
        messages.append({"role": "system", "content": system_content})

        # Add user query
        messages.append({"role": "user", "content": query})

        # Prepare API call parameters
        api_params = {
            **self.base_params,
            "messages": messages
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = "auto"

        # Get response from SGLang
        response = self.client.chat.completions.create(**api_params)

        # Handle tool execution if needed
        message = response.choices[0].message
        if message.tool_calls and tool_manager:
            return self._handle_tool_execution(message, messages, tools, tool_manager)

        # Return direct response
        return message.content

    def _handle_tool_execution(self, assistant_message, messages: List[Dict[str, Any]],
                               tools: List, tool_manager):
        """
        Handle execution of tool calls and get follow-up response.

        Args:
            assistant_message: The message containing tool calls
            messages: Existing messages list
            tools: Available tools
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        # Add AI's tool call message
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })

        # Execute all tool calls and collect results
        import json
        for tool_call in assistant_message.tool_calls:
            # Parse arguments
            tool_args = json.loads(tool_call.function.arguments)

            # Execute tool
            tool_result = tool_manager.execute_tool(
                tool_call.function.name,
                **tool_args
            )

            # Add tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

        # Prepare final API call with tools still available
        final_params = {
            **self.base_params,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto"
        }

        # Get final response
        final_response = self.client.chat.completions.create(**final_params)
        return final_response.choices[0].message.content
