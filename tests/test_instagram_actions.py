import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies before importing instagram_actions
sys.modules['selenium'] = MagicMock()
sys.modules['selenium.webdriver.common.by'] = MagicMock()
sys.modules['selenium.webdriver.common.action_chains'] = MagicMock()
sys.modules['bs4'] = MagicMock()

# Now import the module under test
import instagram_actions

class TestInstagramActions(unittest.TestCase):

    @patch('instagram_actions.subprocess.run')
    def test_get_stream_metadata_security(self, mock_run):
        """
        Verify that get_stream_metadata adds '--' before the URL to prevent flag injection.
        """
        # Mock successful output
        mock_run.return_value.stdout = '{"format": {"duration": "10.0"}, "streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}'

        url = "-malicious_url"
        instagram_actions.get_stream_metadata(url)

        # Get the command list passed to subprocess.run
        call_args = mock_run.call_args[0][0]

        # Verify that '--' is present and precedes the URL
        self.assertIn("--", call_args, "Missing '--' delimiter in ffprobe command")
        dash_dash_index = call_args.index("--")
        url_index = call_args.index(url)
        self.assertLess(dash_dash_index, url_index, "'--' must appear before the URL")

    @patch('instagram_actions.subprocess.run')
    def test_get_media_duration_security(self, mock_run):
        """
        Verify that get_media_duration adds '--' before the file path to prevent flag injection.
        """
        # Mock successful output
        mock_run.return_value.stdout = "10.0"

        file_path = "-malicious_file"
        instagram_actions.get_media_duration(file_path)

        # Get the command list passed to subprocess.run
        call_args = mock_run.call_args[0][0]

        # Verify that '--' is present and precedes the file path
        self.assertIn("--", call_args, "Missing '--' delimiter in ffprobe command")
        dash_dash_index = call_args.index("--")
        file_path_index = call_args.index(file_path)
        self.assertLess(dash_dash_index, file_path_index, "'--' must appear before the file path")

if __name__ == '__main__':
    unittest.main()
