import hashlib
import json
import os
import re
import requests

try:
  from pypdf import PdfReader
except Exception:
  PdfReader = None

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
CHANNEL_ID = "@ParamedixClasses"
SEEN_FILE = "seen_notices.json"

IMPORTANT_KEYWORDS = [
    "rsahc",
    "rpmc",
    "paramedical",
    "provisional",
    "marksheet",
    "result",
    "exam",
    "examination",
    "rehanded",
    "supplementary",
    "fee",
    "schedule",
    "notice",
    "college",
    "institute",
    "परीक्षा",
    "परिणाम",
    "अंकतालिका",
    "प्रमाण-पत्र",
    "शुल्क",
    "संस्थान",
    "सूचना",
    "आवेदन",
    "प्रवेश",
]


def load_seen():
  if os.path.exists(SEEN_FILE):
    try:
      with open(SEEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
          return set(data)
    except Exception:
      pass
  return set()


def save_seen(seen_set):
  try:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
      json.dump(list(seen_set)[-2000:], f, ensure_ascii=False, indent=2)
  except Exception as e:
    print(f"Error saving seen notices: {e}")


def extract_text_from_pdf(pdf_path):
  text_parts = []
  if PdfReader and os.path.exists(pdf_path):
    try:
      reader = PdfReader(pdf_path)
      for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
          text_parts.append(page_text.strip())
    except Exception as e:
      print(f"PDF text extraction error: {e}")

  combined = "\n".join(text_parts).strip()

  # Agar PDF scanned image hai aur text khali hai, to Gemini se read karein
  if not combined and GEMINI_API_KEY and os.path.exists(pdf_path):
    try:
      import base64
      with open(pdf_path, "rb") as f:
        b64_pdf = base64.b64encode(f.read()).decode("utf-8")

      url = (
          "https://generativelanguage.googleapis.com/v1beta/models/"
          f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
      )
      payload = {
          "contents": [{
              "parts": [
                  {
                      "inline_data": {
                          "mime_type": "application/pdf",
                          "data": b64_pdf,
                      }
                  },
                  {
                      "text": "Extract all text accurately from this official notice PDF."
                  },
              ]
          }]
      }
      r = requests.post(url, json=payload, timeout=45)
      if r.status_code == 200:
        combined = (
            r.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
    except Exception as e:
      print(f"Gemini PDF OCR fallback error: {e}")

  return combined


def match_keywords(text):
  low = (text or "").lower()
  matched = [kw for kw in IMPORTANT_KEYWORDS if kw.lower() in low]
  return matched


def summarize_with_gemini(raw_text, matched_kws):
  if not GEMINI_API_KEY:
    snippet = " ".join((raw_text or "").split())[:900]
    return (
        "📢 **RSAHC / Paramedical Update**\n\n"
        f"{snippet}\n\n"
        f"🔑 Matched: {', '.join(matched_kws[:6])}\n"
        f"Join {CHANNEL_ID}"
    )

  prompt = (
      "Create a clean, accurate, easy-to-read Telegram channel update in Hindi/Hinglish "
      "from this official notice text. Include important dates, fees, instructions, and documents if present. "
      f"End with 'Join {CHANNEL_ID}'. Do not invent any facts.\n\n"
      f"Notice Text:\n{raw_text[:4000]}"
  )

  for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    try:
      r = requests.post(
          url,
          json={"contents": [{"parts": [{"text": prompt}]}]},
          timeout=40,
      )
      if r.status_code == 200:
        msg = (
            r.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        if msg:
          if CHANNEL_ID.lower() not in msg.lower():
            msg += f"\n\nJoin {CHANNEL_ID}"
          return msg
    except Exception as e:
      print(f"Gemini summarize error ({model}): {e}")

  snippet = " ".join((raw_text or "").split())[:900]
  return f"📢 **RSAHC Update**\n\n{snippet}\n\nJoin {CHANNEL_ID}"


def send_telegram_message(text):
  if not BOT_TOKEN:
    print("BOT_TOKEN missing.")
    return False
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": CHANNEL_ID,
      "text": text[:4000],
      "disable_web_page_preview": True,
  }
  try:
    r = requests.post(url, data=payload, timeout=20)
    if r.status_code == 200:
      return True
    print(f"Telegram sendMessage failed: {r.text}")
    return False
  except Exception as e:
    print(f"Telegram error: {e}")
    return False


def process_notice_text(raw_text, source_label="Notice"):
  cleaned_norm = " ".join(re.sub(r"\s+", " ", (raw_text or "").lower()).split())
  if not cleaned_norm:
    print(f"[{source_label}] Empty text.")
    return False

  matched = match_keywords(cleaned_norm)
  if not matched:
    print(f"[{source_label}] No target keywords matched. Skipped.")
    return False

  notice_hash = hashlib.md5(cleaned_norm.encode("utf-8")).hexdigest()
  seen = load_seen()
  if notice_hash in seen:
    print(f"[{source_label}] Already posted. Skipped duplicate.")
    return False

  formatted_msg = summarize_with_gemini(raw_text, matched)
  if send_telegram_message(formatted_msg):
    seen.add(notice_hash)
    save_seen(seen)
    print(f"[{source_label}] Posted to {CHANNEL_ID} | Keywords: {matched}")
    return True
  return False


def process_pdf_file(pdf_path):
  text = extract_text_from_pdf(pdf_path)
  return process_notice_text(text, source_label=os.path.basename(pdf_path))


if __name__ == "__main__":
  sample_pdf = os.environ.get("NOTICE_PDF_PATH", "latest_notice.pdf")
  if os.path.exists(sample_pdf):
    process_pdf_file(sample_pdf)
  else:
    print("Set NOTICE_PDF_PATH or call process_pdf_file('path/to/file.pdf').")
    
