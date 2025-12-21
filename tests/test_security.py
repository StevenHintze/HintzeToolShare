import unittest
import sys
import os

# Add parent directory to path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools_registry import check_safety

class TestSafetyLogic(unittest.TestCase):
    def test_admin_access(self):
        self.assertTrue(check_safety("ADMIN", "Open"))
        self.assertTrue(check_safety("ADMIN", "Adult Only"))
        self.assertTrue(check_safety("ADMIN", "Supervised"))

    def test_adult_access(self):
        self.assertTrue(check_safety("ADULT", "Open"))
        self.assertTrue(check_safety("ADULT", "Adult Only"))
        self.assertTrue(check_safety("ADULT", "Supervised"))

    def test_child_access(self):
        self.assertTrue(check_safety("CHILD", "Open"))
        self.assertTrue(check_safety("CHILD", "Supervised"))
        self.assertFalse(check_safety("CHILD", "Adult Only"))
        self.assertFalse(check_safety("CHILD", "Unknown Rating"))

if __name__ == '__main__':
    unittest.main()
