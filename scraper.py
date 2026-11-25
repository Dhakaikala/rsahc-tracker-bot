from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import re
import sys
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_USERNAME = "@ParamedixClasses"
PROMO_FOOTER = "✅ Join : @ParamedixClasses"

STATE_FILE = "last_seen_paramedix.json"

PARAMEDICAL_SOURCES = [
    {"name": "RSAHC Main Home", "url": "https://rsahcouncil.org/"},
    {"name": "RPC Main Portal", "url": "https://www.rpcraj.net/"},
    {"name": "RPC / RSAHC Results", "url": "https://result.rpcraj.net/"},
    {"name": "RSAHC Examination", "url": "https://rsahcouncil.org/examination/"},
    {"name": "RSAHC Admission", "url": "https://rsahcouncil.org/admission/"},
    {
        "name": "RSAHC Affiliated Colleges",
        "url": "https://rsahcouncil.org/affiliated-colleges/",
    },
    {"name": "RSAHC Our Courses", "url": "https://rsahcouncil.org/our-courses/"},
    {"name": "RSAHC Syllabus", "url": "https://rsahcouncil.org/syllabus/"},
    {
        "name": "RPMC Counselling Portal",
        "url": "https://counselling.rpcraj.net/RpmCForm/JhSpage.php",
    },
    {
        "name": "RSAHC Notifications",
        "url": "https://rsahcouncil.org/notifications/",
    },
    {
        "name": "RSAHC Fee Structure",
        "url": "https://rsahcouncil.org/fee-structure/",
    },
    {
        "name": "RSAHC Registration Issued",
        "url": "https://rsahcouncil.org/registration-issued/",
    },
    {"name": "RSAHC Eligibility", "url": "https://rsahcouncil.org/eligibility/"},
    {
        "name": "Paramedical Professionals Reg.",
        "url": "https://rsahcouncil.org/registration-for-paramedical-professionals/",
    },
    {
        "name": "RSAHC Registration Process",
        "url": "https://rsahcouncil.org/registration-processs/",
    },
    {
        "name": "RSAHC Code of Ethics",
        "url": "https://rsahcouncil.org/code-of-ethics/",
    },
    {
        "name": "RSAHC Fee Structure 3",
        "url": "https://rsahcouncil.org/fee-structure-3/",
    },
]

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,hi-IN;q=0.8,hi;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
DOC_EXTS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".txt",
    ".csv",
)

SKIP_IMG_KEYWORDS = (
    "logo",
    "icon",
    "favicon",
    "arrow",
    "bullet",
    "social",
    "facebook",
    "twitter",
    "instagram",
    "youtube",
    "whatsapp",
    "spinner",
    "loading",
    "spacer",
    "header",
    "footer",
    "bg",
    "background",
    "counter",
    "headercounter",
    "visitor",
    "hitcounter",
    "captcha",
)

SKIP_URL_OR_TEXT = (
    "login",
    "signin",
    "signup",
    "privacy",
    "disclaimer",
    "terms",
    "sitemap",
    "forgot",
    "password",
    "headercounter",
    "hitcounter",
)

VOLATILE_QUERY_KEYS = {
    "expires",
    "signature",
    "key-pair-id",
    "policy",
    "x-amz-signature",
    "x-amz-credential",
    "x-amz-date",
    "x-amz-expires",
    "x-amz-security-token",
    "token",
    "ts",
    "time",
    "timestamp",
    "v",
    "ver",
}

_BOLD_UPPER = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
_BOLD_LOWER = "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"
_BOLD_DIGIT = "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"


def to_bold(text_str):
  out = []
  for ch in str(text_str or ""):
    if "A" <= ch <= "Z":
      out.append(_BOLD_UPPER[ord(ch) - ord("A")])
    elif "a" <= ch <= "z":
      out.append(_BOLD_LOWER[ord(ch) - ord("a")])
    elif "0" <= ch <= "9":
      out.append(_BOLD_DIGIT[ord(ch) - ord("0")])
    else:
      out.append(ch)
  return "".join(out)


