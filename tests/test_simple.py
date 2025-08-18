"""
Simple test file to verify basic functionality works
"""
import sys
import pathlib

# Add the project root to Python path
project_root = pathlib.Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_import_container_manager():
    """Test that we can import ContainerManager"""
    try:
        from container_manager import ContainerManager
        print("✅ Successfully imported ContainerManager")
        return True
    except ImportError as e:
        print(f"❌ Failed to import ContainerManager: {e}")
        return False

def test_create_container_manager():
    """Test that we can create a ContainerManager instance"""
    try:
        from container_manager import ContainerManager
        manager = ContainerManager()
        print("✅ Successfully created ContainerManager instance")
        return True
    except Exception as e:
        print(f"❌ Failed to create ContainerManager: {e}")
        return False

def test_basic_methods():
    """Test basic methods exist"""
    try:
        from container_manager import ContainerManager
        manager = ContainerManager()
        
        # Check that basic methods exist
        assert hasattr(manager, 'register_desired_state')
        assert hasattr(manager, 'ensure_singleton_for_image')
        assert hasattr(manager, 'list_managed_containers')
        
        print("✅ All basic methods exist")
        return True
    except Exception as e:
        print(f"❌ Failed to test basic methods: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Running simple tests...")
    
    tests = [
        test_import_container_manager,
        test_create_container_manager,
        test_basic_methods
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Ready for next step.")
    else:
        print("⚠️  Some tests failed. Need to fix issues first.")
