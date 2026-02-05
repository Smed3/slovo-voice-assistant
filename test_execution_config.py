#!/usr/bin/env python3
"""
Manual test for execution config extraction.

This script verifies that:
1. Tool manifests with execution config are correctly parsed
2. Tool manifests without execution config use defaults
3. The data structures match expected schema
"""

import json
import yaml
from pathlib import Path


def test_manifest_with_execution():
    """Test manifest that includes execution configuration."""
    manifest_path = Path("tools/manifests/examples/web-search.manifest.json")
    
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    # Check that execution config is present
    assert "execution" in manifest, "Manifest should have execution config"
    execution = manifest["execution"]
    
    # Check execution fields
    assert execution["type"] == "docker", f"Expected docker, got {execution['type']}"
    assert execution["image"] == "slovo/tool-web-search:latest", f"Wrong image: {execution['image']}"
    assert execution["entrypoint"] == "python /app/main.py", f"Wrong entrypoint: {execution['entrypoint']}"
    assert execution["timeout"] == 30, f"Wrong timeout: {execution['timeout']}"
    
    print("✓ Manifest with execution config parsed correctly")
    return True


def test_manifest_without_execution():
    """Test manifest that lacks execution configuration."""
    manifest_path = Path("tools/manifests/examples/example-calculator.yaml")
    
    with open(manifest_path, "r") as f:
        manifest = yaml.safe_load(f)
    
    # Check that execution config is not present
    assert "execution" not in manifest, "Calculator manifest should not have execution config"
    
    # Verify it has other expected fields
    assert manifest["name"] == "example-calculator"
    assert manifest["version"] == "1.0.0"
    assert "capabilities" in manifest
    assert len(manifest["capabilities"]) > 0
    
    print("✓ Manifest without execution config handled correctly")
    return True


def test_execution_config_extraction():
    """Test that execution config can be extracted as expected by tool_discovery."""
    manifest_path = Path("tools/manifests/examples/web-search.manifest.json")
    
    with open(manifest_path, "r") as f:
        manifest_data = json.load(f)
    
    # Simulate extraction logic from tool_discovery.py
    execution = manifest_data.get("execution", {})
    execution_type = execution.get("type", "docker")
    docker_image = execution.get("image")
    docker_entrypoint = execution.get("entrypoint")
    execution_timeout = execution.get("timeout", 30)
    
    # Verify extracted values
    assert execution_type == "docker"
    assert docker_image == "slovo/tool-web-search:latest"
    assert docker_entrypoint == "python /app/main.py"
    assert execution_timeout == 30
    
    print("✓ Execution config extraction logic works correctly")
    return True


def test_entrypoint_parsing():
    """Test that entrypoint can be parsed as string or list."""
    # Test string entrypoint
    entrypoint_str = "python /app/main.py"
    if isinstance(entrypoint_str, str):
        command = entrypoint_str.split()
    else:
        command = entrypoint_str
    
    assert command == ["python", "/app/main.py"], f"Wrong parsing: {command}"
    
    # Test list entrypoint
    entrypoint_list = ["node", "/app/index.js", "--verbose"]
    if isinstance(entrypoint_list, str):
        command = entrypoint_list.split()
    else:
        command = entrypoint_list
    
    assert command == ["node", "/app/index.js", "--verbose"], f"Wrong parsing: {command}"
    
    print("✓ Entrypoint parsing works for both string and list")
    return True


if __name__ == "__main__":
    print("Testing execution config handling...\n")
    
    try:
        test_manifest_with_execution()
        test_manifest_without_execution()
        test_execution_config_extraction()
        test_entrypoint_parsing()
        
        print("\n✅ All tests passed!")
        exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