def clean_text(val):
  return " ".join(str(val or "").strip().split())


def clean_url(url_str):
  return str(url_str or "").strip().strip("()[]\"'").strip()


def canonical_url(url_str):
  u = clean_url(url_str)
  if not u:
    return ""
  try:
    parsed = urlparse(u)
    kept_q = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in VOLATILE_QUERY_KEYS
    ]
    clean_q = urlencode(kept_q)
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        clean_q,
        "",
    ))
  except Exception:
    return u.split("?")[0]


def make_id(raw_str):
  return hashlib.sha256(str(raw_str or "").encode("utf-8")).hexdigest()[:24]


def get_ist_now_str():
  ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
  return ist_now.strftime("%d-%m-%Y %I:%M %p IST")


def load_state():
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
          seen_ids = (
              data.get("seen_ids", [])
              if isinstance(data.get("seen_ids"), list)
              else []
          )
          seen_urls = (
              data.get("seen_urls", [])
              if isinstance(data.get("seen_urls"), list)
              else []
          )
          return {
              "seen_ids": seen_ids,
              "seen_urls": [canonical_url(x) for x in seen_urls if clean_url(x)],
          }
    except Exception as e:
      print(f"Error reading {STATE_FILE}: {e}")
  return {"seen_ids": [], "seen_urls": []}


