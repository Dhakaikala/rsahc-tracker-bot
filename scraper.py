import html
import json
import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Paramedix Bot Token & Channel
TELEGRAM_BOT_TOKEN = "8008140727:AAGMciDDyPzuvFzWhKXNqmrfTYLdnIRnfOI"
CHANNEL_USERNAME = "@ParamedixClasses"

TARGET_URL = "https://result.rpcraj.net/"
HISTORY_FILE = "last_seen.json"


def load_history():
  default_state = {
      "items": [],
      "forced_18_11_2026_done": False,
      "is_initialized": False,
  }
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
          return {
              "items": data.get("items", []) if isinstance(data.get("items"), list) else [],
              "forced_18_11_2026_done": bool(data.get("forced_18_11_2026_done", False)),
              "is_initialized": bool(data.get("is_initialized", True)),
          }
        elif isinstance(data, list):
          return {
              "items": data,
              "forced_18_11_2026_done": False,
              "is_initialized": True,
          }
    except Exception:
      pass
  return default_state


def save_history(state):
  try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
      json.dump(state, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"Error saving history: {e}")


def send_telegram_alert(title, link):
  try:
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"
    safe_title = html.escape(title)
    safe_link = html.escape(link)

    message = (
        f"🚨 <b>RSAHC / RPMC NEW RESULT DECLARED!</b> 🎓\n\n"
        f"📌 <b>{safe_title}</b>\n\n"
        f"🔗 <b>Check Result:</b> {safe_link}\n\n"
        f"✅ <b>Join : @ParamedixClasses</b>"
    )

    if ".pdf" in link.lower() or "pdf" in link.lower():
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "document": link,
          "caption": message,
          "parse_mode": "HTML",
      }
      res = requests.post(api_url + "sendDocument", data=payload, timeout=15)
    else:
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "text": message,
          "parse_mode": "HTML",
          "disable_web_page_preview": False,
      }
      res = requests.post(api_url + "sendMessage", data=payload, timeout=15)

    if res.status_code != 200:
      print(f"Telegram API Error: {res.text}")
    else:
      print(f"Sent to {CHANNEL_USERNAME}: {title}")
  except Exception as e:
    print(f"Telegram send error: {e}")


def is_18_nov_2026(text):
  return "18/11/2026" in text or "18-11-2026" in text


def scrape_paramedical():
  state = load_history()
  seen_items = state["items"]
  seen_titles = {
      item.get("title") for item in seen_items if isinstance(item, dict) and "title" in item
  }

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  current_found = []
  ignore_words = {
      "constituted by government of rajasthan",
      "rajasthan state allied and healthcare council",
      "results",
      "council",
  }

  try:
    response = requests.get(
        TARGET_URL, headers=headers, timeout=25, verify=False
    )
    if response.status_code == 200:
      soup = BeautifulSoup(response.text, "html.parser")

      # 1. किसी भी टेबल की हर रो (Row) को स्कैन करना
      for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
          cols = [
              " ".join(td.get_text(strip=True).split())
              for td in tr.find_all(["td", "th"])
          ]
          if len(cols) >= 1:
            row_text = " | ".join([c for c in cols if c])
            if len(row_text) > 10 and row_text.lower() not in ignore_words:
              a_tag = tr.find("a", href=True)
              item_url = (
                  urljoin(TARGET_URL, a_tag["href"])
                  if (a_tag and a_tag.get("href"))
                  else TARGET_URL
              )
              if row_text not in {x["title"] for x in current_found}:
                current_found.append({"title": row_text, "url": item_url})

      # 2. सभी लिंक्स (<a>) को स्कैन करना
      for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(strip=True).split())
        href = a["href"].strip()

        if (
            len(title) > 10
            and not href.startswith("javascript:")
            and not href.startswith("#")
            and title.lower() not in ignore_words
        ):
          full_url = urljoin(TARGET_URL, href)
          if title not in {x["title"] for x in current_found}:
            current_found.append({"title": title, "url": full_url})

      # 3. लिस्ट (<li>) या पैराग्राफ (<p>) में छपे रिजल्ट्स को भी पकड़ना
      for tag in soup.find_all(["li", "p"]):
        title = " ".join(tag.get_text(strip=True).split())
        if len(title) > 15 and title.lower() not in ignore_words:
          a_tag = tag.find("a", href=True)
          item_url = (
              urljoin(TARGET_URL, a_tag["href"])
              if (a_tag and a_tag.get("href"))
              else TARGET_URL
          )
          if title not in {x["title"] for x in current_found}:
            current_found.append({"title": title, "url": item_url})

  except Exception as e:
    print(f"Error scraping Paramedical site: {e}")

  if not state["is_initialized"]:
    # पहली बार बेसलाइन सेव करें, लेकिन 18/11/2026 वाले रिजल्ट्स तुरंत भेज दें
    state["items"] = current_found[:1000]
    state["is_initialized"] = True

    nov_18_items = [
        item for item in current_found if is_18_nov_2026(item["title"])
    ]
    for item in reversed(nov_18_items):
      send_telegram_alert(item["title"], item["url"])

    state["forced_18_11_2026_done"] = True
    save_history(state)
    print("First run completed. Sent 18/11/2026 results if available.")
    return

  to_post = []

  # अगर 18/11/2026 वाले रिजल्ट्स अभी तक फोर्स-पोस्ट नहीं हुए हैं, तो उन्हें भी भेजें
  if not state["forced_18_11_2026_done"]:
    nov_18_items = [
        item for item in current_found if is_18_nov_2026(item["title"])
    ]
    for item in reversed(nov_18_items):
      to_post.append(item)
    state["forced_18_11_2026_done"] = True

  # बाकी एकदम नए आइटम्स (जो पहले नहीं देखे गए)
  really_new = [
      item for item in current_found if item["title"] not in seen_titles
  ]
  for item in reversed(really_new):
    if item["title"] not in {x["title"] for x in to_post}:
      to_post.append(item)

  if to_post:
    for item in to_post:
      send_telegram_alert(item["title"], item["url"])

    merged = really_new + seen_items
    # डुप्लिकेट हटाते हुए लेटेस्ट हिस्ट्री सेव करें
    unique_items = []
    used = set()
    for item in merged:
      t = item.get("title")
      if t and t not in used:
        unique_items.append(item)
        used.add(t)

    state["items"] = unique_items[:1000]
    save_history(state)
  else:
    print("No new updates found.")


if __name__ == "__main__":
  scrape_paramedical()
