#!/usr/bin/env python3
"""
Test script to verify project setup is working correctly.

This script runs basic validation and tests to ensure the project
is properly configured and ready for development.
"""

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from utils.validation import run_all_validations
from utils.logging_config import setup_logging


def main():
    """Run setup tests and validation."""
    print("Testing Wiber Distributed Messaging System Setup")
    print("=" * 60)
    
    # Set up logging for the test
    logger = setup_logging(level="INFO", node_id="setup-test")
    
    # Run validation
    logger.info("Running project validation...")
    success = run_all_validations()
    
    if success:
        print("\n[SUCCESS] All validations passed!")
        print("Project setup is correct and ready for development")
        
        # Test logging functionality
        logger.info("Testing logging functionality...")
        logger.debug("This is a debug message")
        logger.info("This is an info message")
        logger.warning("This is a warning message")
        logger.error("This is an error message")
        
        print("\n[INFO] Logging test completed successfully")
        print("\nNext steps:")
        print("   1. Run: python -m pytest tests/test_setup.py -v")
        print("   2. Start implementing Task 0.2: Configuration System")
        
        return True
    else:
        print("\n[ERROR] Validation failed!")
        print("Please fix the errors above before continuing")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
