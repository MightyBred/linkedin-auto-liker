import json
import os
import time
import random
from datetime import date


from playwright.sync_api import sync_playwright


# =========================
# SETTINGS
# =========================

CDP_URL = "http://localhost:9222"
STATE_FILE = "linkedin_bot_state.json"

MAX_ACTIONS_PER_RUN = 100
MAX_SCROLLS = 75

MIN_DELAY_AFTER_CLICK = 3.0
MAX_DELAY_AFTER_CLICK = 6.0
MIN_DELAY_AFTER_SCROLL = 1.5
MAX_DELAY_AFTER_SCROLL = 3.0
SCROLL_DISTANCE = 600

REACTION_SELECTOR = "button[aria-label^='Reaction button state:']"


# =========================
# STATE
# =========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "date": str(date.today()),
            "actions_today": 0,
            "processed_posts": []
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return {
            "date": str(date.today()),
            "actions_today": 0,
            "processed_posts": []
        }

    if state.get("date") != str(date.today()):
        state["date"] = str(date.today())
        state["actions_today"] = 0
        state["processed_posts"] = []

    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# =========================
# LINKEDIN PAGE
# =========================

def get_linkedin_page(browser):
    for context in browser.contexts:
        for page in context.pages:
            if "linkedin.com" in page.url:
                return page

    raise RuntimeError(
        "No LinkedIn page found. Open https://www.linkedin.com/feed/ "
        "in the Chrome window launched with --remote-debugging-port=9222."
    )


# =========================
# RESTRICTION CHECK
# =========================

def restriction_detected(page):
    """
    Stop only for recognizable verification/restriction indicators.
    Do NOT use broad words such as 'challenge' by themselves.
    """

    url = page.url.lower()

    restricted_urls = [
        "/checkpoint/",
        "/challenge/",
        "/uas/login",
    ]

    if any(x in url for x in restricted_urls):
        return True, f"Restricted/checkpoint URL detected: {page.url}"

    try:
        body_text = page.locator("body").inner_text().lower()
    except Exception:
        return False, ""

    strong_indicators = [
        "verify your identity",
        "security verification",
        "we need to verify",
        "unusual activity",
        "account restricted",
        "temporarily restricted",
        "confirm your identity",
        "captcha verification",
    ]

    for phrase in strong_indicators:
        if phrase in body_text:
            return True, f"Possible LinkedIn verification/restriction: {phrase}"

    return False, ""


# =========================
# POST DETECTION
# =========================

def find_feed_posts(page):
    """
    LinkedIn's current feed uses reaction buttons rather than
    the older article/feed-shared-update-v2 selectors.

    Each reaction button is associated with its feed-post
    container five levels above it.
    """

    buttons = page.locator(REACTION_SELECTOR)
    posts = []

    for i in range(buttons.count()):
        button = buttons.nth(i)

        try:
            if not button.is_visible():
                continue

            post = button.locator("xpath=" + "/.." * 5)

            if not post.is_visible():
                continue

            text = post.inner_text().strip()

            # Skip advertisements/promoted posts.
            if "Promoted" in text:
                continue

            posts.append((post, button))

        except Exception:
            continue

    return posts


# =========================
# POST IDENTIFICATION
# =========================

def get_post_identifier(post, button):
    """
    Try several identifiers so the same post isn't processed repeatedly.
    """

    attributes = [
        "data-urn",
        "data-id",
        "data-activity-urn",
    ]

    for attr in attributes:
        try:
            value = post.get_attribute(attr)
            if value:
                return value
        except Exception:
            pass

    try:
        links = post.locator("a").all()

        for link in links:
            href = link.get_attribute("href")

            if href and ("/posts/" in href or "activity-" in href):
                return href
    except Exception:
        pass

    # Fallback based on visible post text.
    try:
        text = post.inner_text().strip()

        if text:
            return "text:" + text[:500]
    except Exception:
        pass

    return None


# =========================
# REACTION STATE
# =========================

def already_reacted(button):
    state = button.get_attribute("aria-label") or ""
    return "no reaction" not in state.lower()


# =========================
# PROCESS ONE POST
# =========================

def process_post(page, post, button, state):
    post_id = get_post_identifier(post, button)

    if not post_id:
        print("Could not identify post. Skipping.")
        return False

    if post_id in state["processed_posts"]:
        print("Already processed. Skipping.")
        return False

    if already_reacted(button):
        print("Already reacted. Marking as processed.")
        state["processed_posts"].append(post_id)
        save_state(state)
        return False

    try:
        post_text = post.inner_text().strip().replace("\n", " | ")

        print("\nCandidate post:")
        print(post_text[:300])

        button.scroll_into_view_if_needed()
        time.sleep(1)

        print("Clicking reaction button...")

        button.click()

        time.sleep(random.uniform(MIN_DELAY_AFTER_CLICK, MAX_DELAY_AFTER_CLICK))

        # Check whether the button's state changed.
        new_state = button.get_attribute("aria-label") or ""

        if "no reaction" not in new_state.lower():
            print("Reaction registered.")

            state["actions_today"] += 1
            state["processed_posts"].append(post_id)
            save_state(state)

            return True

        print("Reaction state did not change. Skipping.")

    except Exception as e:
        print("Error processing post:", e)

    return False


# =========================
# MAIN
# =========================

def main():

    state = load_state()

    if state["actions_today"] >= MAX_ACTIONS_PER_RUN:
        print("Maximum actions for this run already reached.")
        return

    with sync_playwright() as p:

        print("Connecting to Chrome...")

        browser = p.chromium.connect_over_cdp(CDP_URL)

        page = get_linkedin_page(browser)

        print("Connected to:")
        print(page.title())
        print(page.url)

        print("\nChecking page...")

        restricted, reason = restriction_detected(page)

        if restricted:
            print(reason)
            print("Stopping.")
            return

        actions = 0

        for scroll_number in range(MAX_SCROLLS):

            print(
                f"\n--- Scroll {scroll_number + 1}/{MAX_SCROLLS} ---"
            )

            restricted, reason = restriction_detected(page)

            if restricted:
                print(reason)
                print("Stopping.")
                return

            posts = find_feed_posts(page)

            print(f"Found {len(posts)} candidate posts.")

            for post, button in posts:

                if actions >= MAX_ACTIONS_PER_RUN:
                    print("Run limit reached.")
                    return

                if state["actions_today"] >= MAX_ACTIONS_PER_RUN:
                    print("Run limit reached.")
                    return

                restricted, reason = restriction_detected(page)

                if restricted:
                    print(reason)
                    print("Stopping.")
                    return

                if process_post(page, post, button, state):
                    actions += 1

                    print(
                        f"Actions this run: {actions}/"
                        f"{MAX_ACTIONS_PER_RUN}"
                    )

            page.mouse.wheel(0, SCROLL_DISTANCE)

            time.sleep(random.uniform(MIN_DELAY_AFTER_SCROLL, MAX_DELAY_AFTER_SCROLL))

        print("\nFinished.")
        print("Actions this run:", actions)
        print("Actions recorded today:", state["actions_today"])


if __name__ == "__main__":
    main()