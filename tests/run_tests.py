from test_suite import TestSuite
import json
import logging

def main():
    # Initialize logging
    logging.basicConfig(
        level=logging.INFO,
        filename='test_results.log',
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    suite = TestSuite()
    results = suite.run_all_tests()
    
    # Save results
    with open('test_results.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main() 