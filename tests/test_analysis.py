"""Tests for analysis module"""

import unittest
import pandas as pd
from coffee_futures.analysis import analyze_futures


class TestAnalysis(unittest.TestCase):
    """Test cases for analysis functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.sample_data = pd.DataFrame({
            'price': [100, 102, 101, 103, 105],
            'volume': [1000, 1100, 950, 1200, 1300]
        })
    
    def test_analyze_futures_returns_dict(self):
        """Test that analyze_futures returns a dictionary"""
        result = analyze_futures(self.sample_data)
        self.assertIsInstance(result, dict)
        self.assertIn('mean', result)
        self.assertIn('std', result)
        self.assertIn('correlation', result)


if __name__ == '__main__':
    unittest.main()
