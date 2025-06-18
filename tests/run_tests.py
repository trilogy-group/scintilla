#!/usr/bin/env python3
"""
Scintilla Test Runner

Comprehensive test suite for the Scintilla MCP system.
Runs all available tests and provides detailed reporting.
"""

import asyncio
import subprocess
import sys
import os
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestRunner:
    def __init__(self):
        self.tests_dir = Path(__file__).parent
        self.results = {}
        
    async def run_python_test(self, test_file: str, description: str) -> bool:
        """Run a Python test file and capture results"""
        print(f"\n🧪 Running {description}")
        print("=" * 60)
        
        try:
            # Run the test file
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(self.tests_dir / test_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.tests_dir.parent
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print(stdout.decode('utf-8'))
                print(f"✅ {description} - PASSED")
                return True
            else:
                print(f"❌ {description} - FAILED")
                print("STDOUT:", stdout.decode('utf-8'))
                print("STDERR:", stderr.decode('utf-8'))
                return False
                
        except Exception as e:
            print(f"❌ {description} - ERROR: {e}")
            return False
    
    def run_shell_test(self, test_file: str, description: str) -> bool:
        """Run a shell script test"""
        print(f"\n🧪 Running {description}")
        print("=" * 60)
        
        try:
            result = subprocess.run(
                ['bash', str(self.tests_dir / test_file)],
                capture_output=True,
                text=True,
                cwd=self.tests_dir.parent
            )
            
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
                
            if result.returncode == 0:
                print(f"✅ {description} - PASSED")
                return True
            else:
                print(f"❌ {description} - FAILED")
                return False
                
        except Exception as e:
            print(f"❌ {description} - ERROR: {e}")
            return False
    
    async def run_all_tests(self):
        """Run the complete test suite"""
        print("🔍🤖 SCINTILLA COMPREHENSIVE TEST SUITE")
        print("=" * 60)
        print("Running all tests to verify system functionality...")
        print("=" * 60)
        
        # Test 1: Search-focused system (our main test)
        self.results['search_system'] = await self.run_python_test(
            'test_search_focused.py',
            'Search-Focused System (Core Functionality)'
        )
        
        # Test 2: General endpoint testing
        self.results['endpoints'] = await self.run_python_test(
            'test_endpoints.py', 
            'API Endpoints (Health, Streaming, Non-streaming)'
        )
        
        # Test 3: Real server integration
        self.results['real_servers'] = await self.run_python_test(
            'test_real_hive_servers.py',
            'Real Hive Server Integration'
        )
        
        # Test 4: Credential system
        self.results['credentials'] = await self.run_python_test(
            'test_credential_system.py',
            'Credential Management System'
        )
        
        # Test 5: Manual curl commands (optional)
        print(f"\n📋 Manual curl tests available:")
        print(f"   - tests/test_curl_commands.sh (General API testing)")
        print(f"   - tests/test_jira_curl.sh (Jira-specific testing)")
        print(f"   Run these manually when server is running.")
        
        # Summary
        await self.print_summary()
    
    async def print_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 60)
        print("🎯 COMPREHENSIVE TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(self.results.values())
        
        for test_name, passed in self.results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name.ljust(20)}: {status}")
        
        print(f"\n📊 Overall Results: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("\n🎉 ALL TESTS PASSED! Scintilla system is working perfectly!")
            print("\n🚀 System Status: PRODUCTION READY")
            print("\n✨ Key Features Verified:")
            print("   🔍 Search-focused knowledge base queries")
            print("   🚫 Action tool filtering (read-only safety)")
            print("   🤖 Intelligent query encapsulation")
            print("   🔧 MCP server integration")
            print("   🔐 Secure credential management")
            print("   📡 Streaming and non-streaming APIs")
            print("   💬 Multiple query modes")
            
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) failed - system needs attention")
            print("\n🔧 Failed Tests:")
            for test_name, passed in self.results.items():
                if not passed:
                    print(f"   ❌ {test_name}")
        
        print("\n💡 Next Steps:")
        if passed_tests == total_tests:
            print("   🌐 Deploy to production environment")
            print("   📊 Set up monitoring and logging")
            print("   📚 Create user documentation")
        else:
            print("   🐛 Fix failing tests")
            print("   🔍 Check server configuration")
            print("   📋 Review error logs")
        
        print("\n📁 Test Files Location: tests/")
        print("📖 Run individual tests: python tests/<test_file>.py")
        print("🌐 Manual API tests: bash tests/test_curl_commands.sh")

async def main():
    """Main test runner entry point"""
    runner = TestRunner()
    await runner.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 