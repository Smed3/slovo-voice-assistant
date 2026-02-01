"""
Structured reasoning models for Slovo Agent Runtime.

These Pydantic models enable structured LLM outputs for agent reasoning,
uncertainty signaling, and clarification requests.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Uncertainty & Clarification Models
# =============================================================================


class UncertaintyLevel(str, Enum):
    """Level of uncertainty in a response or interpretation."""

    CERTAIN = "certain"  # High confidence, no clarification needed
    LIKELY = "likely"  # Reasonable confidence
    UNCERTAIN = "uncertain"  # Low confidence, may need clarification
    UNKNOWN = "unknown"  # Cannot determine, definitely needs clarification


class ClarificationReason(str, Enum):
    """Reason why clarification is needed."""

    AMBIGUOUS_INTENT = "ambiguous_intent"
    MISSING_PARAMETERS = "missing_parameters"
    MULTIPLE_INTERPRETATIONS = "multiple_interpretations"
    CONFLICTING_INFORMATION = "conflicting_information"
    OUT_OF_SCOPE = "out_of_scope"
    RISKY_ACTION = "risky_action"
    INSUFFICIENT_CONTEXT = "insufficient_context"


class ClarificationRequest(BaseModel):
    """Request for user clarification."""

    needed: bool = Field(
        description="Whether clarification is needed before proceeding"
    )
    reason: ClarificationReason | None = Field(
        default=None, description="Why clarification is needed"
    )
    question: str | None = Field(
        default=None, description="The question to ask the user"
    )
    options: list[str] = Field(
        default_factory=list,
        description="Suggested options for the user to choose from",
    )
    context: str | None = Field(
        default=None, description="Additional context about what was unclear"
    )


# =============================================================================
# Intent Interpretation Models
# =============================================================================


class DetectedLanguage(BaseModel):
    """Detected language in user input."""

    code: str = Field(description="ISO 639-1 language code")
    name: str = Field(description="Human-readable language name")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")


class ExtractedEntity(BaseModel):
    """An entity extracted from user input."""

    type: str = Field(description="Entity type (e.g., 'date', 'location', 'person')")
    value: str = Field(description="The extracted value")
    original_text: str = Field(description="Original text span")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence")


class IntentAnalysis(BaseModel):
    """Structured LLM output for intent interpretation."""

    primary_intent: str = Field(description="The primary user intent")
    intent_type: str = Field(
        description="Type of intent: question, command, conversation, tool_request"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Intent confidence")

    # Language detection
    primary_language: DetectedLanguage = Field(description="Primary language detected")
    secondary_languages: list[DetectedLanguage] = Field(
        default_factory=list,
        description="Other languages detected (for code-switching)",
    )

    # Entity extraction
    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="Extracted entities"
    )

    # Tool requirements
    requires_tool: bool = Field(
        default=False, description="Whether a tool is needed to fulfill request"
    )
    suggested_tools: list[str] = Field(
        default_factory=list, description="Suggested tools that could help"
    )

    # Clarification
    clarification: ClarificationRequest = Field(
        default_factory=lambda: ClarificationRequest(needed=False),
        description="Clarification request if needed",
    )

    # Reasoning trace
    reasoning: str = Field(description="Explanation of the interpretation process")


# =============================================================================
# Planning Models
# =============================================================================


class PlannedAction(BaseModel):
    """A single planned action in execution."""

    step_number: int = Field(description="Step number in sequence")
    action_type: str = Field(
        description="Type: llm_response, tool_execution, memory_retrieval, clarification"
    )
    description: str = Field(description="Human-readable description of the action")
    tool_name: str | None = Field(default=None, description="Tool to use if applicable")
    tool_parameters: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the tool"
    )
    depends_on: list[int] = Field(
        default_factory=list, description="Step numbers this depends on"
    )
    estimated_duration_ms: int | None = Field(
        default=None, description="Estimated execution time"
    )


class RiskAssessment(BaseModel):
    """Risk assessment for a plan."""

    level: str = Field(description="Risk level: low, medium, high, critical")
    factors: list[str] = Field(
        default_factory=list, description="Factors contributing to risk"
    )
    mitigations: list[str] = Field(
        default_factory=list, description="Suggested risk mitigations"
    )
    requires_approval: bool = Field(
        default=False, description="Whether user approval is required"
    )


class ExecutionPlanAnalysis(BaseModel):
    """Structured LLM output for execution planning."""

    can_fulfill: bool = Field(
        description="Whether the request can be fulfilled with available capabilities"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Plan confidence")

    # The plan
    steps: list[PlannedAction] = Field(
        default_factory=list, description="Ordered list of actions to take"
    )

    # Complexity assessment
    complexity: str = Field(
        description="Complexity level: simple, moderate, complex, very_complex"
    )
    estimated_total_duration_ms: int | None = Field(
        default=None, description="Estimated total execution time"
    )

    # Risk assessment
    risk: RiskAssessment = Field(
        default_factory=lambda: RiskAssessment(level="low"),
        description="Risk assessment",
    )

    # Missing capabilities
    missing_capabilities: list[str] = Field(
        default_factory=list,
        description="Capabilities needed but not currently available",
    )
    requires_tool_discovery: bool = Field(
        default=False, description="Whether new tools need to be discovered"
    )

    # Clarification
    clarification: ClarificationRequest = Field(
        default_factory=lambda: ClarificationRequest(needed=False),
        description="Clarification request if needed before planning",
    )

    # Reasoning
    reasoning: str = Field(description="Explanation of the planning process")


# =============================================================================
# Verification Models
# =============================================================================


class VerificationIssue(BaseModel):
    """A specific issue found during verification."""

    severity: str = Field(description="Severity: info, warning, error, critical")
    category: str = Field(
        description="Category: format, accuracy, completeness, safety, consistency"
    )
    description: str = Field(description="Description of the issue")
    suggestion: str | None = Field(
        default=None, description="Suggested fix or improvement"
    )


class VerificationAnalysis(BaseModel):
    """Structured LLM output for result verification."""

    is_valid: bool = Field(description="Whether the result is valid overall")
    confidence: float = Field(ge=0.0, le=1.0, description="Verification confidence")

    # Quality assessment
    accuracy_score: float = Field(
        ge=0.0, le=1.0, description="Estimated accuracy of the result"
    )
    completeness_score: float = Field(
        ge=0.0, le=1.0, description="How completely the request was addressed"
    )
    relevance_score: float = Field(
        ge=0.0, le=1.0, description="How relevant the result is to the request"
    )

    # Issues found
    issues: list[VerificationIssue] = Field(
        default_factory=list, description="Issues found during verification"
    )

    # Self-correction
    requires_correction: bool = Field(
        default=False, description="Whether correction is needed"
    )
    correction_strategy: str | None = Field(
        default=None, description="Strategy for correcting issues"
    )

    # Uncertainty
    uncertainty_level: UncertaintyLevel = Field(
        default=UncertaintyLevel.CERTAIN,
        description="Level of uncertainty in the result",
    )
    uncertainty_factors: list[str] = Field(
        default_factory=list,
        description="Factors contributing to uncertainty",
    )

    # Reasoning
    reasoning: str = Field(description="Explanation of the verification process")


# =============================================================================
# Response Generation Models
# =============================================================================


class ResponseTone(str, Enum):
    """Tone of the response."""

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CASUAL = "casual"
    FORMAL = "formal"
    EMPATHETIC = "empathetic"


class ExplanationDetail(BaseModel):
    """A single detail in the explanation."""

    category: str = Field(description="Category: action, reasoning, warning, note")
    content: str = Field(description="The detail content")
    importance: str = Field(description="Importance: high, medium, low")


class ResponseGeneration(BaseModel):
    """Structured LLM output for response generation."""

    response: str = Field(description="The main response to show the user")
    tone: ResponseTone = Field(
        default=ResponseTone.FRIENDLY, description="Tone of the response"
    )

    # Explanation components
    summary: str = Field(description="Brief summary of what was done")
    details: list[ExplanationDetail] = Field(
        default_factory=list, description="Detailed explanation points"
    )

    # Confidence communication
    confidence_statement: str | None = Field(
        default=None,
        description="Statement about confidence level if relevant",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Important caveats or limitations to mention",
    )

    # Follow-up
    suggested_follow_ups: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions or actions",
    )

    # Formatting
    use_markdown: bool = Field(
        default=True, description="Whether to use markdown formatting"
    )


# =============================================================================
# Conversation Context Models
# =============================================================================


class ConversationContext(BaseModel):
    """Context from conversation history for LLM calls."""

    recent_topics: list[str] = Field(
        default_factory=list, description="Recent conversation topics"
    )
    user_preferences: dict[str, Any] = Field(
        default_factory=dict, description="Known user preferences"
    )
    pending_clarifications: list[ClarificationRequest] = Field(
        default_factory=list, description="Unanswered clarification requests"
    )
    conversation_language: str = Field(
        default="en", description="Primary conversation language"
    )
    turn_count: int = Field(default=0, description="Number of turns in conversation")


# =============================================================================
# Agent State Models
# =============================================================================


class AgentState(BaseModel):
    """Current state of the agent pipeline."""

    conversation_id: str
    turn_id: str
    current_stage: str = Field(
        description="Current stage: interpreting, planning, executing, verifying, explaining"
    )

    # Accumulated data
    intent_analysis: IntentAnalysis | None = None
    execution_plan: ExecutionPlanAnalysis | None = None
    verification: VerificationAnalysis | None = None

    # Execution tracking
    executed_steps: list[int] = Field(default_factory=list)
    step_outputs: dict[int, Any] = Field(default_factory=dict)

    # Error tracking
    errors: list[str] = Field(default_factory=list)

    # Context
    context: ConversationContext = Field(default_factory=ConversationContext)
