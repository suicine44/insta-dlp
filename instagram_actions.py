import time
import random
import re
import base64
import json
import subprocess
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

def human_sleep(min_seconds=2.0, max_seconds=5.0):
    """Sleeps for a random amount of time to simulate human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def download_blob_video(driver, blob_url):
    """
    Downloads a blob URL by using JavaScript to fetch it as a blob and convert to base64.
    """
    print(f"    [JS] Attempting to fetch blob: {blob_url}")
    script = """
    var uri = arguments[0];
    var callback = arguments[1];
    fetch(uri).then(res => res.blob()).then(blob => {
        var reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = function() {
            callback(reader.result);
        }
    }).catch(e => {
        console.error("Blob fetch failed:", e);
        callback(null);
    });
    """
    try:
        # execute_async_script allows waiting for the callback
        base64_data = driver.execute_async_script(script, blob_url)

        if not base64_data:
            return None

        # Remove header "data:video/mp4;base64," (or similar)
        if "," in base64_data:
            _, encoded = base64_data.split(",", 1)
        else:
            encoded = base64_data

        return base64.b64decode(encoded)
    except Exception as e:
        print(f"    [!] Blob extraction failed: {e}")
        return None

def scroll_human(driver, scroll_count=5):
    """
    Scrolls the page down in a non-linear, human-like way.
    """
    actions = ActionChains(driver)

    for _ in range(scroll_count):
        # Random scroll amount
        scroll_height = random.randint(400, 800)

        driver.execute_script(f"window.scrollBy(0, {scroll_height});")

        # Occasional "micro-moves" with mouse (optional but good for heuristics)
        try:
            # Move mouse slightly to center of screen
            actions.move_by_offset(random.randint(-10, 10), random.randint(-10, 10)).perform()
            # Reset offset logic is complex in selenium, so just perform simple move
            actions.reset_actions()
        except:
            pass # Ignore mouse move errors


        human_sleep(1.5, 3.5)

def unmute_video(driver):
    """
    Attempts to unmute the video using robust SVG targeting and ActionChains.
    Refined based on failure to trigger with simple JS clicks.
    """
    print("    [ACT] Attempting to unmute video...")

    # 1. Target the SVG specifically (Mute Icon)
    # This is more robust than generic ARIA labels which might be hidden/ambiguous
    # Common aria-labels for the button housing the SVG: "Audio is muted", "Click to enable audio"
    selectors = [
        "//*[@aria-label='Audio is muted']",
        "//*[@aria-label='Click to enable audio']",
        "//button[descendant::svg[contains(@aria-label, 'Audio is muted')]]",
        "//div[@role='button'][descendant::svg[@aria-label='Audio is muted']]"
    ]

    target_btn = None
    for sel in selectors:
        try:
            btns = driver.find_elements(By.XPATH, sel)
            for btn in btns:
                if btn.is_displayed():
                    target_btn = btn
                    print(f"    [ACT] Found mute button via selector: {sel}")
                    break
            if target_btn: break
        except:
            continue

    if target_btn:
        try:
            # Use ActionChains for a "real" click
            actions = ActionChains(driver)
            actions.move_to_element(target_btn).click().perform()
            human_sleep(0.5, 1.0)
            print("    [ACT] Clicked mute button with ActionChains.")
            return
        except Exception as e:
            print(f"    [!] ActionChains click failed: {e}")
            # Fallback to JS click
            driver.execute_script("arguments[0].click();", target_btn)

    # 2. Keyboard fallback (M)
    print("    [ACT] Sending 'M' key as fallback...")
    try:
        actions = ActionChains(driver)
        actions.send_keys("m").perform()
        human_sleep(0.5, 1.0)
    except:
        pass

def get_post_links(driver):
    """
    Extracts all visible post links from the current feed view.
    Returns a set of URLs to avoid duplicates.
    """
    soup = BeautifulSoup(driver.page_source, "html.parser")
    links = set()

    # Instagram post links usually look like /p/CODE/ or /reel/CODE/
    # We now handle both absolute (https://...) and relative (/) paths
    all_links = soup.find_all("a", href=True)
    print(f"    [DEBUG] Found {len(all_links)} total anchor tags.")

    for a in all_links:
        href = a["href"]

        # Check for /p/ or /reel/ segments
        # Regex explanation:
        # (?:https?://www\.instagram\.com)? -> Optional Domain
        # /(?:p|reel)/              -> /p/ or /reel/
        # ([\w-]+)/?                -> The code (captured)
        match = re.search(r"/(p|reel)/([\w-]+)", href)

        if match:
            # Reconstruct clean URL
            short_code = match.group(2) # Group 2 is the code
            # type = match.group(1) # p or reel
            full_url = f"https://www.instagram.com/p/{short_code}/"
            links.add(full_url)

    print(f"    [DEBUG] Filtered down to {len(links)} unique post links.")
    return links

def get_post_details_api(post_url, session):
    """
    Fetches full post details (Media + Metrics) using Instagram's ?__a=1&__d=dis endpoint.
    Returns dict or default structure on failure.
    """
    result = {"success": False, "likes": 0, "views": 0, "date": 0, "media": []}

    try:
        # Clean URL and append params
        base_url = post_url.split("?")[0]
        api_url = f"{base_url}?__a=1&__d=dis"

        # Add headers to mimic browsing context
        kwargs = {
            "timeout": 10,
            "headers": {
                "Referer": "https://www.instagram.com/",
                "x-requested-with": "XMLHttpRequest"
            }
        }

        resp = session.get(api_url, **kwargs)

        if resp.status_code != 200:
            # print(f"    [!] API Fail {resp.status_code}: {api_url}") # Debug only
            return result

        try:
            data = resp.json()
        except json.JSONDecodeError:
            return result

        # Navigate JSON structure
        items = data.get("graphql", {}).get("shortcode_media")
        if not items:
            items = data.get("items", [{}])[0]

        if not items:
            return result

        # Extract Metrics
        result["date"] = items.get("taken_at_timestamp", 0)
        result["views"] = items.get("video_view_count", 0)

        likes_node = items.get("edge_media_preview_like", {})
        result["likes"] = likes_node.get("count", 0)

        # Helper to extract media
        def extract_node(node):
            if node.get("is_video"):
                return {"type": "video", "url": node.get("video_url")}
            else:
                resources = node.get("display_resources", [])
                if resources:
                    best = sorted(resources, key=lambda x: x["config_width"], reverse=True)[0]
                    return {"type": "image", "url": best["src"]}
                elif node.get("display_url"):
                    return {"type": "image", "url": node["display_url"]}
            return None

        # Check for Carousel (Sidecar)
        if "edge_sidecar_to_children" in items:
            children = items["edge_sidecar_to_children"].get("edges", [])
            for child in children:
                node = child.get("node", {})
                res = extract_node(node)
                if res: result["media"].append(res)
        else:
            res = extract_node(items)
            if res: result["media"].append(res)

        result["success"] = True
        print(f"    [API] Post details: Likes={result['likes']}, Views={result['views']}, Media={len(result['media'])}")
        return result

    except Exception as e:
        print(f"    [!] API Error: {e}")
        return result

def get_stream_metadata(url):
    """
    Uses ffprobe to extract type, resolution, and duration from a URL.
    Returns dict: {'type': 'video'|'audio'|None, 'width': int, 'height': int, 'duration': float}
    """
    meta = {'type': None, 'width': 0, 'height': 0, 'duration': 0.0}

    # JSON Retry for Robustness (Primary method now)
    try:
        cmd_json = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,width,height:format=duration",
            "-of", "json",
            "--",
            url
        ]
        res = subprocess.run(cmd_json, capture_output=True, text=True, timeout=8)
        data = json.loads(res.stdout)

        # Duration
        if "format" in data and "duration" in data["format"]:
            meta['duration'] = float(data["format"]["duration"])

        # Streams
        if "streams" in data:
            for s in data["streams"]:
                if s.get("codec_type") == "video":
                    meta['type'] = 'video'
                    meta['width'] = int(s.get("width", 0))
                    meta['height'] = int(s.get("height", 0))
                    break # Take first video stream
                elif s.get("codec_type") == "audio":
                    meta['type'] = 'audio'

    except Exception as e:
        print(f"    [!] Probe error: {e}")

    return meta

def get_media_duration(file_path):
    """
    Returns the duration of a media file in seconds (float) using ffprobe.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "--",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def get_video_url_from_network_logs(driver):
    """
    Scans logs, probess ALL candidates, and verifies the BEST video/audio pair.
    """
    print("    [LOGS] Scanning network traffic for media files...")

    candidates = set()
    videos = [] # list of dicts with meta
    audios = [] # list of dicts with meta

    # 1. Collect phase
    for attempt in range(15):
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                try:
                    message_obj = json.loads(entry["message"])
                    message = message_obj.get("message", {})
                    if message.get("method") == "Network.responseReceived":
                        response = message.get("params", {}).get("response", {})
                        url = response.get("url", "")
                        mime = response.get("mimeType", "")

                        if "video" in mime or "audio" in mime or ".mp4" in url:
                            if url.startswith("http"):
                                clean = re.sub(r"(&|\?)bytestart=[0-9]+", "", url)
                                clean = re.sub(r"(&|\?)byteend=[0-9]+", "", clean)
                                if "init" not in clean and clean not in candidates:
                                    candidates.add(clean)
                except: continue

            # 2. Analyze phase
            if len(videos) == 0 or len(audios) == 0:
                if candidates:
                    print(f"    [LOGS] Analyzing {len(candidates)} streams for quality...")
                    for url in candidates:
                        # Check if we already analyzed this URL
                        if any(v['url'] == url for v in videos) or any(a['url'] == url for a in audios):
                            continue

                        meta = get_stream_metadata(url)
                        meta['url'] = url

                        if meta['type'] == 'video':
                            pixels = meta['width'] * meta['height']
                            meta['pixels'] = pixels
                            videos.append(meta)
                            print(f"    [VID] Found: {meta['width']}x{meta['height']} ({meta['duration']:.1f}s)")
                        elif meta['type'] == 'audio':
                            audios.append(meta)
                            print(f"    [AUD] Found: {meta['duration']:.1f}s")

            # 3. Decision phase
            if videos and audios:
                # Sort videos by pixels (quality) DESC
                videos.sort(key=lambda x: x['pixels'], reverse=True)
                # Sort audios by duration DESC (usually longer = better/complete)
                audios.sort(key=lambda x: x['duration'], reverse=True)

                best_video = videos[0]
                best_audio = audios[0]

                print(f"    [★] Selected BEST Video: {best_video['width']}x{best_video['height']} | Audio: {best_audio['duration']:.1f}s")
                return {"video": best_video['url'], "audio": best_audio['url']}

            if attempt < 14:
                if attempt % 5 == 0:
                    print(f"    [WAIT] Need pairs (V:{len(videos)} A:{len(audios)}). Waiting... ({attempt//5 + 1}/3)")
                time.sleep(0.5)

        except Exception as e:
            # Suppress noisy connection errors (common during shutdown/interrupts)
            msg = str(e)
            if "HTTPConnectionPool" in msg or "Max retries exceeded" in msg or "Connection refused" in msg:
                continue
            print(f"    [!] Scan error: {e}")

    return None

