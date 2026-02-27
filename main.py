import os
import time
import json
import requests
import re
import sys
import signal
import argparse
import logging
import concurrent.futures
import driver_setup
import instagram_actions as action
from urllib.parse import urlparse
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
import random
import datetime
import subprocess

# ============================================================
# CONSTANTS & GLOBALS
# ============================================================
STOP_REQUESTED = False

class Logger:
    """
    Minimalist 'Hacker' Style Logger with ANSI colors.
    Logs verbose debug info to file, but keeps console clean.
    """
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    GREY = '\033[90m'

    def __init__(self, debug_mode=False, log_file="scraper.log"):
        self.debug_mode = debug_mode
        self.log_file = log_file

        # Setup file logging
        logging.basicConfig(
            filename=self.log_file,
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            filemode='a'
        )

    def info(self, msg):
        print(f"{self.BLUE}[*]{self.ENDC} {msg}")
        logging.info(msg)

    def success(self, msg):
        print(f"{self.GREEN}[+]{self.ENDC} {msg}")
        logging.info(f"SUCCESS: {msg}")

    def warning(self, msg):
        print(f"{self.WARNING}[!]{self.ENDC} {msg}")
        logging.warning(msg)

    def error(self, msg):
        print(f"{self.FAIL}[X]{self.ENDC} {msg}")
        logging.error(msg)

    def debug(self, msg):
        logging.debug(msg)
        if self.debug_mode:
            print(f"{self.GREY}[DEBUG] {msg}{self.ENDC}")

    def banner(self):
        print(f"{self.CYAN}{self.BOLD}")
        print("╔════════════════════════════════════════╗")
        print("║          INSTAGRAM OSINT v1.0          ║")
        print("╚════════════════════════════════════════╝")
        print(f"{self.ENDC}")

# Initialize Global Logger (will be set in main)
log = None

def signal_handler(sig, frame):
    global STOP_REQUESTED
    if log: log.warning("Ctrl+C detected! Stopping gracefully after current item...")
    else: print("\n[!] Ctrl+C detected! Stopping gracefully...")
    STOP_REQUESTED = True

signal.signal(signal.SIGINT, signal_handler)

def is_safe_username(username):
    """
    Validates the username to prevent path traversal and ensure it follows
    basic Instagram-like naming conventions.
    """
    if not username or len(username) > 30:
        return False

    # Check for path traversal sequences and separators
    if ".." in username or "/" in username or "\\" in username:
        return False

    # Instagram usernames only allow letters, numbers, periods, and underscores.
    # They cannot start or end with a period.
    # Logic: Start with alnum/underscore, middle can have dots, end with alnum/underscore.
    if not re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9._]*[a-zA-Z0-9_]$|^[a-zA-Z0-9_]$", username):
        return False

    return True


def wait_for_login(driver):
    """
    Pauses execution and waits for user to log in interactively.
    """
    driver.get("https://www.instagram.com/accounts/login/")
    log.warning("AUTHENTICATION REQUIRED: Please log in to Instagram now.")

    try:
        # Simple wait loop for user confirmation
        print(f"{Logger.WARNING}Press ENTER in this terminal once you have successfully logged in...{Logger.ENDC}")
        input()
        log.success("User confirmed login. Resuming session...")
    except KeyboardInterrupt:
        log.warning("Login skipped/aborted by user.")
        return False
    return True


def download_file(url, session, driver, output_dir, override_name=None, media_type="image", timestamp=None):
    try:
        if not url: return None, None

        # Deduce filename
        if override_name:
            filename = override_name
        else:
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename: filename = f"media_{int(time.time())}"
            # Add extension if missing
            if media_type == "image" and not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")):
                filename += ".jpg"
            elif media_type == "video" and not filename.lower().endswith(".mp4"):
                filename += ".mp4"

        save_path = os.path.join(output_dir, filename)

        # Avoid downloading if exists
        if os.path.exists(save_path):
            log.debug(f"File exists (skipping): {filename}")
            # Ensure timestamp is correct even if skipped? Optional, but good.
            if timestamp:
                try: os.utime(save_path, (timestamp, timestamp))
                except: pass
            return filename, save_path

        # Ensure name doesn't exceed OS limits
        if len(filename) > 200:
            filename = filename[-200:]
            save_path = os.path.join(output_dir, filename)

        # Download
        # If blob, use selenium script (not ideal for images usually, but fallback)
        if url.startswith("blob:"):
            log.debug(f"Detected BLOB video: {url}")
            content = action.download_blob_video(driver, url)
            if not content:
                log.debug("Failed to download blob content.")
                return None, None
            with open(save_path, "wb") as f:
                f.write(content)
        else:
            # Requests download
            resp = session.get(url, stream=True, timeout=20)
            resp.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Apply Timestamp (Organization)
        if timestamp:
            try:
                os.utime(save_path, (timestamp, timestamp))
            except Exception as e:
                log.warning(f"Failed to set timestamp: {e}")

        log.success(f"Saved: {filename}")
        return filename, save_path

    except Exception as e:
        log.error(f"Download Error: {e}")
    return None, None


