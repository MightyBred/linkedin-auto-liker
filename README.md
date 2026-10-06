\# LinkedIn Auto Liker

## Disclaimer

This project is provided for educational and personal automation purposes. Users are responsible for complying with LinkedIn's terms, policies, and applicable laws. The project does not attempt to bypass CAPTCHAs, verification systems, account restrictions, or other platform safeguards.

A Python/Playwright project that automates interacting with LinkedIn feed posts through a locally controlled Chrome browser.



\## Features



\- Connects to an existing Chrome session through Chrome DevTools Protocol

\- Detects reaction buttons on feed posts

\- Skips promoted posts

\- Tracks processed posts locally

\- Configurable action limit

\- Configurable delays

\- Stops when verification or account restriction indicators are detected



\## Requirements



\- Windows

\- Python 3

\- Google Chrome

\- Playwright



\## Installation



```powershell

py -m pip install -r requirements.txt

py -m playwright install chromium

