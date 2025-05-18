import time
import random
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List
import json
from pathlib import Path
import requests
from urllib.parse import urlparse, quote
import base64
import atexit
import signal
import sys

# === Configuration ===
CONFIG = {
    "ACTION_LIMIT_PER_SESSION": 100,
    "MIN_DELAY": 4,
    "MAX_DELAY": 9,
    "MAX_RETRIES": 3,
    "TIMEOUT": 15,
    "LOG_DIR": "logs",
    "PROXY_TEST_URL": "http://httpbin.org/ip",
    "PROXY_TEST_TIMEOUT": 10,
    "CHROME_VERSION": None  # Let it auto-detect
}

# === Setup Logging ===
def setup_logging():
    log_dir = Path(CONFIG["LOG_DIR"])
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"instagram_bot_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def format_proxy_url(proxy: str) -> str:
    """Format proxy URL with proper encoding."""
    try:
        parsed = urlparse(proxy)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError("Invalid proxy format")
            
        # Extract username and password
        auth = parsed.netloc.split('@')[0]
        host = parsed.netloc.split('@')[1]
        
        # URL encode the password
        username, password = auth.split(':')
        password = quote(password, safe='')
        
        # Reconstruct the proxy URL
        return f"{parsed.scheme}://{username}:{password}@{host}"
    except Exception as e:
        logger.error(f"Error formatting proxy URL: {str(e)}")
        return proxy

