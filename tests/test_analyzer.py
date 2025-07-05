import unittest
import os
from core.analyzer import Analyzer
from config import settings

class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        with open('data/test_patterns.txt', 'w', encoding='utf-8') as f:
            f.write("password\nsecret\n")
        settings.SETTINGS['patterns_file'] = 'data/test_patterns.txt'
        self.analyzer = Analyzer('data/test_patterns.txt')

    def test_classify_high_risk(self):
        self.assertEqual(self.analyzer.classify_file("password.txt"), 'HIGH')

    def test_classify_medium_risk(self):
        self.assertEqual(self.analyzer.classify_file("config.env"), 'MEDIUM')

    def test_classify_low_risk(self):
        self.assertEqual(self.analyzer.classify_file("image.png"), 'LOW')

    def test_analyze_content(self):
        with open('data/test_file.txt', 'w', encoding='utf-8') as f:
            f.write("secret_key=123")
        self.assertEqual(self.analyzer.analyze_content('data/test_file.txt'), 'HIGH')

    def test_cache(self):
        self.analyzer.classify_file("password.txt")
        self.assertIn("password.txt", self.analyzer.cache)
        self.assertEqual(self.analyzer.cache["password.txt"], 'HIGH')

    def tearDown(self):
        for file in ['data/test_patterns.txt', 'data/test_file.txt']:
            if os.path.exists(file):
                os.remove(file)

if __name__ == '__main__':
    unittest.main()