import os
import undetected_chromedriver as uc

def get_driver(headless=False, mute_audio=False):
    options = uc.ChromeOptions()
    
    # 1. Profile Persistence
    # Use the 'chrome_profile' folder in the scraper directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(base_dir, "chrome_profile")
    
    options.add_argument(f"--user-data-dir={profile_dir}")
    # Using 'Default' profile usually not needed with user-data-dir alone in UC, 
    # but good for consistency if trying to stick to one profile.
    # options.add_argument("--profile-directory=Default")
    
    # 2. Performance Logs (for capturing network traffic)
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    # 3. Headless Mode
    if headless:
        options.add_argument("--headless=new") 

    # 4. Mute Audio
    if mute_audio:
        options.add_argument("--mute-audio")

    # 5. Initialize
    # version_main allows specifying a major chrome version if auto-detection fails
    options.add_argument("--window-size=1920,1080")
    
    driver = uc.Chrome(options=options, version_main=None)  
    
    # Set window size (important for high-res media)
    try:
        driver.set_window_size(1920, 1080)
    except Exception:
        # Fails in some headless environments or if window not found immediately
        pass
    
    return driver

if __name__ == "__main__":
    # Test execution
    d = get_driver(headless=False)
    d.get("https://checker.of.visuals.com") # Simple check
    input("Press Enter to close...")
    d.quit()