def validate_proxy(proxy: str) -> bool:
    """Validate if the proxy is working by making a test request."""
    try:
        formatted_proxy = format_proxy_url(proxy)
        parsed = urlparse(formatted_proxy)
        
        if not all([parsed.scheme, parsed.netloc]):
            logger.error(f"Invalid proxy format: {proxy}")
            return False

        proxies = {
            'http': formatted_proxy,
            'https': formatted_proxy
        }
        
        # Add proxy authentication headers
        auth = parsed.netloc.split('@')[0]
        headers = {
            'Proxy-Authorization': f'Basic {base64.b64encode(auth.encode()).decode()}'
        }
        
        response = requests.get(
            CONFIG["PROXY_TEST_URL"],
            proxies=proxies,
            headers=headers,
            timeout=CONFIG["PROXY_TEST_TIMEOUT"],
            verify=False  # Disable SSL verification for testing
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Proxy validation failed: {str(e)}")
        return False

def cleanup_driver(driver):
    """Safely cleanup Chrome driver."""
    if driver:
        try:
            # Store the process ID before quitting
            pid = driver.service.process.pid if driver.service and driver.service.process else None
            
            # Quit the driver
            driver.quit()
            
            # If we have a process ID, try to terminate it
            if pid:
                try:
                    import psutil
                    process = psutil.Process(pid)
                    process.terminate()
                except:
                    pass
            
            # Clear the driver's internal state
            driver._executable_path = None
            driver.service = None
            driver.command_executor = None
            
        except Exception as e:
            logger.error(f"Error during driver cleanup: {str(e)}")
        finally:
            # Ensure the driver object is properly cleaned up
            try:
                del driver
            except:
                pass

def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info("Received termination signal. Cleaning up...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class InstagramBot:
    def __init__(self, username: str, password: str, proxy: Optional[str] = None):
        self.username = username
        self.password = password
        self.proxy = proxy
        self.driver = None
        self.logger = logger
        self.use_proxy = False

        if proxy:
            formatted_proxy = format_proxy_url(proxy)
            if validate_proxy(formatted_proxy):
                self.use_proxy = True
                self.proxy = formatted_proxy
                self.logger.info(f"Using proxy: {formatted_proxy}")
            else:
                self.logger.warning(f"Proxy validation failed, will use direct connection")

    def __enter__(self):
        self.driver = self.create_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            cleanup_driver(self.driver)
            self.driver = None

    def create_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        
        if self.use_proxy:
            try:
                options.add_argument(f'--proxy-server={self.proxy}')
                parsed = urlparse(self.proxy)
                auth = parsed.netloc.split('@')[0]
                options.add_argument(f'--proxy-auth={auth}')
                self.logger.info(f"Added proxy configuration: {self.proxy}")
            except Exception as e:
                self.logger.error(f"Failed to configure proxy: {str(e)}")
                self.use_proxy = False
        
        # Additional options to help with proxy issues
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        
        try:
            driver = uc.Chrome(
                options=options,
                version_main=CONFIG["CHROME_VERSION"],
                driver_executable_path=None,
                browser_executable_path=None,
                suppress_welcome=True,
                use_subprocess=True  # Use subprocess to better handle cleanup
            )
            return driver
        except Exception as e:
            self.logger.error(f"Failed to create Chrome driver: {str(e)}")
            if self.use_proxy:
                self.logger.info("Retrying without proxy...")
                self.use_proxy = False
                options = uc.ChromeOptions()
                options.add_argument("--start-maximized")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-blink-features=AutomationControlled")
                driver = uc.Chrome(
                    options=options,
                    version_main=CONFIG["CHROME_VERSION"],
                    driver_executable_path=None,
                    browser_executable_path=None,
                    suppress_welcome=True,
                    use_subprocess=True
                )
                return driver
            raise

    def random_delay(self):
        time.sleep(random.uniform(CONFIG["MIN_DELAY"], CONFIG["MAX_DELAY"]))

    def login(self) -> bool:
        try:
            self.driver.get("https://www.instagram.com/accounts/login/")
            WebDriverWait(self.driver, CONFIG["TIMEOUT"]).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            
            self.driver.find_element(By.NAME, "username").send_keys(self.username)
            self.driver.find_element(By.NAME, "password").send_keys(self.password + Keys.ENTER)
            
            WebDriverWait(self.driver, CONFIG["TIMEOUT"]).until(
                EC.presence_of_element_located((By.XPATH, "//nav"))
            )
            
            # Handle popups
            for _ in range(2):
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[text()='Not Now']"))
                    ).click()
                except TimeoutException:
                    pass
            
            self.logger.info(f"Successfully logged in as {self.username}")
            return True
            
        except Exception as e:
            self.logger.error(f"Login failed for {self.username}: {str(e)}")
            return False

    def follow_user(self, target_username: str) -> bool:
        for attempt in range(CONFIG["MAX_RETRIES"]):
            try:
                self.driver.get(f"https://www.instagram.com/{target_username}/")
                WebDriverWait(self.driver, CONFIG["TIMEOUT"]).until(
                    EC.presence_of_element_located((By.XPATH, "//section"))
                )
                
                buttons = self.driver.find_elements(By.XPATH, "//button")
                for btn in buttons:
                    label = btn.text.strip()
                    if label in ["Follow", "Follow Back"]:
                        btn.click()
                        self.logger.info(f"Followed {target_username}")
                        return True
                    elif label in ["Following", "Requested"]:
                        self.logger.info(f"Already following {target_username}")
                        return True
                
                self.logger.warning(f"Could not find follow button for {target_username}")
                return False
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed for following {target_username}: {str(e)}")
                if attempt < CONFIG["MAX_RETRIES"] - 1:
                    self.random_delay()
                continue
        return False

    def unfollow_user(self, target_username: str) -> bool:
        for attempt in range(CONFIG["MAX_RETRIES"]):
            try:
                self.driver.get(f"https://www.instagram.com/{target_username}/")
                WebDriverWait(self.driver, CONFIG["TIMEOUT"]).until(
                    EC.presence_of_element_located((By.TAG_NAME, "header"))
                )
                
                buttons = self.driver.find_elements(By.XPATH, "//button")
                for btn in buttons:
                    label = btn.text.strip()
                    if label in ["Following", "Requested"]:
                        btn.click()
                        break
                else:
                    self.logger.info(f"Not following {target_username}")
                    return True

                WebDriverWait(self.driver, CONFIG["TIMEOUT"]).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
                )
                time.sleep(2)
                
                for div in self.driver.find_elements(By.XPATH, "//div[@role='dialog']//div"):
                    if div.text.strip().lower() == "unfollow":
                        div.click()
                        self.logger.info(f"Unfollowed {target_username}")
                        return True
                
                self.logger.warning(f"'Unfollow' not found in modal for {target_username}")
                return False
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed for unfollowing {target_username}: {str(e)}")
                if attempt < CONFIG["MAX_RETRIES"] - 1:
                    self.random_delay()
                continue
        return False

    def run_session(self, targets: pd.DataFrame) -> Dict[str, List[Dict]]:
        if not self.login():
            return {"success": [], "failure": []}

        success_log = []
        failure_log = []
        actions_done = 0

        for _, row in targets.iterrows():
            if actions_done >= CONFIG["ACTION_LIMIT_PER_SESSION"]:
                self.logger.info(f"Action limit ({CONFIG['ACTION_LIMIT_PER_SESSION']}) reached")
                break

            username = row["username"]
            action = row["action"].strip().lower()

            success = False
            if action == "follow":
                success = self.follow_user(username)
            elif action == "unfollow":
                success = self.unfollow_user(username)
            else:
                self.logger.warning(f"Invalid action: {action}")
                continue

            log_entry = {
                "target": username,
                "action": action,
                "timestamp": datetime.now().isoformat(),
                "status": "success" if success else "fail"
            }
            
            (success_log if success else failure_log).append(log_entry)
            actions_done += 1
            self.random_delay()

        return {"success": success_log, "failure": failure_log}

def save_logs(logs: Dict[str, List[Dict]], session_id: str):
    log_dir = Path(CONFIG["LOG_DIR"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for status, entries in logs.items():
        if entries:
            df = pd.DataFrame(entries)
            filename = log_dir / f"{status}_{session_id}_{timestamp}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"Saved {len(entries)} {status} logs to {filename}")

def main():
    try:
        accounts = pd.read_csv("accounts.csv")
        targets = pd.read_csv("targets.csv")
        
        for _, account in accounts.iterrows():
            session_id = f"{account['username']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Starting session {session_id} for {account['username']}")
            
            with InstagramBot(
                username=account["username"],
                password=account["password"],
                proxy=account.get("proxy")
            ) as bot:
                logs = bot.run_session(targets)
                save_logs(logs, session_id)
            
            logger.info(f"Completed session {session_id}")
            
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()
