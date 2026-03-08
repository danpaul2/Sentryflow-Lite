

from typing import Dict, List
from utils import extract_keywords, compare_similarity
from logger import logger
from client import generate_tool

class AgentRouter:
    """Enhanced agent that routes prompts to appropriate tools"""
    
    def __init__(self):
        self.tool_definitions = {
            "send_email": {
                "keywords": ["email", "mail", "send", "message", "contact", "notify"],
                "priority": 2,
                "description": "Send an email message"
            },
            "search_web": {
                "keywords": ["search", "find", "look up", "google", "query", "information"],
                "priority": 1,
                "description": "Search the web for information"
            },
            "create_report": {
                "keywords": ["report", "document", "create", "generate", "write", "summary"],
                "priority": 3,
                "description": "Create a report or document"
            }
        }
        
        # Example prompts for similarity matching
        self.example_mappings = {
            "send_email": [
                "send an email to john about the meeting",
                "email the team about project updates",
                "notify sarah via email"
            ],
            "search_web": [
                "search for recent ai developments",
                "find information about quantum computing",
                "look up weather forecast"
            ],
            "create_report": [
                "generate a quarterly report",
                "write a summary of findings",
                "create documentation for the project"
            ]
        }
    
    def score_tool_match(self, prompt: str, tool_name: str) -> float:
        """
        Score how well a prompt matches a tool
        
        Returns:
            Match score (0-1)
        """
        prompt_lower = prompt.lower()
        tool_def = self.tool_definitions[tool_name]
        
        # Keyword matching score
        keyword_matches = sum(1 for kw in tool_def["keywords"] if kw in prompt_lower)
        keyword_score = min(keyword_matches / len(tool_def["keywords"]), 1.0)
        
        # Similarity to example prompts
        examples = self.example_mappings[tool_name]
        similarities = [compare_similarity(prompt, example) for example in examples]
        similarity_score = max(similarities) if similarities else 0.0
        
        # Combined score (weighted)
        final_score = (keyword_score * 0.6) + (similarity_score * 0.4)
        
        return final_score
    
    def select_tool(self, prompt: str) -> str:
        """
        Select the best tool for the given prompt
        
        Returns:
            Tool name
        """
        # Score all tools
        scores = {}
        for tool_name in self.tool_definitions.keys():
            scores[tool_name] = self.score_tool_match(prompt, tool_name)
        
        # Get the tool with highest score
        best_tool = max(scores.items(), key=lambda x: x[1])
        
        logger.debug(f"Tool selection scores", scores=scores, selected=best_tool[0])
        
        return best_tool[0]
    
    def extract_parameters(self, prompt: str, tool_name: str) -> Dict:
        """
        Extract parameters from prompt based on tool type
        
        Returns:
            Dictionary of parameters
        """
        prompt_lower = prompt.lower()
        keywords = extract_keywords(prompt)
        
        if tool_name == "send_email":
            return self._extract_email_params(prompt, prompt_lower, keywords)
        elif tool_name == "search_web":
            return self._extract_search_params(prompt, prompt_lower, keywords)
        elif tool_name == "create_report":
            return self._extract_report_params(prompt, prompt_lower, keywords)
        else:
            return {}
    
    def _extract_email_params(self, prompt: str, prompt_lower: str, keywords: List[str]) -> Dict:
        """Extract email parameters"""
        params = {
            "to": "unknown@company.com",
            "subject": "Automated Message",
            "body": prompt
        }
        
        # Try to extract recipient
        if " to " in prompt_lower:
            parts = prompt_lower.split(" to ")
            if len(parts) > 1:
                recipient_part = parts[1].split()[0]
                params["to"] = f"{recipient_part}@company.com"
        
        # Try to extract subject
        if "about" in prompt_lower:
            parts = prompt.split("about")
            if len(parts) > 1:
                subject = parts[1].strip().split('.')[0]
                params["subject"] = subject[:50]  # Limit subject length
        
        # Detect potential sensitive content
        sensitive_keywords = ["password", "credentials", "confidential", "secret"]
        if any(kw in prompt_lower for kw in sensitive_keywords):
            params["body"] = f"[Contains sensitive information] {prompt}"
        
        return params
    
    def _extract_search_params(self, prompt: str, prompt_lower: str, keywords: List[str]) -> Dict:
        """Extract search parameters"""
        # Remove search-related words to get actual query
        search_words = ["search", "find", "look up", "google", "query", "for"]
        query_keywords = [kw for kw in keywords if kw not in search_words]
        
        query = " ".join(query_keywords) if query_keywords else prompt
        
        return {
            "query": query[:200],  # Limit query length
            "max_results": 10
        }
    
    def _extract_report_params(self, prompt: str, prompt_lower: str, keywords: List[str]) -> Dict:
        """Extract report parameters"""
        params = {
            "title": "Generated Report",
            "content": prompt
        }
        
        # Try to extract title
        if "report" in prompt_lower:
            parts = prompt_lower.split("report")
            if len(parts) > 1:
                title_part = parts[1].strip().split('.')[0]
                params["title"] = title_part[:100]
        
        # Determine format based on keywords
        if any(word in prompt_lower for word in ["pdf", "document"]):
            params["format"] = "pdf"
        elif any(word in prompt_lower for word in ["spreadsheet", "excel", "csv"]):
            params["format"] = "csv"
        else:
            params["format"] = "text"
        
        return params
    
    def decide(self, prompt: str) -> Dict:
        """
        Main decision function - select tool and extract parameters
        
        Returns:
            Tool JSON with tool name and parameters
        """
        # Select appropriate tool
        tool_spec = generate_tool(prompt)

        if tool_spec is None:
            raise Exception("Tool Generation failed!")
        
        tool_name = tool_spec["tool_name"]

        # Extract parameters
        parameters = tool_spec.get("parameters",{})        
        tool_json = {
            "tool": tool_name,
            "parameters": parameters,
            "description": tool_spec.get("description", "Dynamically created tool"),
            "category": tool_spec.get("operation_type", "Dynamic"),
            "risk_level": tool_spec.get("risk_level", "medium")
        }
        
        logger.info(f"Agent decision made", tool=tool_name, prompt_length=len(prompt))
        
        return tool_json

# Global agent instance
agent = AgentRouter()

# Convenience function for backward compatibility
def agent_decide(prompt: str) -> Dict:
    """Backward compatible function"""
    return agent.decide(prompt)
