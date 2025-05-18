# Instagram Automation Bot

This project is an **Instagram Automation Bot** built with Python, Selenium, and undetected-chromedriver. It automates the process of following and unfollowing Instagram users using multiple accounts, with support for proxies and robust logging.

## Features
- Automates Instagram actions (follow/unfollow) for a list of target users
- Supports multiple Instagram accounts (read from `accounts.csv`)
- Optional proxy support for each account
- Randomized delays and action limits to mimic human behavior
- Robust logging and session tracking
- Error handling and proxy validation

## How It Works
1. **Accounts and Targets**: The bot reads Instagram account credentials and proxies from `accounts.csv`, and a list of target users and actions from `targets.csv`.
2. **Session Management**: For each account, a browser session is started (optionally using a proxy). The bot logs in and performs the specified actions (follow/unfollow) on the target users.
3. **Logging**: All actions and errors are logged to the `logs/` directory, with separate files for successes and failures.

## File Structure
- `main.py` - Main script containing the bot logic
- `accounts.csv` - List of Instagram accounts and proxies (see format below)
- `targets.csv` - List of target usernames and actions (see format below)
- `logs/` - Directory where logs and session results are saved

## Setup
1. **Install Requirements**
   ```bash
   pip install -r requirements.txt
   ```
   (You may also need to install Chrome and the correct version of undetected-chromedriver.)

2. **Prepare Input Files**
   - `accounts.csv`:
     ```csv
     username,password,proxy
     your_username,your_password,http://user:pass@host:port
     ```
     (Proxy is optional. Leave blank if not using a proxy.)
   - `targets.csv`:
     ```csv
     username,action
     targetuser1,follow
     targetuser2,unfollow
     ```

3. **Run the Bot**
   ```bash
   python main.py
   ```

## Configuration
You can adjust settings such as action limits and delays in the `CONFIG` dictionary at the top of `main.py`:
- `ACTION_LIMIT_PER_SESSION`: Max actions per account per session
- `MIN_DELAY`, `MAX_DELAY`: Random delay range between actions (in seconds)

## Notes
- Use this tool responsibly and in accordance with Instagram's terms of service.
- Excessive automation may result in account bans or restrictions.
- Proxy support is included for privacy and to reduce the risk of bans.

## License
This project is for educational purposes only. 