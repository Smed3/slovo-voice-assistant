"""
Tool Discovery Agent

Phase 4: Searches for relevant APIs, loads and parses OpenAPI documentation,
and generates tool manifests for approval.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import structlog
import yaml

from slovo_agent.llm.base import LLMMessage, LLMProvider, MessageRole
from slovo_agent.models import (
    ToolDiscoveryRequest,
    ToolManifestCreate,
    ToolSourceType,
)
from slovo_agent.tools.repository import ToolRepository

logger = structlog.get_logger(__name__)


# System prompt for OpenAPI analysis
OPENAPI_ANALYSIS_PROMPT = """You are an API analysis system for a voice assistant called Slovo.
Your job is to analyze OpenAPI specifications and extract tool capabilities.

Given an OpenAPI specification, extract:
1. Tool name (from the API title, make it URL-safe and lowercase)
2. Version (from the API version)
3. Description (clear, concise description of what the tool does)
4. Capabilities (list of operations/endpoints the tool provides)
5. Parameters schema (JSON schema for each capability)

Guidelines:
1. Focus on practical, useful operations that would benefit a voice assistant
2. Simplify complex APIs - group related operations into capabilities
3. Generate clear, user-friendly descriptions
4. Extract parameter schemas that are easy to validate
5. Identify security requirements (API keys, OAuth, etc.)

