"""
Notion Weather Assistant - Enhanced conversational AI assistant for Notion
and Weather using MCP (Model Context Protocol) and OpenAI.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

from mcp_orchestrator import MCPOrchestrator

load_dotenv()

class NotionAssistant:

    def __init__(self, user_email: str ="manoharreddygujjula7800@gmail.com"):
        self.user_email= user_email
        self.openai_client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"))
        self.conversation_history: List[Dict[str, Any]] = []
        self.max_iterations = 10 # Prent infinite loops

        #System Prompt
        self.system_prompt = f"You Notion Assistant Pro, an Advanced AI assisstant for {user_email} that can manage both weather  and Notion workspace"

    async def _call_tool_safely(self, orchestrator: MCPOrchestrator, tool_name: str, args: Dict[str,Any], tool_call_id: str) -> Dict[str, Any]:
        """Safely call a tool and return a standardized result."""

        try:
            server, result = await orchestrator.call_tool_by_fullname(tool_name, args)
            
            return {
                "tool_call_id": tool_call_id,
                "role" : "tool",
                "name" : tool_name,
                "content" : str(result)
            }
        except Exception as e:
            return {
                "tool_call_id" : tool_call_id,
                "role": "tool",
                "name" : tool_name,
                "content" : f"Error: {str(e)}"
            }

    async def _excecute_tool_calls(self, orchestrator: MCPOrchestrator, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """ Excecute multiple tool calls in parallel and returns results."""
        tasks=[]
        for tc in tool_calls:
            tool_name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            task = self._call_tool_safely(orchestrator, tool_name, args, tc.id)
            tasks.append(task)
        return await asyncio.gather(*tasks)

    async def run_chat(self):
        """Main chat loop for Notion Assistant. """
        print("Notion - Weather Agnet")
        print("="*70)
        print(f"Managing notion for: {self.user_email}")
        print("Type 'quit' to exit, 'help' for commands")
        print("=" * 70)

        async with MCPOrchestrator() as orchestrator:

            while True:
                try:
                    user_input = input("You: ").strip()

                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        print("GoodBye! Notion Assistant signing off.")
                        break
                    
                    if user_input.lower() == 'help':
                        self._show_help()
                        continue
                    
                    if not user_input:
                        continue

                    self.conversation_history.append({
                        "role": "user",
                        "content": user_input
                    })

                    tool_specs = await orchestrator.get_all_tool_specs()

                    messages = [{"role": "system", "content": self.system_prompt}]

                    messages.extend(self.conversation_history[-10:]) # last 10 messages

                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        tools = [{
                            "type":"function",
                            "function": {
                                "name" : spec["name"],
                                "description" : spec["description"],
                                "parameters" : spec["inputSchema"]
                            }
                        }for spec in tool_specs],
                        tool_choice = "auto"
                    )

                    message = response.choices[0].message

                    assistant_message= {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": getattr(message, "tool_calls", None)
                    }
                    self.conversation_history.append(assistant_message)

                    if message.tool_calls:

                        tool_messages= await self._execute_tool_calls(orchestrator, list(message.tool_calls))

                        self.conversation_history.extend(tool_messages)

                        iteration =0

                        while iteration< self.max_iterations:
                            iteration+=1

                            follow_up_messages = [{"role":"system", "content": self.system_prompt}]

                            recent_history = self.conversation_history[-10:]
                            follow_up_messages.extend(recent_history)

                            follow_up_response = self.openai_client.chat.completions.create(
                                model="gpt-4o",
                                messages= follow_up_messages,
                                tools = [{
                                    "type":"function",
                                    "function": {
                                        "name": spec["name"],
                                        "description": spec["description"],
                                        "parameters" : spec["inputSchema"]
                                    }
                                } for spec in tool_specs],
                                tool_choice="auto"
                            )

                            follow_up_message = follow_up_response.choice[0].message

                            if follow_up_message.tool_calls:

                                additional_tool_messages = await self._execute_tool_calls(orchestrator, list(follow_up_message.tool_calls))

                                self.conversation_history.append({
                                    "role":"assistant",
                                    "content": follow_up_message.content or "",
                                    "tool_calls": getattr(follow_up_message, "tool_calls", None)
                                })

                                self.conversation_history.extend(additional_tool_messages)
                            else:

                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content" : follow_up_message.content or ""
                                })

                                if follow_up_message.content:
                                    print(f"\n🤖 Assistant: {follow_up_message.content}")
                                break
                        else:
                            print("\n🤖 Assistant : I've completed the requested operations. Is there anything else I can help you with?")
                    else:
                        print(f"\n🤖 Assistant : {message.content}")
                
                except KeyboardInterrupt:
                    print("\n Goodbye! Assistant signing off.")
                    break
                except Exception as e:
                    print(f"\n Error: {str(e)}")
                    print("Please try again or type 'help' for assistance.")



async def main():
    """Main entry point."""
    assistant = NotionAssistant()
    await assistant.run_chat()
    

if __name__ == "__main__":
    asyncio.run(main())