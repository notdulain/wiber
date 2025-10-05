"""
Tests for project setup and basic functionality.

This module tests that the project is properly configured and basic
components are working correctly.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from utils.validation import validate_project_structure, validate_dependencies
from utils.logging_config import setup_logging, get_logger


class TestProjectSetup:
    """Test project setup and configuration."""
    
    def test_project_structure_validation(self):
        """Test that project structure is correct."""
        is_valid, errors = validate_project_structure()
        
        # Should pass basic structure validation
        assert is_valid, f"Project structure validation failed: {errors}"
    
    def test_dependencies_validation(self):
        """Test that required dependencies are available."""
        is_valid, errors = validate_dependencies()
        
        # Should pass dependency validation
        assert is_valid, f"Dependencies validation failed: {errors}"
    
    def test_logging_setup(self):
        """Test that logging configuration works."""
        # Should be able to set up logging without errors
        logger = setup_logging(level="DEBUG", node_id="test-node")
        
        # Should be able to log messages
        logger.info("Test log message")
        logger.debug("Debug message", extra_data={"test": True})
        
        # Should be able to get component logger
        component_logger = get_logger("test-component", node_id="test-node")
        component_logger.warning("Component warning")
        
        # If we get here without exceptions, logging is working
        assert True
    
    def test_import_structure(self):
        """Test that we can import from our project structure."""
        # Test that we can import our utilities
        from utils.validation import run_all_validations
        from utils.logging_config import setup_logging
        
        # These should not raise ImportError
        assert run_all_validations is not None
        assert setup_logging is not None


class TestBasicFunctionality:
    """Test basic functionality of core components."""
    
    def test_logging_levels(self):
        """Test that different logging levels work."""
        logger = setup_logging(level="DEBUG")
        
        # Test different log levels
        logger.debug("Debug message")
        logger.info("Info message") 
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Should not raise exceptions
        assert True
    
    def test_structured_logging(self):
        """Test structured logging with context."""
        logger = setup_logging(node_id="test-node", component="test-component")
        
        # Test structured logging with bindings
        logger = logger.bind(user_id="user123", action="test_action")
        logger.info("User performed action", result="success")
        
        # Should not raise exceptions
        assert True
