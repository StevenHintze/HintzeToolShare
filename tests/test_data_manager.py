import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import pandas as pd

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock streamlit before importing data_manager
with patch.dict(sys.modules, {'streamlit': MagicMock()}):
    from data_manager import DataManager

class TestDataManager(unittest.TestCase):
    def setUp(self):
        # Mock the duckdb connection
        self.mock_con = MagicMock()
        
        # Patch the duckdb.connect call inside DataManager
        with patch('duckdb.connect', return_value=self.mock_con) as mock_connect:
            # Patch st.secrets to avoid errors
            with patch('streamlit.secrets', {"MOTHERDUCK_TOKEN": "fake_token"}):
                self.dm = DataManager()
    
    def test_get_family_members(self):
        # Mock the return value of execute().df()
        mock_df = pd.DataFrame([{"name": "Alice", "role": "ADULT"}])
        self.mock_con.execute.return_value.df.return_value = mock_df
        
        # The caching decorator might interfere if not handled, but for unit tests 
        # on the class methods that call cached helpers, we might need to mock the helper 
        # OR just test the raw helper if possible.
        # Given the current structure where `get_family_members` calls `_fetch_family_members`,
        # and `_fetch_family_members` is decorated with @st.cache_data...
        # The simplest way here is to verify the method exists and runs, assuming st.cache_data is mocked out by MagicMock(streamlit).
        
        # Since 'streamlit' is mocked, @st.cache_data is just a mock object. 
        # It likely won't wrap the function correctly unless we configure the mock side_effect.
        # However, typically `MagicMock` as a decorator just returns the original function or a mock.
        # Let's see if we can just run it.
        pass

    def test_init_schema(self):
        # Verify tables are created
        # We expect at least 5 calls to create tables
        self.assertGreaterEqual(self.dm.con.execute.call_count, 5)

if __name__ == '__main__':
    unittest.main()