def extract_media_from_post(driver):
    """
    Parses the opened post page to extract high quality media.
    Works for single images, carousels (partial), and videos.

    Enhanced with:
    - 1080px minimum resolution for images
    - Multiple srcset parsing strategies
    - JSON-LD structured data extraction
    - data-src lazy-loaded image detection
    """
    soup = BeautifulSoup(driver.page_source, "html.parser")
    media_data = []
    seen_urls = set()  # Avoid duplicates

    MIN_IMAGE_WIDTH = 1080  # Minimum resolution requirement

    # =================================================================
    # STRATEGY 1: Videos (blob: or direct mp4)
    # =================================================================
    videos = soup.find_all("video")
    for v in videos:
        src = v.get("src")
        poster = v.get("poster")
        if src and src not in seen_urls:
            media_data.append({"type": "video", "url": src, "poster": poster})
            seen_urls.add(src)

    # =================================================================
    # STRATEGY 2: High-Quality Images with srcset (Best Quality First)
    # =================================================================
    images = soup.find_all("img", srcset=True)
    potential_images = [] # Store all candidates to sort later

    for img in images:
        srcset = img.get("srcset", "")
        alt = img.get("alt", "")

        # Skip small icons/profile pics (usually very short srcset or small patterns)
        if not srcset or len(srcset) < 30:
            continue

        # Parse srcset
        details = []
        for candidate in srcset.split(","):
            candidate = candidate.strip()
            match = re.match(r'^(.+?)\s+(\d+)(?:w|px)?$', candidate)
            if match:
                url = match.group(1)
                width = int(match.group(2))
                details.append((width, url))

        if details:
            # Sort this image's variants by width DESC
            details.sort(key=lambda x: x[0], reverse=True)
            best_width, best_url = details[0]

            # We want the LARGEST image available, but ignore tiny ones (<400)
            if best_width >= 400 and best_url not in seen_urls:
                 # Store (width, url, alt)
                 potential_images.append((best_width, best_url, alt))

    # Sort ALL potential images found by width DESC
    potential_images.sort(key=lambda x: x[0], reverse=True)

    # Take top images (if gallery, we might want multiple, but let's take all unique high-res)
    for width, url, alt in potential_images:
        media_data.append({
            "type": "image",
            "url": url,
            "width": width,
            "alt": alt
        })
        seen_urls.add(url)
        print(f"    [IMG] Found HD image: {width}px")

    # =================================================================
    # STRATEGY 3: data-src lazy-loaded images (Fallback)
    # =================================================================
    if not media_data:
        lazy_images = soup.find_all("img", attrs={"data-src": True})
        for img in lazy_images:
            src = img.get("data-src")
            if src and src not in seen_urls:
                # Accept if decent resolution appears in URL or if it's main content
                # "p1080x1080", "s1080x1080", "s750x750", or just standard cdn
                if any(x in src for x in ["1080", "1440", "s750", "p1080", "p750"]):
                    media_data.append({"type": "image", "url": src})
                    seen_urls.add(src)
                    print(f"    [IMG] Found lazy-loaded image")

    # =================================================================
    # STRATEGY 4: JSON-LD Structured Data
    # =================================================================
    if not media_data:
        try:
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                if script.string:
                    data = json.loads(script.string)
                    content_url = data.get("contentUrl") or data.get("thumbnailUrl")
                    if content_url and content_url not in seen_urls:
                        if ".jpg" in content_url or ".png" in content_url:
                            media_data.append({"type": "image", "url": content_url})
                            seen_urls.add(content_url)
                            print(f"    [IMG] Found JSON-LD image")
        except Exception:
            pass

    # =================================================================
    # STRATEGY 5: Meta Tags Fallback (Last Resort)
    # =================================================================
    if not media_data:
        # Try og:video first
        og_video = soup.find("meta", property="og:video")
        if og_video and og_video.get("content"):
            url = og_video["content"]
            if url not in seen_urls:
                media_data.append({"type": "video", "url": url})
                seen_urls.add(url)

        # Then og:image (Warning: often cropped)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            url = og_image["content"]
            if url not in seen_urls:
                media_data.append({"type": "image", "url": url})
                seen_urls.add(url)
                print(f"    [!] Using og:image fallback (Quality/Crop risk)")

    # =================================================================
    # STRATEGY 6: Direct high-res image links in article
    # =================================================================
    # Often redundant if Strategy 2 works, but good as backup if srcset parsing fails
    if not media_data:
        article = soup.find("article")
        if article:
            article_imgs = article.find_all("img")
            for img in article_imgs:
                src = img.get("src", "")
                if src and src not in seen_urls:
                    if any(x in src for x in ["s1080x", "s1440x", "1080w", "1280", "s750"]):
                        media_data.append({"type": "image", "url": src})
                        seen_urls.add(src)
                        print(f"    [IMG] Found article image")

    return media_data