Return a JSON object with:
{
  "name": "tool-name",
  "version": "1.0.0",
  "description": "What this tool does",
  "capabilities": [
    {
      "name": "capability_name",
      "description": "What this capability does",
      "endpoint": "/api/endpoint",
      "method": "GET",
      "parameters": {"type": "object", "properties": {...}}
    }
  ],
  "requires_auth": true/false,
  "auth_type": "api_key" | "oauth2" | "basic" | null
}"""


class ToolDiscoveryAgent:
    """
    Agent responsible for discovering and analyzing tools.

    Responsibilities:
    - Load tool manifests from local files
    - Fetch and parse OpenAPI specifications from URLs
    - Analyze API capabilities using LLM
    - Generate tool manifests for approval
    - Integration with tool repository
    """

    def __init__(
        self,
        tool_repository: ToolRepository,
        llm_provider: LLMProvider | None = None,
        openapi_analysis_prompt: str | None = None,
    ) -> None:
        """
        Initialize Tool Discovery Agent.

        Args:
            tool_repository: Repository for tool persistence
            llm_provider: Optional LLM provider for API analysis
            openapi_analysis_prompt: Optional custom prompt for OpenAPI analysis
        """
        self.tool_repo = tool_repository
        self.llm = llm_provider
        self.openapi_analysis_prompt = openapi_analysis_prompt or OPENAPI_ANALYSIS_PROMPT
        self.http_client = httpx.AsyncClient(timeout=30.0)
        logger.info(
            "Tool Discovery Agent initialized",
            has_llm=llm_provider is not None,
            has_custom_prompt=openapi_analysis_prompt is not None,
        )

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider."""
        self.llm = provider
        logger.info("LLM provider updated for tool discovery")

    # =========================================================================
    # Local Manifest Import
    # =========================================================================

    async def import_local_manifest(self, manifest_path: str | Path) -> UUID:
        """
        Import a tool from a local manifest file.

        Args:
            manifest_path: Path to the manifest file (JSON or YAML)

        Returns:
            UUID of the created tool manifest

        Raises:
            FileNotFoundError: If manifest file doesn't exist
            ValueError: If manifest is invalid
        """
        path = Path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        logger.info("Importing local manifest", path=str(path))

        # Load manifest file
        with open(path, "r") as f:
            if path.suffix in [".yaml", ".yml"]:
                manifest_data = yaml.safe_load(f)
            elif path.suffix == ".json":
                manifest_data = json.load(f)
            else:
                raise ValueError(f"Unsupported manifest format: {path.suffix}")

        # Validate required fields
        required_fields = ["name", "version", "description"]
        for field in required_fields:
            if field not in manifest_data:
                raise ValueError(f"Missing required field in manifest: {field}")

        # Extract execution configuration
        execution = manifest_data.get("execution", {})
        execution_type = execution.get("type", "docker")
        docker_image = execution.get("image")
        docker_entrypoint = execution.get("entrypoint")
        execution_timeout = execution.get("timeout", 30)

        # Create tool manifest
        manifest = ToolManifestCreate(
            name=manifest_data["name"],
            version=manifest_data["version"],
            description=manifest_data["description"],
            source_type=ToolSourceType.LOCAL,
            source_location=str(path.absolute()),
            capabilities=manifest_data.get("capabilities", []),
            parameters_schema=manifest_data.get("parameters_schema", {}),
            execution_type=execution_type,
            docker_image=docker_image,
            docker_entrypoint=docker_entrypoint,
            execution_timeout=execution_timeout,
        )

        # Save to repository
        tool_manifest = await self.tool_repo.create_tool_manifest(manifest)

        logger.info(
            "Local manifest imported",
            tool_id=str(tool_manifest.id),
            name=tool_manifest.name,
        )

        return tool_manifest.id

    # =========================================================================
    # OpenAPI URL Ingestion
    # =========================================================================

    async def ingest_openapi_url(self, openapi_url: str) -> UUID:
        """
        Fetch and ingest an OpenAPI specification from a URL.

        Args:
            openapi_url: URL to the OpenAPI spec (JSON or YAML)

        Returns:
            UUID of the created tool manifest

        Raises:
            httpx.HTTPError: If fetching fails
            ValueError: If spec is invalid
        """
        logger.info("Fetching OpenAPI spec from URL", url=openapi_url)

        # Fetch the OpenAPI spec
        try:
            response = await self.http_client.get(openapi_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")

            if "json" in content_type or openapi_url.endswith(".json"):
                openapi_spec = response.json()
            elif "yaml" in content_type or openapi_url.endswith((".yaml", ".yml")):
                openapi_spec = yaml.safe_load(response.text)
            else:
                # Try to parse as JSON first, then YAML
                try:
                    openapi_spec = response.json()
                except json.JSONDecodeError:
                    openapi_spec = yaml.safe_load(response.text)

        except httpx.HTTPError as e:
            logger.error("Failed to fetch OpenAPI spec", url=openapi_url, error=str(e))
            raise

        # Validate OpenAPI spec
        if "openapi" not in openapi_spec and "swagger" not in openapi_spec:
            raise ValueError("Invalid OpenAPI spec: missing version field")

        # Analyze the spec and generate manifest
        manifest = await self._analyze_openapi_spec(openapi_spec, openapi_url)

        # Save to repository
        tool_manifest = await self.tool_repo.create_tool_manifest(manifest)

        logger.info(
            "OpenAPI spec ingested",
            tool_id=str(tool_manifest.id),
            name=tool_manifest.name,
            url=openapi_url,
        )

        return tool_manifest.id

    async def _analyze_openapi_spec(
        self, openapi_spec: dict[str, Any], source_url: str
    ) -> ToolManifestCreate:
        """
        Analyze OpenAPI spec and generate tool manifest.

        Args:
            openapi_spec: Parsed OpenAPI specification
            source_url: Source URL of the spec

        Returns:
            Tool manifest ready for creation
        """
        # Extract basic info from OpenAPI spec
        info = openapi_spec.get("info", {})
        name = info.get("title", "unknown-api").lower().replace(" ", "-")
        version = info.get("version", "1.0.0")
        description = info.get("description", "No description provided")

        # Use LLM for sophisticated analysis if available
        if self.llm:
            analysis = await self._llm_analyze_openapi(openapi_spec)
            if analysis:
                return ToolManifestCreate(
                    name=analysis.get("name", name),
                    version=analysis.get("version", version),
                    description=analysis.get("description", description),
                    source_type=ToolSourceType.OPENAPI_URL,
                    source_location=source_url,
                    openapi_spec=openapi_spec,
                    capabilities=analysis.get("capabilities", []),
                    parameters_schema=analysis.get("parameters_schema", {}),
                )

        # Fallback: basic extraction without LLM
        capabilities = self._extract_capabilities_basic(openapi_spec)

        return ToolManifestCreate(
            name=name,
            version=version,
            description=description,
            source_type=ToolSourceType.OPENAPI_URL,
            source_location=source_url,
            openapi_spec=openapi_spec,
            capabilities=capabilities,
            parameters_schema={},
        )

    async def _llm_analyze_openapi(
        self, openapi_spec: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Use LLM to analyze OpenAPI spec and extract capabilities."""
        assert self.llm is not None

        # Prepare a simplified version of the spec for the LLM
        simplified_spec = {
            "info": openapi_spec.get("info", {}),
            "servers": openapi_spec.get("servers", []),
            "paths": {},
        }

        # Include only essential path information
        for path, path_item in openapi_spec.get("paths", {}).items():
            simplified_spec["paths"][path] = {}
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    operation = path_item[method]
                    simplified_spec["paths"][path][method] = {
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "parameters": operation.get("parameters", []),
                        "requestBody": operation.get("requestBody", {}),
                        "responses": operation.get("responses", {}),
                    }

        spec_json = json.dumps(simplified_spec, indent=2)

        # Truncate if too long (keep it under 4000 chars)
        if len(spec_json) > 4000:
            spec_json = spec_json[:4000] + "\n... (truncated)"

        messages = [
            LLMMessage(
                role=MessageRole.USER,
                content=f"""Analyze this OpenAPI specification and extract tool capabilities:

{spec_json}

Return a JSON object with the structure specified in your instructions.""",
            )
        ]

        try:
            logger.debug("Calling LLM for OpenAPI analysis")

            response = await self.llm.generate(
                messages=messages,
                system_prompt=self.openapi_analysis_prompt,
            )

            # Try to parse JSON from response
            content = response.content.strip()

            # Extract JSON if wrapped in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            analysis = json.loads(content)

            logger.debug("OpenAPI analysis complete", has_capabilities=bool(analysis.get("capabilities")))

            return analysis

        except Exception as e:
            logger.warning("LLM analysis failed, using basic extraction", error=str(e))
            return None

    def _extract_capabilities_basic(self, openapi_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Basic capability extraction without LLM.

        Extracts operation summaries from paths.
        """
        capabilities = []

        for path, path_item in openapi_spec.get("paths", {}).items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    operation = path_item[method]
                    capability = {
                        "name": operation.get("operationId", f"{method}_{path.replace('/', '_')}"),
                        "description": operation.get("summary", operation.get("description", "No description")),
                        "endpoint": path,
                        "method": method.upper(),
                    }
                    capabilities.append(capability)

        return capabilities

    # =========================================================================
    # Tool Discovery (Future: API Search)
    # =========================================================================

    async def discover_tool(self, request: ToolDiscoveryRequest) -> UUID:
        """
        Discover a tool based on capability description.

        Currently returns a discovery request ID. In the future, this will:
        1. Search public API directories (RapidAPI, APIs.guru, etc.)
        2. Analyze search results
        3. Propose the best matching API
        4. Create a tool manifest for approval

        Args:
            request: Discovery request with capability description

        Returns:
            UUID of the discovery request (not the tool manifest)
        """
        logger.info(
            "Tool discovery requested",
            capability=request.capability_description,
        )

        # Create discovery request in queue
        discovery_request = await self.tool_repo.create_discovery_request(request)

        # For MVP, log the request and return
        # Future implementation will include:
        # - API search integration
        # - Result ranking
        # - Automatic OpenAPI ingestion

        logger.info(
            "Discovery request queued",
            request_id=str(discovery_request.id),
            capability=request.capability_description,
        )

        return discovery_request.id

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        await self.http_client.aclose()
        logger.info("Tool Discovery Agent closed")
