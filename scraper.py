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
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
          return [
              item
              for item in data
              if isinstance(item, dict) and "title" in item
          ]
    except Exception:
      pass
  return None  # None का मतलब पहली बार रन हो रहा है


def save_history(history_list):
  try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
      json.dump(history_list, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"Error saving history: {e}")


def send_telegram_alert(title, link):
  try:
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"
    safe_title = html.escape(title)
    safe_link = html.escape(link)

    # शॉर्ट, आकर्षक और बोल्ड कैप्शन + आपकी फिक्स लाइन
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
  except Exception as e:
    print(f"Telegram send error: {e}")


def scrape_paramedical():
  existing_history = load_history()
  is_first_run = existing_history is None
  seen_items = existing_history if existing_history else []
  seen_titles = {
      item.get("title") for item in seen_items if isinstance(item, dict)
  }

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  current_found = []
  # वेबसाइट के स्टैटिक हेडर/फुटर शब्दों को इग्नोर करने के लिए
  ignore_words = [
      "constituted by government of rajasthan",
      "rajasthan state allied and healthcare council",
      "results",
      "council",
  ]

  try:
    response = requests.get(
        TARGET_URL, headers=headers, timeout=25, verify=False
    )
    if response.status_code == 200:
      soup = BeautifulSoup(response.text, "html.parser")

      # 1. किसी भी टेबल की हर रो (Row) को बिना शर्त उठाना
      for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
          cols = [
              " ".join(td.get_text(strip=True).split())
              for td in tr.find_all(["td", "th"])
          ]
          if len(cols) >= 1:
            row_text = " | ".join([c for c in cols if c])
            if len(row_text) > 10 and row_text not in seen_titles:
              if row_text.lower() not in ignore_words:
                a_tag = tr.find("a", href=True)
                item_url = (
                    urljoin(TARGET_URL, a_tag["href"])
                    if (a_tag and a_tag.get("href"))
                    else TARGET_URL
                )
                current_found.append({"title": row_text, "url": item_url})
                seen_titles.add(row_text)

      # 2. सभी लिंक्स (<a>) को स्कैन करना (चाहे PDF हो या वेबपेज लिंक)
      for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(strip=True).split())
        href = a["href"].strip()

        if (
            len(title) > 10
            and not href.startswith("javascript:")
            and not href.startswith("#")
        ):
          if title.lower() not in ignore_words:
            full_url = urljoin(TARGET_URL, href)
            if title not in seen_titles:
              current_found.append({"title": title, "url": full_url})
              seen_titles.add(title)

      # 3. लिस्ट (<li>) या अन्य टेक्स्ट ब्लॉक में छपे रिजल्ट्स को भी पकड़ना
      for tag in soup.find_all(["li", "p"]):
        title = " ".join(tag.get_text(strip=True).split())
        if len(title) > 15 and title.lower() not in ignore_words:
          a_tag = tag.find("a", href=True)
          item_url = (
              urljoin(TARGET_URL, a_tag["href"])
              if (a_tag and a_tag.get("href"))
              else TARGET_URL
          )
          if title not in seen_titles:
            current_found.append({"title": title, "url": item_url})
            seen_titles.add(title)

  except Exception as e:
    print(f"Error scraping Paramedical site: {e}")

  if is_first_run:
    save_history(HISTORY_FILE, current_found[:1000])
    print("First run baseline saved. No old data posted.")
  else:
    if current_found:
      really_new = [
          item
          for item in current_found
          if item["title"] not in {i.get("title") for i in seen_items}
      ]

      if really_new:
        updated_history = really_new + seen_items
        save_history(HISTORY_FILE, updated_history[:1000])

        for item in reversed(really_new):
          send_telegram_alert(item["title"], item["url"])
          print(f"Posted: {item['title']}")
      else:
        print("No new updates found.")
    else:
      print("No updates found.")


if __name__ == "__main__":
  scrape_paramedical()
