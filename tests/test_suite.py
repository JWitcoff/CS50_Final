import sys
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Get the absolute path to the project root
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Use absolute imports instead of relative
from tests.test_scenarios import TestScenarios, TestCase, TestCategory
from tests.conversation_analyzer import ConversationAnalyzer
from tests.test_verifier import TestVerifier
from app import process_message
import logging

class TestSuite:
    def __init__(self):
        self.scenarios = TestScenarios()
        self.verifier = TestVerifier()
        self.analyzer = ConversationAnalyzer()
        self.results = []
        self.test_phone = "+1234567890"  # Test phone number
        
    def run_all_tests(self):
        """Run all test scenarios"""
        for test_case in self.scenarios.test_cases:
            result = self.run_single_test(test_case)
            self.results.append(result)
        return self.results
        
    def run_single_test(self, test_case: TestCase) -> Dict[str, Any]:
        """Run a single test case and return results"""
        logging.info(f"Running test: {test_case.id} - {test_case.description}")
        
        test_result = {
            'test_id': test_case.id,
            'description': test_case.description,
            'category': test_case.category.value,
            'timestamp': datetime.now().isoformat(),
            'messages': [],
            'success': True,
            'errors': []
        }
        
        try:
            # Process each message in the test case
            for i, message in enumerate(test_case.messages):
                # Send message through system
                response = process_message(self.test_phone, message)
                
                # Record message and response
                test_result['messages'].append({
                    'step': i + 1,
                    'input': message,
                    'response': response,
                    'expected_state': test_case.expected_states[i],
                })
                
                # Verify response
                verification = self.verifier.verify_step(
                    message, 
                    response, 
                    test_case.expected_states[i]
                )
                
                if not verification['success']:
                    test_result['success'] = False
                    test_result['errors'].append(verification['error'])
            
            # Analyze conversation quality
            conversation_analysis = self.analyzer.analyze_conversation(test_result)
            test_result['analysis'] = conversation_analysis
            
            # Final verification
            final_verification = self.verifier.verify_final_state(
                test_result,
                test_case.expected_cart
            )
            
            if not final_verification['success']:
                test_result['success'] = False
                test_result['errors'].append(final_verification['error'])
                
        except Exception as e:
            test_result['success'] = False
            test_result['errors'].append(str(e))
            logging.error(f"Test {test_case.id} failed: {str(e)}", exc_info=True)
        
        logging.info(f"Test {test_case.id} completed. Success: {test_result['success']}")
        return test_result 