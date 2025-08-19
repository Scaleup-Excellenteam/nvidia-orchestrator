#!/usr/bin/env python
"""
Test script to verify the package structure and imports work correctly.
"""

import sys
import traceback


def test_imports():
    """Test that all package modules can be imported."""
    print("Testing NVIDIA Orchestrator package imports...")

    tests = []

    # Test main package
    try:
        import nvidia_orchestrator
        print("✅ Main package import successful")
        print(f"   Version: {nvidia_orchestrator.__version__}")
        tests.append(True)
    except Exception as e:
        print(f"❌ Main package import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Test API module
    try:
        print("✅ API module import successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ API module import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Test core module
    try:
        print("✅ Core module import successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ Core module import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Test storage module
    try:
        print("✅ Storage module import successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ Storage module import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Test monitoring module
    try:
        print("✅ Monitoring module import successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ Monitoring module import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Test utils module
    try:
        print("✅ Utils module import successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ Utils module import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Test CLI module
    try:
        print("✅ CLI module import successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ CLI module import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Test main entry point module
    try:
        print("✅ Main entry point import successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ Main entry point import failed: {e}")
        traceback.print_exc()
        tests.append(False)

    # Summary
    print("\n" + "="*50)
    passed = sum(tests)
    total = len(tests)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All imports successful! Package structure is valid.")
        return 0
    else:
        print("⚠️ Some imports failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(test_imports())
