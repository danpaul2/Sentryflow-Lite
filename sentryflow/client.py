import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"



def call_mistral(prompt):

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }
    )

    try:
        data = response.json()
    except Exception:
        raise Exception(f"Ollama returned non-JSON: {response.text}")

    if isinstance(data, dict):

        if "response" in data:
            return data["response"]

        if "message" in data and "content" in data["message"]:
            return data["message"]["content"]

        if "error" in data:
            raise Exception(f"Ollama error: {data['error']}")

    raise Exception(f"Unexpected Ollama response: {data}")

   


def generate_tool(user_prompt):

    prompt = f"""
You are an AI system that converts user requests into tool specifications.

User request:
{user_prompt}

Return JSON:

{{
"tool_name": "short_snake_case_name",
 "description": "what the tool does",
 "operation_type": "information|communication|document|database",
 "parameters": {{}},
 "risk_level": "low|medium|high"
}}

Rules:
- tool_name must be short
- use snake_case
- avoid spaces
"""

    response = call_mistral(prompt)
    if response is None:
        return None
    try:
        return json.loads(response)
    except Exception as e:
        print("Failed to parse tool JSON")
        print("Response:",response)
        return None



def judge_tool(user_prompt, tool):

    if not isinstance(tool, dict):
        return {"allowed": False, "reason": "Invalid tool"}

    if tool.get("risk_level") == "high":
        return {"allowed": False, "reason": "High risk tool blocked"}

    tool_name = tool.get("tool_name")
    if tool_name and "delete" in tool_name:
        return {"allowed": False, "reason": "Destructive tool blocked"}

    return {"allowed": True, "reason": "Tool approved"}



def search_web(params):
    query = params.get("query", "")
    return f"[Simulated web search results for: {query}]"


def create_report(params):
    topic = params.get("topic", "")
    return f"[Simulated report created for: {topic}]"


def send_email(params):
    recipient = params.get("recipient", "")
    message = params.get("message", "")
    return f"[Simulated email sent to {recipient}: {message}]"


def execute_tool(tool):

    op = tool.get("operation_type")
    params = tool.get("parameters") or {}

    if op == "information_retrieval":
        return search_web(params)

    if op == "document_creation":
        return create_report(params)

    if op == "communication":
        return send_email(params)

    return "Unknown operation"



def run_agent():

    user_prompt = input("Enter request: ")

    print("\nGenerating tool...")
    tool = generate_tool(user_prompt)

    print("\nGenerated Tool:")
    print(tool)

    print("\nRunning judge...")
    decision = judge_tool(user_prompt, tool)

    print(decision)

    if decision["allowed"]:

        print("\nExecuting tool...")
        result = execute_tool(tool)

        print("\nResult:")
        print(result)

    else:
        print("\nExecution blocked:", decision["reason"])



if __name__ == "__main__":
    run_agent()