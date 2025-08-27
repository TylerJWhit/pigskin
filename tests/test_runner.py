"""Test runner and test suite management."""

import unittest
import sys
import os
from io import StringIO

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)


class TestRunner:
    """Custom test runner with additional features."""
    
    def __init__(self, verbosity=2):
        self.verbosity = verbosity
        self.test_results = {}
        
    def run_all_tests(self):
        """Run all tests in the test suite."""
        print("=" * 70)
        print("AUCTION DRAFT TOOL - COMPREHENSIVE TEST SUITE")
        print("=" * 70)
        
        # Test modules to run
        test_modules = [
            'test_strategies',
            'test_classes', 
            'test_services',
            'test_data_api',
            'test_integration'
        ]
        
        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0
        
        for module_name in test_modules:
            print(f"\n{'-' * 50}")
            print(f"Running {module_name.replace('_', ' ').title()} Tests")
            print(f"{'-' * 50}")
            
            try:
                # Load test module
                loader = unittest.TestLoader()
                suite = loader.loadTestsFromName(module_name)
                
                # Run tests with custom result capture
                stream = StringIO()
                runner = unittest.TextTestRunner(
                    stream=stream, 
                    verbosity=self.verbosity
                )
                result = runner.run(suite)
                
                # Capture results
                self.test_results[module_name] = {
                    'tests_run': result.testsRun,
                    'failures': len(result.failures),
                    'errors': len(result.errors),
                    'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
                    'success': result.wasSuccessful()
                }
                
                # Update totals
                total_tests += result.testsRun
                total_failures += len(result.failures)
                total_errors += len(result.errors)
                total_skipped += len(result.skipped) if hasattr(result, 'skipped') else 0
                
                # Print results for this module
                print(f"Tests run: {result.testsRun}")
                print(f"Failures: {len(result.failures)}")
                print(f"Errors: {len(result.errors)}")
                if hasattr(result, 'skipped'):
                    print(f"Skipped: {len(result.skipped)}")
                
                # Print detailed failure info
                if result.failures:
                    print("\nFAILURES:")
                    for test, traceback in result.failures:
                        # Extract just the test name and key error info
                        test_name = str(test).split()[0] if ' ' in str(test) else str(test)
                        # Get the assertion error from traceback
                        lines = traceback.split('\n')
                        error_line = "Unknown failure"
                        for line in reversed(lines):
                            if line.strip() and ('AssertionError' in line or 'assert' in line.lower()):
                                error_line = line.strip()
                                break
                        print(f"  - {test_name}: {error_line}")
                        
                if result.errors:
                    print("\nERRORS:")
                    for test, traceback in result.errors:
                        test_name = str(test).split()[0] if ' ' in str(test) else str(test)
                        # Get the exception from traceback
                        lines = traceback.split('\n')
                        error_line = "Unknown error"
                        for line in reversed(lines):
                            if line.strip() and any(x in line for x in ['Error:', 'Exception:', 'ImportError']):
                                error_line = line.strip()
                                break
                        print(f"  - {test_name}: {error_line}")
                        if traceback:
                            lines = traceback.split('\n')
                            # Get the last non-empty line that contains useful info
                            for line in reversed(lines):
                                if line.strip() and not line.startswith(' '):
                                    error_msg = line.strip()
                                    break
                        print(f"  - {test}: {error_msg}")
                
            except ImportError as e:
                print(f"Could not import {module_name}: {e}")
                self.test_results[module_name] = {
                    'tests_run': 0,
                    'failures': 0,
                    'errors': 1,
                    'skipped': 0,
                    'success': False,
                    'import_error': str(e)
                }
                total_errors += 1
                
        # Print final summary
        self.print_final_summary(total_tests, total_failures, total_errors, total_skipped)
        
        return total_failures == 0 and total_errors == 0
        
    def print_final_summary(self, total_tests, total_failures, total_errors, total_skipped):
        """Print final test summary."""
        print("\n" + "=" * 70)
        print("FINAL TEST SUMMARY")
        print("=" * 70)
        
        print(f"Total tests run: {total_tests}")
        print(f"Total failures: {total_failures}")
        print(f"Total errors: {total_errors}")
        print(f"Total skipped: {total_skipped}")
        
        success_rate = ((total_tests - total_failures - total_errors) / max(total_tests, 1)) * 100
        print(f"Success rate: {success_rate:.1f}%")
        
        print("\nPer-module results:")
        for module, results in self.test_results.items():
            status = "✓ PASS" if results['success'] else "✗ FAIL"
            if 'import_error' in results:
                status = "IMPORT ERROR"
            print(f"  {module:20} {status:12} ({results['tests_run']} tests)")
            
        if total_failures == 0 and total_errors == 0:
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print("\nSOME TESTS FAILED - See details above")
            
    def run_specific_test(self, test_name):
        """Run a specific test or test class."""
        print(f"Running specific test: {test_name}")
        
        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(test_name)
            
            runner = unittest.TextTestRunner(verbosity=self.verbosity)
            result = runner.run(suite)
            
            return result.wasSuccessful()
            
        except Exception as e:
            print(f"Error running test {test_name}: {e}")
            return False
            
    def run_quick_tests(self):
        """Run only quick, essential tests."""
        print("Running quick test suite...")
        
        quick_tests = [
            'test_strategies.TestStrategies.test_strategy_creation',
            'test_classes.TestPlayer.test_player_creation',
            'test_classes.TestTeam.test_team_creation',
            'test_data_api.TestConfigManager.test_load_config_success'
        ]
        
        all_passed = True
        for test in quick_tests:
            print(f"  Running {test}...")
            if not self.run_specific_test(test):
                all_passed = False
                
        return all_passed


def run_tests():
    """Main test runner function."""
    runner = TestRunner()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--quick':
            return runner.run_quick_tests()
        elif sys.argv[1] == '--specific':
            if len(sys.argv) > 2:
                return runner.run_specific_test(sys.argv[2])
            else:
                print("Please specify a test name after --specific")
                return False
        else:
            print("Usage: python test_runner.py [--quick] [--specific test_name]")
            return False
    else:
        return runner.run_all_tests()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
