"""
Intent Interpreter Agent

Parses voice/text input, detects language(s), and normalizes intent.
Uses LLM for sophisticated understanding with structured outputs.
"""

import structlog

from slovo_agent.llm.base import LLMMessage, LLMProvider, MessageRole
from slovo_agent.models import (
    ClarificationRequest,
    Intent,
    IntentAnalysis,
    IntentType,
)

logger = structlog.get_logger(__name__)


# System prompt for intent interpretation
INTENT_SYSTEM_PROMPT = """You are an intent interpretation system for a voice assistant called Slovo.
Your job is to analyze user messages and extract structured information about their intent.

You must:
1. Identify the primary intent (what the user wants to accomplish)
2. Classify the intent type (question, command, conversation, tool_request, clarification)
3. Detect the language(s) used, including code-switching
4. Extract relevant entities (dates, locations, names, numbers, etc.)
5. Determine if a tool/external capability is needed
6. Assess your confidence level honestly
7. Request clarification if the intent is ambiguous or missing critical information

Be precise and thorough in your analysis. If you're uncertain about something, say so.
Always provide reasoning for your interpretation."""


class IntentInterpreterAgent:
    """
    Agent responsible for interpreting user intent.

    Responsibilities:
    - Parse natural language input using LLM
    - Detect language(s) and handle code-switching
    - Extract entities and intent type
    - Signal uncertainty and request clarification when needed
    - Normalize for downstream processing
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider
        logger.info(
            "Intent interpreter agent initialized",
            has_llm=llm_provider is not None,
        )

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider."""
        self.llm = provider
        logger.info("LLM provider updated for intent interpreter")

    async def interpret(
        self,
        message: str,
        conversation_context: str | None = None,
    ) -> Intent:
        """
        Interpret a user message and extract intent.

        Args:
            message: The user's message to interpret
            conversation_context: Optional context from conversation history

        Returns:
            Parsed Intent object
        """
        logger.debug("Interpreting message", message_length=len(message))

        # Use LLM for sophisticated interpretation if available
        if self.llm:
            analysis = await self._llm_interpret(message, conversation_context)
            return self._analysis_to_intent(message, analysis)

        # Fallback to simple heuristic interpretation
        return self._heuristic_interpret(message)

    async def _llm_interpret(
        self,
        message: str,
        conversation_context: str | None = None,
    ) -> IntentAnalysis:
        """Use LLM for sophisticated intent interpretation."""
        assert self.llm is not None

        # Build the user message
        user_content = f"Analyze this user message:\n\n\"{message}\""

        if conversation_context:
            user_content = (
                f"Conversation context:\n{conversation_context}\n\n{user_content}"
            )

        messages = [LLMMessage(role=MessageRole.USER, content=user_content)]

        logger.debug("Calling LLM for intent interpretation")

        response = await self.llm.generate_structured(
            messages=messages,
            output_schema=IntentAnalysis,
            system_prompt=INTENT_SYSTEM_PROMPT,
        )

        if response.structured_output:
            logger.debug(
                "Intent analysis complete",
                intent=response.structured_output.primary_intent,
                confidence=response.structured_output.confidence,
            )
            return response.structured_output

        # If structured output failed, create a default analysis
        logger.warning("Structured output parsing failed, using defaults")
        return IntentAnalysis(
            primary_intent=message,
            intent_type="unknown",
            confidence=0.5,
            primary_language={
                "code": "en",
                "name": "English",
                "confidence": 0.5,
            },
            reasoning="Failed to parse structured output from LLM",
        )

    def _analysis_to_intent(self, original_text: str, analysis: IntentAnalysis) -> Intent:
        """Convert IntentAnalysis to Intent model."""
        # Map string intent type to enum
        type_mapping = {
            "question": IntentType.QUESTION,
            "command": IntentType.COMMAND,
            "conversation": IntentType.CONVERSATION,
            "tool_request": IntentType.TOOL_REQUEST,
            "clarification": IntentType.CLARIFICATION,
        }
        intent_type = type_mapping.get(
            analysis.intent_type.lower(), IntentType.UNKNOWN
        )

        # Extract entities as dict
        entities = {e.type: e.value for e in analysis.entities}

        # Determine tool hint from suggested tools
        tool_hint = analysis.suggested_tools[0] if analysis.suggested_tools else None

        return Intent(
            type=intent_type,
            text=original_text,
            language=analysis.primary_language.code,
            entities=entities,
            confidence=analysis.confidence,
            requires_tool=analysis.requires_tool,
            tool_hint=tool_hint,
        )

    def _heuristic_interpret(self, message: str) -> Intent:
        """Fallback heuristic interpretation without LLM."""
        logger.debug("Using heuristic interpretation (no LLM)")

        message_lower = message.lower().strip()

        # Simple heuristics for intent type
        if message_lower.endswith("?") or any(
            message_lower.startswith(q)
            for q in ["what", "how", "why", "when", "where", "who", "can you", "could you"]
        ):
            intent_type = IntentType.QUESTION
        elif any(
            message_lower.startswith(c)
            for c in ["please", "can you", "could you", "i need", "i want", "help me"]
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
            language="en",
            confidence=0.6,  # Lower confidence for heuristic
            requires_tool=requires_tool,
        )

    def get_clarification_request(
        self, analysis: IntentAnalysis
    ) -> ClarificationRequest | None:
        """Extract clarification request from analysis if needed."""
        if analysis.clarification.needed:
            return analysis.clarification
        return None
