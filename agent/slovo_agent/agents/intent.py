"""
Intent Interpreter Agent

Parses voice/text input, detects language(s), and normalizes intent.
"""

import structlog

from slovo_agent.models import Intent, IntentType

logger = structlog.get_logger(__name__)


class IntentInterpreterAgent:
    """
    Agent responsible for interpreting user intent.
    
    Responsibilities:
    - Parse natural language input
    - Detect language(s) and handle code-switching
    - Extract entities and intent type
    - Normalize for downstream processing
    """
    
    def __init__(self) -> None:
        logger.info("Intent interpreter agent initialized")
    
    async def interpret(self, message: str) -> Intent:
        """
        Interpret a user message and extract intent.
        """
        logger.debug("Interpreting message", message_length=len(message))
        
        # Basic intent classification
        # TODO: Use LLM for more sophisticated interpretation
        message_lower = message.lower().strip()
        
        # Simple heuristics for intent type
        if message_lower.endswith("?") or any(
            message_lower.startswith(q) for q in ["what", "how", "why", "when", "where", "who", "can you", "could you"]
        ):
            intent_type = IntentType.QUESTION
        elif any(
            message_lower.startswith(c) for c in ["please", "can you", "could you", "i need", "i want", "help me"]
        ):
            intent_type = IntentType.COMMAND
        else:
            intent_type = IntentType.CONVERSATION
        
        # Check if tool might be needed
        requires_tool = any(
            keyword in message_lower 
            for keyword in ["search", "find", "look up", "calculate", "convert", "translate"]
        )
        
        return Intent(
            type=intent_type,
            text=message,
            language="en",  # TODO: Implement language detection
            confidence=0.8,
            requires_tool=requires_tool,
        )
