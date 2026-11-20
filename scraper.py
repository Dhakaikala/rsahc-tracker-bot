import hashlib
import json
import os
import re
import requests

try:
  from pypdf import PdfReader
except Exception:
  PdfReader = None

NOTICE_BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", "9222243244:AAHdY4RDyRJuZwT5R9h2_XGUkOnRSZdYIwE"
).strip()
NOTICE_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
NOTICE_CHANNEL = "@ParamedixClasses"
PROMO_LINE = "✅ Join : @ParamedixClasses"
SEEN_NOTICES_FILE = "seen_notices.json"

NOTICE_KEYWORDS = [
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


def load_seen_notices():
  if os.path.exists(SEEN_NOTICES_FILE):
    try:
      with open(SEEN_NOTICES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
          return set(data)
    except Exception:
      pass
  return set()


def save_seen_notices(seen_set):
  try:
    with open(SEEN_NOTICES_FILE, "w", encoding="utf-8") as f:
      json.dump(list(seen_set)[-2000:], f, ensure_ascii=False, indent=2)
  except Exception as e:
    print(f"Error saving seen notices: {e}")


def extract_pdf_text(pdf_path):
  parts = []
  if PdfReader and os.path.exists(pdf_path):
    try:
      reader = PdfReader(pdf_path)
      for page in reader.pages:
        t = page.extract_text() or ""
        if t.strip():
          parts.append(t.strip())
    except Exception as e:
      print(f"PDF read error: {e}")

  text = "\n".join(parts).strip()

  # Agar scanned PDF hai aur text nahi nikla to Gemini se padhein
  if not text and NOTICE_GEMINI_KEY and os.path.exists(pdf_path):
    try:
      import base64
      with open(pdf_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")

      url = (
          "https://generativelanguage.googleapis.com/v1beta/models/"
          f"gemini-2.5-flash:generateContent?key={NOTICE_GEMINI_KEY}"
      )
      payload = {
          "contents": [{
              "parts": [
                  {
                      "inline_data": {
                          "mime_type": "application/pdf",
                          "data": b64_data,
                      }
                  },
                  {"text": "Extract all text from this official notice PDF."},
              ]
          }]
      }
      r = requests.post(url, json=payload, timeout=45)
      if r.status_code == 200:
        text = (
            r.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
    except Exception as e:
      print(f"Gemini PDF OCR error: {e}")

  return text


def enforce_promo_footer(message_text):
  lines = [
      line.strip()
      for line in (message_text or "").splitlines()
      if PROMO_LINE.lower() not in line.lower()
      and "join @paramedixclasses" not in line.lower()
      and "join : @paramedixclasses" not in line.lower()
  ]
  body = "\n".join(lines).strip()
  if not body:
    return PROMO_LINE
  return f"{body}\n\n{PROMO_LINE}"


def generate_auto_caption(raw_text, matched_kws):
  if NOTICE_GEMINI_KEY:
    prompt = (
        "Write a clear, crisp, student-friendly Telegram caption in Hindi/Hinglish "
        "based on this official notice/update text. Include key dates, fees, eligibility, "
        "or important instructions accurately without inventing anything. "
        "Do NOT add a footer or join line yourself—keep it clean and informative.\n\n"
        f"Text:\n{raw_text[:4000]}"
    )
    for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
      url = (
          "https://generativelanguage.googleapis.com/v1beta/models/"
          f"{model}:generateContent?key={NOTICE_GEMINI_KEY}"
      )
      try:
        r = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=40,
        )
        if r.status_code == 200:
          out = (
              r.json()
              .get("candidates", [{}])[0]
              .get("content", {})
              .get("parts", [{}])[0]
              .get("text", "")
              .strip()
          )
          if out:
            return enforce_promo_footer(out)
      except Exception as e:
        print(f"Caption generation error ({model}): {e}")

  clean_snip = " ".join((raw_text or "").split())[:750]
  kw_str = ", ".join(matched_kws[:5]) if matched_kws else "Official Update"
  fallback = (
      f"📢 **RSAHC / Paramedical Update**\n\n"
      f"{clean_snip}\n\n"
      f"📌 Topics: {kw_str}"
  )
  return enforce_promo_footer(fallback)


def send_notice_to_channel(text):
  if not NOTICE_BOT_TOKEN:
    print("BOT_TOKEN missing.")
    return False
  final_msg = enforce_promo_footer(text)[:4000]
  url = f"https://api.telegram.org/bot{NOTICE_BOT_TOKEN}/sendMessage"
  try:
    r = requests.post(
        url,
        data={
            "chat_id": NOTICE_CHANNEL,
            "text": final_msg,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    if r.status_code == 200:
      return True
    print(f"Telegram sendMessage failed: {r.text}")
    return False
  except Exception as e:
    print(f"Telegram error: {e}")
    return False


def check_and_post_notice(text_or_pdf_path, is_pdf=False, label="Notice"):
  raw_text = (
      extract_pdf_text(text_or_pdf_path) if is_pdf else (text_or_pdf_path or "")
  )
  norm_text = " ".join(re.sub(r"\s+", " ", raw_text.lower()).split())
  if not norm_text:
    return False

  matched = [k for k in NOTICE_KEYWORDS if k.lower() in norm_text]
  if not matched:
    return False

  h = hashlib.md5(norm_text.encode("utf-8")).hexdigest()
  seen = load_seen_notices()
  if h in seen:
    return False

  caption = generate_auto_caption(raw_text, matched)
  if send_notice_to_channel(caption):
    seen.add(h)
    save_seen_notices(seen)
    print(f"[{label}] Posted caption to {NOTICE_CHANNEL} | Keywords: {matched}")
    return True
  return False
  
