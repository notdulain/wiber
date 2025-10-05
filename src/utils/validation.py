"""
Project structure validation utilities.

This module provides functions to validate that the project structure
is correct and all required components are in place.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

import structlog

logger = structlog.get_logger(__name__)


def validate_project_structure() -> Tuple[bool, List[str]]:
    """
    Validate that the project has the correct structure.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Define required directories
    required_dirs = [
        "src",
        "src/cluster",
        "src/api", 
        "src/replication",
        "src/timing",
        "src/config",
        "src/utils",
        "tests",
        "config",
        "scripts",
        "guides",
        "data",
    ]
    
    # Define required files
    required_files = [
        "requirements.txt",
        "README.md",
        "config/cluster.yaml",
        "scripts/run_cluster.py",
    ]
    
    # Check directories
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            errors.append(f"Missing required directory: {dir_path}")
        elif not os.path.isdir(dir_path):
            errors.append(f"Path exists but is not a directory: {dir_path}")
    
    # Check files
    for file_path in required_files:
        if not os.path.exists(file_path):
            errors.append(f"Missing required file: {file_path}")
        elif not os.path.isfile(file_path):
            errors.append(f"Path exists but is not a file: {file_path}")
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info("Project structure validation passed")
    else:
        logger.error("Project structure validation failed", errors=errors)
    
    return is_valid, errors


def validate_python_imports() -> Tuple[bool, List[str]]:
    """
    Validate that all Python modules can be imported without errors.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Add src to Python path for imports
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    # Define modules to test import
    modules_to_test = [
        "utils.logging_config",
        "config.cluster",
        "cluster.node",
        "cluster.raft", 
        "cluster.rpc",
        "api.wire",
        "replication.log",
        "replication.dedup",
        "timing.sync",
        "timing.lamport",
    ]
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            logger.debug("Successfully imported module", module=module_name)
        except ImportError as e:
            error_msg = f"Failed to import {module_name}: {e}"
            errors.append(error_msg)
            logger.error("Import validation failed", module=module_name, error=str(e))
        except Exception as e:
            error_msg = f"Unexpected error importing {module_name}: {e}"
            errors.append(error_msg)
            logger.error("Unexpected import error", module=module_name, error=str(e))
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info("Python imports validation passed")
    else:
        logger.error("Python imports validation failed", errors=errors)
    
    return is_valid, errors


def validate_dependencies() -> Tuple[bool, List[str]]:
    """
    Validate that all required dependencies are available.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Define required packages
    required_packages = [
        "structlog",
        "yaml", 
        "asyncio",
        "pytest",
        "colorama",
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            logger.debug("Successfully imported dependency", package=package)
        except ImportError:
            error_msg = f"Missing required dependency: {package}"
            errors.append(error_msg)
            logger.error("Dependency validation failed", package=package)
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info("Dependencies validation passed")
    else:
        logger.error("Dependencies validation failed", errors=errors)
    
    return is_valid, errors


def run_all_validations() -> bool:
    """
    Run all validation checks.
    
    Returns:
        True if all validations pass, False otherwise
    """
    logger.info("Starting project validation")
    
    # Run all validations
    structure_valid, structure_errors = validate_project_structure()
    imports_valid, imports_errors = validate_python_imports()
    deps_valid, deps_errors = validate_dependencies()
    
    # Combine all errors
    all_errors = structure_errors + imports_errors + deps_errors
    
    # Log results
    if all_errors:
        logger.error("Project validation failed", total_errors=len(all_errors))
        for error in all_errors:
            logger.error("Validation error", error=error)
        return False
    else:
        logger.info("All project validations passed!")
        return True


if __name__ == "__main__":
    # Run validation when script is executed directly
    success = run_all_validations()
    sys.exit(0 if success else 1)