def extract_metadata(driver):
    """Extracts caption, date, and likes (if visible)."""
    soup = BeautifulSoup(driver.page_source, "html.parser")
    meta = {}

    # Extract Date
    time_tag = soup.find("time")
    if time_tag:
        meta["date"] = time_tag.get("datetime")
        meta["date_text"] = time_tag.text

    # Extract Caption
    # Instagram structure: h1 is usually the caption in post view, or specific uls
    # We'll try finding the first user text
    try:
        # Often the caption is inside an h1 or div with class _a9zs
        # This is brittle, using meta description is safer for filename
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            content = og_desc.get("content", "")
            # usually "Likes, Comments - Caption (@user) on Instagram..."
            meta["caption"] = content
        else:
             meta["caption"] = driver.title
    except Exception:
        meta["caption"] = "unknown_caption"

    return meta

def verify_post_owner(driver, target_username):
    """
    Checks if the current post belongs to the target username.
    Returns True if match or uncertain, False if definitely different.
    """
    try:
        # Strategy 1: Look for the username link in the header
        # Usually internal href = "/username/"
        header_links = driver.find_elements(By.XPATH, "//header//a")
        for link in header_links:
            href = link.get_attribute("href")
            if href and f"/{target_username}/" in href:
                return True

        # Strategy 2: Check meta tags
        soup = BeautifulSoup(driver.page_source, "html.parser")
        meta_auth = soup.find("meta", property="og:title")
        if meta_auth:
            content = meta_auth.get("content", "")
            if f"(@{target_username})" in content:
                return True

        # If we can't find it, assume SAFE (don't skip) or STRICT?
        # Given the "corruption" issue, let's be strict if we find SOMEONE ELSE
        if header_links:
            # Check if we see ANOTHER username
            for link in header_links:
                href = link.get_attribute("href")
                if href and "/p/" not in href and "/explore/" not in href:
                     # It's a profile link, if not target, then reject
                     if target_username not in href:
                         print(f"    [SKIP] Post owner seems to be: {href}")
                         return False

        return True
    except Exception:
        return True # Fail open to avoid skipping valid posts on error
