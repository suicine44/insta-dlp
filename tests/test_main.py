import os
import sys
import pytest
from unittest.mock import MagicMock, patch, mock_open
import logging

# Mock missing dependencies before importing main
mock_requests = MagicMock()
sys.modules['requests'] = mock_requests
mock_selenium = MagicMock()
sys.modules['selenium'] = mock_selenium
sys.modules['selenium.common'] = MagicMock()
sys.modules['selenium.common.exceptions'] = MagicMock()
mock_uc = MagicMock()
sys.modules['undetected_chromedriver'] = mock_uc
sys.modules['driver_setup'] = MagicMock()
sys.modules['instagram_actions'] = MagicMock()

# Add the root directory to sys.path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main

@pytest.fixture
def mock_logger():
    with patch('main.logging') as mock_log:
        yield mock_log

@pytest.fixture
def logger_instance():
    # Patch logging.basicConfig to avoid side effects during test initialization
    with patch('main.logging.basicConfig'):
        return main.Logger(debug_mode=True, log_file="test.log")

def test_logger_init():
    with patch('main.logging.basicConfig') as mock_basic_config:
        logger = main.Logger(debug_mode=True, log_file="custom.log")
        assert logger.debug_mode is True
        assert logger.log_file == "custom.log"
        mock_basic_config.assert_called_once_with(
            filename="custom.log",
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            filemode='a'
        )

def test_logger_info(logger_instance, mock_logger):
    with patch('builtins.print') as mock_print:
        logger_instance.info("Test Info")
        mock_print.assert_called_once()
        assert "Test Info" in mock_print.call_args[0][0]
        mock_logger.info.assert_called_once_with("Test Info")

def test_logger_success(logger_instance, mock_logger):
    with patch('builtins.print') as mock_print:
        logger_instance.success("Test Success")
        mock_print.assert_called_once()
        assert "Test Success" in mock_print.call_args[0][0]
        mock_logger.info.assert_called_once_with("SUCCESS: Test Success")

def test_logger_warning(logger_instance, mock_logger):
    with patch('builtins.print') as mock_print:
        logger_instance.warning("Test Warning")
        mock_print.assert_called_once()
        assert "Test Warning" in mock_print.call_args[0][0]
        mock_logger.warning.assert_called_once_with("Test Warning")

def test_logger_error(logger_instance, mock_logger):
    with patch('builtins.print') as mock_print:
        logger_instance.error("Test Error")
        mock_print.assert_called_once()
        assert "Test Error" in mock_print.call_args[0][0]
        mock_logger.error.assert_called_once_with("Test Error")

def test_logger_debug(logger_instance, mock_logger):
    # Test with debug_mode=True
    with patch('builtins.print') as mock_print:
        logger_instance.debug("Test Debug")
        mock_print.assert_called_once()
        assert "Test Debug" in mock_print.call_args[0][0]
        mock_logger.debug.assert_called_once_with("Test Debug")

    # Test with debug_mode=False
    logger_instance.debug_mode = False
    mock_logger.debug.reset_mock()
    with patch('builtins.print') as mock_print:
        logger_instance.debug("Test Debug False")
        mock_print.assert_not_called()
        mock_logger.debug.assert_called_once_with("Test Debug False")

def test_logger_banner(logger_instance):
    with patch('builtins.print') as mock_print:
        logger_instance.banner()
        # Should be called multiple times for different lines of the banner
        assert mock_print.call_count >= 5
        # Verify it prints something that looks like the banner
        all_calls = "".join([str(call) for call in mock_print.call_args_list])
        assert "INSTAGRAM OSINT" in all_calls

@patch('main.log')
@patch('main.requests.Session')
@patch('main.os.path.exists')
@patch('main.os.utime')
@patch('main.action.download_blob_video')
def test_download_file_success(mock_blob, mock_utime, mock_exists, mock_session_class, mock_log):
    mock_exists.return_value = False
    mock_session = mock_session_class.return_value
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
    mock_session.get.return_value = mock_response

    with patch('builtins.open', mock_open()) as mocked_file:
        url = "https://example.com/image.jpg"
        filename, save_path = main.download_file(url, mock_session, None, "/tmp")

        assert filename == "image.jpg"
        assert save_path == "/tmp/image.jpg"
        mock_session.get.assert_called_once_with(url, stream=True, timeout=20)
        mock_response.raise_for_status.assert_called_once()
        mocked_file.assert_called_once_with("/tmp/image.jpg", "wb")
        mock_log.success.assert_called_once()