def main():
    global log, STOP_REQUESTED
    parser = argparse.ArgumentParser(description="Instagram OSINT Scraper")
    parser.add_argument("target", help="Username of the target account")
    parser.add_argument("--login", action="store_true", help="Interactive login mode before scraping")
    parser.add_argument("--tagged", action="store_true", help="Scrape 'tagged' feed")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug output")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (hidden)")
    parser.add_argument("--mute", action="store_true", default=True, help="Mute browser audio (default: True)")
    parser.add_argument("--no-mute", action="store_false", dest="mute", help="Enable browser audio")
    parser.add_argument("--sort", choices=["default", "reverse", "random", "likes", "views"], default="default", help="Sort order of scraped posts")
    args = parser.parse_args()

    # Init Logger
    log = Logger(debug_mode=args.debug)
    log.banner()

    # Validate target username
    if not is_safe_username(args.target):
        log.error(f"Invalid or unsafe target username: '{args.target}'")
        sys.exit(1)

    # Paths
    SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
    OSINT_ROOT = os.path.dirname(SCRAPER_DIR)
    # Use basename as an additional layer of protection
    safe_target = os.path.basename(args.target)
    TARGET_DIR = os.path.join(OSINT_ROOT, "targets", safe_target)

    VIDEO_DIR = os.path.join(TARGET_DIR, "instagram", "videos")
    IMAGE_DIR = os.path.join(TARGET_DIR, "instagram", "images")
    DATA_DIR = os.path.join(TARGET_DIR, "instagram", "data")

    os.makedirs(VIDEO_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    log.info(f"Target: @{args.target}")
    log.info(f"Output: {TARGET_DIR}")

    # 1. Start Driver
    # Pass mute/headless options (requires updating driver_setup.py to accept them)
    try:
        driver = driver_setup.get_driver(headless=args.headless, mute_audio=args.mute)
    except TypeError:
        # Fallback if driver_setup isn't updated yet (safety net)
        log.debug("driver_setup.get_driver doesn't accept mute_audio yet.")
        driver = driver_setup.get_driver(headless=args.headless)

    # 2. Login Flow (Seamless)
    if args.login:
        if args.headless:
            log.warning("Login mode with Headless is difficult. If it fails, try without --headless.")
        if not wait_for_login(driver):
            log.info("Exiting...")
            driver.quit()
            return

    # 3. Setup Session
    session = requests.Session()
    session.headers.update({
        "User-Agent": driver.execute_script("return navigator.userAgent")
    })

    try:
        # Navigation
        target_url = f"https://www.instagram.com/{args.target}/"
        if args.tagged:
            log.info("Switching to TAGGED feed...")
            target_url += "tagged/"

        log.info(f"Navigating to {target_url}...")
        driver.get(target_url)
        action.human_sleep(3, 5)

        # Login Check (Auto-Trigger)
        if "Log In" in driver.title or "Entrar" in driver.title:
            log.error("Redirected to login page. Session likely expired or invalid.")
            # If headless, we might need to unhide to login? Difficult dynamically.
            # Best effort: pause and hope user can interact if not headless.
            if args.headless:
                log.error("Cannot login interactively in headless mode! Rerun with --login (without headless).")
                START_LOGIN_MODE = False
            else:
                START_LOGIN_MODE = True

            if START_LOGIN_MODE and wait_for_login(driver):
                # Navigate BACK to target after login
                log.info(f"Re-navigating to {target_url}...")
                driver.get(target_url)
                action.human_sleep(3, 5)
            else:
                log.error("Login required. Stopping.")
                return

        # Scroll Phase
        log.info("Scrolling feed to populate...")
        action.scroll_human(driver, scroll_count=3)

        # Harvest
        post_links = action.get_post_links(driver)
        log.info(f"Found {len(post_links)} unique posts.")


        # ==========================================================
        # PRE-SCAN / SORTING PHASE
        # ==========================================================
        posts_queue = [] # List of dicts: {'url':..., 'data':...}

        if args.sort in ["likes", "views"]:
            log.info(f"Pre-scanning {len(post_links)} posts for sort: {args.sort.upper()} (Parallel Mode)...")

            # Rate limiting / Worker handling
            # We use a wrapper to add specific handling if needed
            def scan_post(link):
                # Small random jitter to reduce block risk
                time.sleep(random.uniform(0.05, 0.2))
                det = action.get_post_details_api(link, session)
                det['url'] = link
                return det

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all
                futures = {executor.submit(scan_post, link): link for link in post_links}

                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    completed += 1
                    if completed % 10 == 0:
                        log.debug(f"Scanned {completed}/{len(post_links)}...")

                    try:
                        data = future.result()
                        posts_queue.append(data)
                    except Exception as e:
                        log.error(f"Scan worker failed: {e}")

            if args.sort == "likes":
                posts_queue.sort(key=lambda x: x.get('likes', 0), reverse=True)
            elif args.sort == "views":
                posts_queue.sort(key=lambda x: x.get('views', 0), reverse=True)

            top_val = posts_queue[0].get(args.sort, 0) if posts_queue else 0
            log.info(f"Sorting complete. Top post has {top_val} {args.sort}.")

        else:
            # Standard Modes
            for link in post_links:
                posts_queue.append({'url': link})

            if args.sort == "reverse":
                log.info("Sorting: Oldest First (Reverse)")
                posts_queue.reverse()
            elif args.sort == "random":
                log.info("Sorting: Random (Shuffle)")
                random.shuffle(posts_queue)

        # ==========================================================
        # DOWNLOAD PHASE
        # ==========================================================
        for i, item_data in enumerate(posts_queue):
            if STOP_REQUESTED:
                log.warning("Stopping loop as requested.")
                break

            link = item_data['url']

            # Metrics logging
            metrics_info = ""
            if 'likes' in item_data:
                metrics_info = f" | {item_data.get('likes')} Likes, {item_data.get('views')} Views"

            log.info(f"[{i+1}/{len(posts_queue)}] Processing: {link}{metrics_info}")

            # Temp tracking
            temp_files_to_clean = []

            try:
                # Flush logs
                _ = driver.get_log("performance")

                driver.get(link)
                action.human_sleep(2, 4)

                if not args.tagged:
                    if not action.verify_post_owner(driver, args.target):
                        log.debug(f"Skipping post (not owner)")
                        continue

                # Extract Metadata
                metadata = action.extract_metadata(driver)
                if 'likes' in item_data:
                    metadata['likes'] = item_data['likes']
                    metadata['views'] = item_data['views']

                # Consolidate Date/Timestamp
                post_date = item_data.get('date') or metadata.get('date')
                # If both fail, default to now or None (but None won't sort files)
                if not post_date: post_date = time.time()

                # Format for FFMPEG
                try:
                    dt_obj = datetime.datetime.fromtimestamp(post_date)
                    iso_date = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    iso_date = None

                caption = metadata.get("caption", "").split("on Instagram")[0]
                safe_caption = re.sub(r'[\\/*?:"<>|]', "", caption)[:60].strip()
                if not safe_caption:
                    safe_caption = f"post_{link.strip('/').split('/')[-1]}"

                action.unmute_video(driver)

                # Setup Variables for Paths
                api_media_list = item_data.get('media')
                if not api_media_list:
                    details_now = action.get_post_details_api(link, session)
                    api_media_list = details_now.get('media', [])
                    if details_now.get('date'): post_date = details_now['date'] # Update date if found now

                log_media = action.get_video_url_from_network_logs(driver)

                metadata["url"] = link
                metadata["media_files"] = []
                downloaded_any = False

                # PATH 1: API was successful (High Quality / Carousel)
                if api_media_list:
                    log.debug(f"Method: API ({len(api_media_list)} items)")
                    for idx, item in enumerate(api_media_list):
                       # Use index in filename for carousels
                       suffix = "" if len(api_media_list) == 1 else f"_{idx+1}"

                       fname, _ = download_file(
                           item["url"],
                           session,
                           driver,
                           VIDEO_DIR if item["type"] == "video" else IMAGE_DIR,
                           override_name=f"{safe_caption}{suffix}.{'mp4' if item['type']=='video' else 'jpg'}",
                           media_type=item["type"],
                           timestamp=post_date
                       )
                       if fname:
                           metadata["media_files"].append(fname)
                           downloaded_any = True

                # PATH 2: Network Logs (Video Only - if API missed video or failed)
                # Only use if we haven't downloaded a video yet OR if API failed entirely
                if not downloaded_any and log_media and log_media["video"]:
                    log.debug("Method: Network Logs")
                    # ... same video logic ...
                    video_url = log_media["video"]
                    audio_url = log_media["audio"]

                    temp_vid_name = f"temp_v_{safe_caption[:10]}.mp4"
                    # Download temps with timestamp too (good practice)
                    v_file, v_path = download_file(video_url, session, driver, VIDEO_DIR, override_name=temp_vid_name, media_type="video", timestamp=post_date)

                    if v_path: temp_files_to_clean.append(v_path)

                    final_filename = f"{safe_caption}.mp4"
                    final_path = os.path.join(VIDEO_DIR, final_filename)
                    merged = False

                    if audio_url:
                        temp_aud_name = f"temp_a_{safe_caption[:10]}.mp4"
                        a_file, a_path = download_file(audio_url, session, driver, VIDEO_DIR, override_name=temp_aud_name, media_type="video", timestamp=post_date)
                        if a_path: temp_files_to_clean.append(a_path)

                        if v_file and a_file:
                            dur_v = action.get_media_duration(v_path)
                            dur_a = action.get_media_duration(a_path)
                            if abs(dur_v - dur_a) <= 2.0:
                                log.debug("Merging streams...")
                                # Add Metadata to FFMPEG
                                cmd = [
                                    "ffmpeg", "-y",
                                    "-i", v_path,
                                    "-i", a_path,
                                    "-c", "copy",
                                    "-loglevel", "error"
                                ]
                                if iso_date:
                                    cmd.extend(["-metadata", f"creation_time={iso_date}"])

                                # Add Description/Source Metadata
                                if caption:
                                    # Sanitize slightly for metadata preventing huge breaks
                                    clean_desc = caption.replace('"', "'")[:255]
                                    cmd.extend(["-metadata", f"title={clean_desc}"])
                                    cmd.extend(["-metadata", f"description={clean_desc}"])

                                cmd.extend(["-metadata", f"comment={link}"])
                                artist_name = "@" + link.split('/')[3] if len(link.split('/')) > 3 else "Instagram"
                                cmd.extend(["-metadata", f"artist={artist_name}"])

                                cmd.append(final_path)

                                try:
                                    subprocess.run(cmd, check=True)
                                    log.success(f"Merged: {final_filename}")
                                    # Update timestamp on merged file
                                    try: os.utime(final_path, (post_date, post_date))
                                    except: pass
                                    metadata["media_files"].append(final_filename)
                                    merged = True
                                except Exception as e:
                                    log.error(f"Merge failed: {e}")

                    if not merged and v_path and os.path.exists(v_path):
                        if os.path.exists(final_path):
                             pass
                        else:
                            os.rename(v_path, final_path)
                            log.success(f"Saved (Video Only): {final_filename}")
                            # Update timestamp on renamed file (renaming keeps it, but safe to force)
                            try: os.utime(final_path, (post_date, post_date))
                            except: pass
                            metadata["media_files"].append(final_filename)
                            if v_path in temp_files_to_clean: temp_files_to_clean.remove(v_path)

                    downloaded_any = True

                # PATH 3: DOM Fallback (Images/Carousel skipped by API)
                if not downloaded_any:
                     log.debug("Method: DOM extraction (Fallback)")
                     media_items = action.extract_media_from_post(driver)
                     for idx, item in enumerate(media_items):
                        item_type = item.get("type", "image")
                        suffix = "" if len(media_items) == 1 else f"_{idx+1}"
                        target_dir = IMAGE_DIR if item_type == "image" else VIDEO_DIR
                        fname, _ = download_file(
                            item["url"],
                            session,
                            driver,
                            target_dir,
                            override_name=f"{safe_caption}{suffix}.{'mp4' if item_type=='video' else 'jpg'}",
                            media_type=item_type,
                            timestamp=post_date
                        )
                        if fname: metadata["media_files"].append(fname)

            # Save Metadata

                # Save Metadata
                short_code = link.strip("/").split("/")[-1]
                json_path = os.path.join(DATA_DIR, f"{short_code}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)

            except (InvalidSessionIdException, WebDriverException) as driver_err:
                log.error(f"Browser connection lost: {driver_err}")
                log.warning("The browser window might have been closed or crashed.")
                STOP_REQUESTED = True
                break
            except Exception as item_error:
                err_str = str(item_error)
                # Suppress connection errors if we are trying to stop
                if STOP_REQUESTED and ("HTTPConnectionPool" in err_str or "Max retries exceeded" in err_str or "Connection refused" in err_str):
                    pass
                else:
                    log.error(f"Item Error: {item_error}")

            finally:
                if temp_files_to_clean:
                    for tp in temp_files_to_clean:
                        if os.path.exists(tp):
                            try: os.remove(tp)
                            except: pass

    except KeyboardInterrupt:
        log.warning("User interrupted session.")
    except Exception as e:
        # Suppress verbose connection errors if we are stopping
        err_str = str(e)
        if STOP_REQUESTED and ("HTTPConnectionPool" in err_str or "Max retries exceeded" in err_str or "invalid session" in err_str):
            log.debug(f"Suppressing shutdown error: {e}")
        else:
            log.error(f"Critical Error: {e}")
    finally:
        log.info("Closing driver...")
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
