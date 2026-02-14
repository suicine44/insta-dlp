# insta-dlp

**insta-dlp** is a powerful Instagram OSINT (Open Source Intelligence) scraper and downloader. It leverages Selenium (via `undetected-chromedriver`) and direct API requests to fetch high-quality images, videos, reels, and metadata from Instagram profiles.

Key features include:
- **Interactive Login**: Seamlessly handle authentication with a persistent browser profile.
- **Tagged Posts**: Scrape posts where the target user is tagged.
- **Sorting**: Sort posts by likes, views, date, or random shuffle.
- **Video/Audio Merging**: Automatically merges high-quality video and audio streams using `ffmpeg`.
- **Headless Mode**: Run the scraper in the background.

## Prerequisites

Before running the project, ensure you have the following installed:

- **Python 3.8+**
- **Google Chrome** (latest stable version)
- **FFmpeg** (required for merging video and audio streams)

### Installing Google Chrome (Linux)

If you are on a Debian-based Linux system (e.g., Ubuntu), you can use the provided script to install Google Chrome:

```bash
chmod +x install_chrome.sh
./install_chrome.sh
```

### Installing FFmpeg

- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add it to your PATH.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/insta-dlp.git
   cd insta-dlp
   ```

2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

The main entry point for the scraper is `main.py`.

### Basic Usage

To scrape a target user's profile:

```bash
python3 main.py <username>
```

Example:
```bash
python3 main.py instagram
```

### Authentication

Instagram often requires login to view profiles or download media. `insta-dlp` uses a persistent Chrome profile located in the `chrome_profile/` directory.

**Option 1: Interactive Login (Recommended)**

Run the scraper with the `--login` flag. This will open a browser window where you can log in manually. Once logged in, press Enter in the terminal to continue.

```bash
python3 main.py <username> --login
```

**Option 2: Manual Profile Setup**

You can also use the `launch_browser.sh` script to open a browser with the persistent profile, log in, and then close it. Subsequent runs of `main.py` will use the saved session.

```bash
chmod +x launch_browser.sh
./launch_browser.sh
# Log in to Instagram in the opened browser, then close it.
```

### Command Line Arguments

| Argument | Description |
| :--- | :--- |
| `target` | The Instagram username to scrape. |
| `--login` | Enable interactive login mode before scraping. |
| `--tagged` | Scrape the user's "tagged" feed instead of their main posts. |
| `--headless` | Run the browser in headless mode (background). Note: Login might be difficult in headless mode. |
| `--mute` | Mute browser audio (default: True). Use `--no-mute` to enable audio. |
| `--sort` | Sort order for posts. Options: `default`, `reverse`, `random`, `likes`, `views`. |
| `--debug` | Enable verbose debug output. |

### Examples

**Scrape tagged posts sorted by likes:**
```bash
python3 main.py <username> --tagged --sort likes
```

**Run in headless mode (after logging in):**
```bash
python3 main.py <username> --headless
```

## Project Structure

Here is an overview of the key files in the repository:

- **`main.py`**: The main script. It handles argument parsing, initializes the scraper, manages the download loop, and orchestrates the overall process.
- **`driver_setup.py`**: Configures the Selenium WebDriver using `undetected-chromedriver`. It manages browser options, including the persistent user profile (`chrome_profile/`), headless mode, and performance logging capabilities.
- **`instagram_actions.py`**: Contains the core logic for interacting with Instagram. This includes functions for scrolling, parsing the DOM (BeautifulSoup), extracting JSON data from the API, handling video downloads, and merging streams.
- **`install_chrome.sh`**: A helper Bash script to automate the installation of Google Chrome on Linux systems.
- **`launch_browser.sh`**: A utility script that launches a Chrome instance using the same persistent profile as the scraper. Useful for manual login or debugging.
- **`requirements.txt`**: Lists all Python libraries required for the project.

## Output

Downloaded content is saved in the `targets/<username>/` directory, organized into:
- `instagram/images/`
- `instagram/videos/`
- `instagram/data/` (JSON metadata)
