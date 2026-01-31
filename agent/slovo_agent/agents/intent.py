"""
Intent Interpreter Agent

Parses voice/text input, detects language(s), and normalizes intent.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger()


class IntentType(str, Enum):
    """Types of user intents."""
    
    QUESTION = "question"
    COMMAND = "command"
    CONVERSATION = "conversation"
    TOOL_REQUEST = "tool_request"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """Parsed user intent."""
    
    type: IntentType
    text: str
    language: str = "en"
    entities: dict = None
    confidence: float = 1.0
    requires_tool: bool = False
    tool_hint: Optional[str] = None
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = {}


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