def save_state(state):
  try:
    payload = {
        "updated_at": get_ist_now_str(),
        "seen_ids": state.get("seen_ids", [])[-15000:],
        "seen_urls": state.get("seen_urls", [])[-15000:],
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
      json.dump(payload, f, ensure_ascii=False, indent=2)
  except Exception as e:
    print(f"Error saving {STATE_FILE}: {e}")


def classify_file_type(url_str, content_type=""):
  lower_u = clean_url(url_str).lower().split("?")[0]
  ct = str(content_type or "").lower()
  if lower_u.endswith(IMAGE_EXTS) or ct.startswith("image/"):
    return "image"
  if lower_u.endswith(DOC_EXTS) or "pdf" in ct or "octet-stream" in ct:
    return "document"
  return "link"


def is_likely_ui_asset(url_str, alt_text=""):
  combined = f"{clean_url(url_str).lower()} {clean_text(alt_text).lower()}"
  if any(bad in combined for bad in SKIP_IMG_KEYWORDS):
    return True
  try:
    path_file = urlparse(clean_url(url_str)).path.split("/")[-1]
    stem = path_file.rsplit(".", 1)[0] if "." in path_file else path_file
    if stem.isdigit() and len(stem) >= 6:
      return True
  except Exception:
    pass
  return False


def is_allowed_domain_or_file(url_str, title_str, kind):
  u = clean_url(url_str).lower()
  t = clean_text(title_str).lower()
  if not u.startswith(("http://", "https://")):
    return False
  parsed = urlparse(u)
  if not parsed.netloc:
    return False
  if any(bad in u or bad in t for bad in SKIP_URL_OR_TEXT):
    return False
  stripped_t = clean_text(title_str)
  if stripped_t.isdigit() and len(stripped_t) >= 5:
    return False

  allowed_domains = ("rsahcouncil.org", "rpcraj.net")
  if any(d in parsed.netloc for d in allowed_domains):
    return True
  if kind in ("document", "image"):
    return True
  return False


def fetch_with_session(session, page_url):
  parsed = urlparse(page_url)
  origin = f"{parsed.scheme}://{parsed.netloc}/"
  headers = dict(BASE_HEADERS)
  headers["Referer"] = origin
  return session.get(clean_url(page_url), headers=headers, timeout=25, verify=False)


def extract_items_from_page(session, source_name, page_url):
  items = []
  try:
    resp = fetch_with_session(session, page_url)
    if resp.status_code != 200:
      print(f"[{source_name}] HTTP {resp.status_code} for {page_url}")
      return items

    soup = BeautifulSoup(resp.text, "html.parser")
    seen_local = set()

    for tag in soup.find_all(["a", "iframe", "embed"]):
      href = tag.get("href") or tag.get("src") or ""
      full_url = clean_url(urljoin(page_url, href))
      if not full_url or full_url.startswith(("javascript:", "mailto:", "#")):
        continue
      c_url = canonical_url(full_url)
      if c_url in seen_local:
        continue

      title = clean_text(tag.get_text(" ", strip=True))
      if not title or len(title) < 2:
        title = clean_text(tag.get("title") or tag.get("aria-label") or "")
      if not title or len(title) < 2:
        path_part = urlparse(full_url).path.split("/")[-1]
        title = clean_text(re.sub(r"[-_]+", " ", path_part)) or "RSAHC Update"

      kind = classify_file_type(full_url)
      if not is_allowed_domain_or_file(full_url, title, kind):
        continue

      seen_local.add(c_url)
      items.append({
          "source": source_name,
          "title": title[:220],
          "url": full_url,
          "canonical_url": c_url,
          "kind": kind,
      })

    for img in soup.find_all("img"):
      src = clean_url(
          urljoin(
              page_url,
              img.get("src")
              or img.get("data-src")
              or img.get("data-lazy-src")
              or "",
          )
      )
      if not src:
        continue
      c_url = canonical_url(src)
      if c_url in seen_local:
        continue
      alt_text = clean_text(img.get("alt") or img.get("title") or "")
      if is_likely_ui_asset(src, alt_text):
        continue
      if not is_allowed_domain_or_file(src, alt_text, "image"):
        continue

      seen_local.add(c_url)
      path_name = clean_text(
          re.sub(
              r"[-_]+",
              " ",
              urlparse(src).path.split("/")[-1].rsplit(".", 1)[0],
          )
      )
      final_title = alt_text or path_name or "RSAHC Notice Image"
      items.append({
          "source": source_name,
          "title": final_title[:220],
          "url": src,
          "canonical_url": c_url,
          "kind": "image",
      })

    print(f"[{source_name}] Found {len(items)} items.")
  except Exception as e:
    print(f"[{source_name}] Error fetching page: {e}")
  return items


def build_caption(item):
  title = clean_text(item.get("title", "RSAHC / RPMC Update"))[:135]
  source = clean_text(item.get("source", "RSAHC / RPMC"))[:55]
  url = clean_url(item.get("url", ""))
  kind = item.get("kind", "link")

  badge = {
      "image": to_bold("IMAGE"),
      "document": to_bold("PDF / DOC"),
      "link": to_bold("NEW UPDATE"),
  }.get(kind, to_bold("ALERT"))

  header = f"🩺 {to_bold('PARAMEDIX ALERT')} • {badge}\n\n"
  footer = f"\n\n{PROMO_FOOTER}"

  body_lines = [
      f"📌 {to_bold(title)}",
      f"🏛️ {to_bold(source)}",
  ]
  if url:
    body_lines.append(f"🔗 {url}")

  caption = header + "\n".join(body_lines) + footer
  if len(caption) > 1024:
    max_body_len = 1024 - len(header) - len(footer) - 5
    trimmed_body = ("\n".join(body_lines))[: max(40, max_body_len)]
    caption = header + trimmed_body + "…" + footer
  return caption[:1024]


def download_binary(session, url_str):
  try:
    r = fetch_with_session(session, url_str)
    if r.status_code == 200 and r.content and len(r.content) > 150:
      ct = r.headers.get("Content-Type", "")
      return r.content, ct
  except Exception as e:
    print(f"Download failed for {url_str}: {e}")
  return None, ""


def send_telegram_item(session, item):
  if not TELEGRAM_BOT_TOKEN:
    print("Missing BOT_TOKEN.")
    return False

  caption = build_caption(item)
  url = clean_url(item.get("url", ""))
  kind = item.get("kind", "link")
  api_base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

  if kind in ("image", "document") and url:
    content, ct = download_binary(session, url)
    real_kind = classify_file_type(url, ct)
    if content:
      parsed_name = urlparse(url).path.split("/")[-1] or (
          "rsahc_notice.jpg" if real_kind == "image" else "rsahc_notice.pdf"
      )
      parsed_name = (
          re.sub(r"[^A-Za-z0-9._-]", "_", parsed_name)[:80] or "rsahc_notice"
      )

      if real_kind == "image":
        endpoint = f"{api_base}/sendPhoto"
        files = {"photo": (parsed_name, io.BytesIO(content))}
        data = {"chat_id": CHANNEL_USERNAME, "caption": caption}
      else:
        if "." not in parsed_name:
          parsed_name += ".pdf"
        endpoint = f"{api_base}/sendDocument"
        files = {"document": (parsed_name, io.BytesIO(content))}
        data = {"chat_id": CHANNEL_USERNAME, "caption": caption}

      try:
        res = requests.post(endpoint, data=data, files=files, timeout=45)
        if res.status_code == 200:
          return True
        print(f"Media send failed ({endpoint}): {res.text[:220]}")
      except Exception as e:
        print(f"Media post error: {e}")

  msg_text = caption
  if len(msg_text) > 4096:
    msg_text = msg_text[: 4096 - len(PROMO_FOOTER) - 4] + "…\n\n" + PROMO_FOOTER

  try:
    res = requests.post(
        f"{api_base}/sendMessage",
        data={
            "chat_id": CHANNEL_USERNAME,
            "text": msg_text,
            "disable_web_page_preview": False,
        },
        timeout=25,
    )
    if res.status_code == 200:
      return True
    print(f"sendMessage failed: {res.text[:220]}")
    return False
  except Exception as e:
    print(f"sendMessage error: {e}")
    return False


def main():
  seed_only = "--seed-only" in sys.argv
  if not TELEGRAM_BOT_TOKEN and not seed_only:
    print("BOT_TOKEN missing.")
    return

  state = load_state()
  seen_ids = set(state.get("seen_ids", []))
  seen_urls = set(canonical_url(x) for x in state.get("seen_urls", []) if x)

  session = requests.Session()
  collected = []
  for src in PARAMEDICAL_SOURCES:
    collected.extend(extract_items_from_page(session, src["name"], src["url"]))
    time.sleep(0.8)

  if seed_only:
    seeded = 0
    for it in collected:
      c_u = it.get("canonical_url") or canonical_url(it.get("url", ""))
      t = clean_text(it.get("title", ""))
      item_id = make_id(f"{c_u}|{t}")
      if item_id not in seen_ids:
        seen_ids.add(item_id)
        seeded += 1
      if c_u and c_u not in seen_urls:
        seen_urls.add(c_u)
    state["seen_ids"] = list(seen_ids)
    state["seen_urls"] = list(seen_urls)
    save_state(state)
    print(
        f"Seeded {seeded} existing items into {STATE_FILE} without posting to"
        " Telegram."
    )
    return

  new_items = []
  for it in collected:
    c_u = it.get("canonical_url") or canonical_url(it.get("url", ""))
    t = clean_text(it.get("title", ""))
    item_id = make_id(f"{c_u}|{t}")
    if item_id not in seen_ids and (not c_u or c_u not in seen_urls):
      it["id"] = item_id
      it["canonical_url"] = c_u
      new_items.append(it)

  print(f"Total new RSAHC/RPMC items detected: {len(new_items)}")
  if not new_items:
    return

  posted = 0
  for it in new_items:
    if send_telegram_item(session, it):
      seen_ids.add(it["id"])
      if it.get("canonical_url"):
        seen_urls.add(it["canonical_url"])
      posted += 1
      print(f"Posted ({posted}/{len(new_items)}): {it.get('title')[:70]}")
    time.sleep(1.2)

  if posted > 0:
    state["seen_ids"] = list(seen_ids)
    state["seen_urls"] = list(seen_urls)
    save_state(state)
    print(f"Done! Sent {posted} updates to {CHANNEL_USERNAME}.")
  else:
    print("No updates were posted. Check bot admin rights in @ParamedixClasses.")


if __name__ == "__main__":
  requests.packages.urllib3.disable_warnings()
  main()
