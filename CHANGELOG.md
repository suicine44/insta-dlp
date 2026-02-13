# Changelog

All notable changes to the **Instagram OSINT Scraper** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **CLI Arguments**: 
  - `--login`: Launches a dedicated browser session for secure manual login (replacing `launch_browser.sh`).
  - `--tagged`: Enables scraping of the "Tagged" feed (`/username/tagged/`).
  - `--headless`: **Verified** working. Runs the browser in the background (hidden).
  - `--mute/--no-mute`: Browser audio is now muted by default (`--mute`) for silent operation. Use `--no-mute` to hear audio.
- **Graceful Exit**: Implemented `Ctrl+C` signal handling to close the driver/scraper cleanly without stack traces.
- **HEIC Support**: Added explicit detection and download support for `.heic` images.
- **Robust Cleanup**: Implemented a temporary file tracking system to ensure `.temp` files are deleted even if errors occur.
- **Fallback Logic**: If audio download fails during video scraping, the valid video stream is now automatically renamed and saved instead of being discarded as a temp file.

### Changed
- **Refactor**: Complete rewrite of `main.py` to support modular feature flags and better error handling.

## [BETA1] - 2025-12-12

### Added
- **Project Structure**: Established comprehensive folder structure under `osint-linux/scraper`.
- **Media Output Hierarchy**: 
  - Videos: `targets/{username}/instagram/videos/`
  - Images: `targets/{username}/instagram/images/`
  - Metadata: `targets/{username}/instagram/data/`
- **High-Quality Scraping**:
  - Implementation of `ffmpeg` stream merging for best video/audio quality.
  - 1080p visualization priority for image extraction.
  - Support for `blob:` video downloads via Selenium.
- **Login System**:
  - Persistent login via `launch_browser.sh` (using `chrome_profile`).
  - Session sharing between manual login and automated scraper.

### Fixed
- **Login Regression**: Fixed an issue where `launch_browser.sh` was saving the session to a legacy directory (`asmr_gaucha`), preventing the scraper from authenticating. The script now dynamically resolves the profile path relative to its own location.

### Known Issues
- Manual login is required periodically.
- "Login Mode" integrated into `main.py` is planned for future release to replace shell scripts.