@patch('main.log')
@patch('main.os.path.exists')
def test_download_file_exists(mock_exists, mock_log):
    mock_exists.return_value = True

    url = "https://example.com/image.jpg"
    filename, save_path = main.download_file(url, None, None, "/tmp", timestamp=123456)

    assert filename == "image.jpg"
    assert save_path == "/tmp/image.jpg"
    mock_log.debug.assert_called_once_with("File exists (skipping): image.jpg")
    with patch('main.os.utime') as mock_utime:
        # Re-run to check utime
        main.download_file(url, None, None, "/tmp", timestamp=123456)
        mock_utime.assert_called_once_with("/tmp/image.jpg", (123456, 123456))

@patch('main.log')
@patch('main.action.download_blob_video')
@patch('main.os.path.exists')
def test_download_file_blob(mock_exists, mock_blob, mock_log):
    mock_exists.return_value = False
    mock_blob.return_value = b"blob_content"

    with patch('builtins.open', mock_open()) as mocked_file:
        url = "blob:https://example.com/123"
        filename, save_path = main.download_file(url, None, MagicMock(), "/tmp", override_name="video.mp4")

        assert filename == "video.mp4"
        mock_blob.assert_called_once()
        mocked_file.assert_called_once_with("/tmp/video.mp4", "wb")
        mocked_file().write.assert_called_once_with(b"blob_content")

@patch('main.log')
@patch('main.os.path.exists')
def test_download_file_filename_logic(mock_exists, mock_log):
    mock_exists.return_value = False

    # Test deduction and extension
    with patch('main.requests.Session') as mock_session_class:
        mock_session = mock_session_class.return_value
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_session.get.return_value = mock_response

        with patch('builtins.open', mock_open()):
            # No extension in URL, media_type image
            fname, _ = main.download_file("https://example.com/path", mock_session, None, "/tmp", media_type="image")
            assert fname.endswith(".jpg")

            # No extension in URL, media_type video
            fname, _ = main.download_file("https://example.com/path2", mock_session, None, "/tmp", media_type="video")
            assert fname.endswith(".mp4")

    # Test truncation
    long_name = "a" * 250
    with patch('main.requests.Session') as mock_session_class:
        mock_session = mock_session_class.return_value
        mock_response = MagicMock()
        mock_response.iter_content.return_value = []
        mock_session.get.return_value = mock_response
        with patch('builtins.open', mock_open()):
            fname, save_path = main.download_file("https://example.com/img", mock_session, None, "/tmp", override_name=long_name)
            assert len(fname) == 200
            assert fname == long_name[-200:]

@patch('main.log')
@patch('main.requests.Session')
def test_download_file_error(mock_session_class, mock_log):
    mock_session = mock_session_class.return_value
    mock_session.get.side_effect = Exception("Network error")

    url = "https://example.com/image.jpg"
    filename, save_path = main.download_file(url, mock_session, None, "/tmp")

    assert filename is None
    assert save_path is None
    mock_log.error.assert_called_once()
    assert "Network error" in str(mock_log.error.call_args[0][0])

@patch('main.log')
def test_wait_for_login_success(mock_log):
    mock_driver = MagicMock()
    with patch('builtins.input', return_value=""):
        result = main.wait_for_login(mock_driver)
        assert result is True
        mock_driver.get.assert_called_once_with("https://www.instagram.com/accounts/login/")
        mock_log.warning.assert_called_once()
        mock_log.success.assert_called_once()

@patch('main.log')
def test_wait_for_login_interrupt(mock_log):
    mock_driver = MagicMock()
    with patch('builtins.input', side_effect=KeyboardInterrupt):
        result = main.wait_for_login(mock_driver)
        assert result is False
        mock_log.warning.assert_any_call("Login skipped/aborted by user.")

@patch('main.log')
def test_signal_handler(mock_log):
    main.STOP_REQUESTED = False
    main.signal_handler(None, None)
    assert main.STOP_REQUESTED is True
    mock_log.warning.assert_called_once()
