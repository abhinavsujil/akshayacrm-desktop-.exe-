import pytesseract
import pygetwindow as gw
import pyautogui
import time
import re
from supabase_utils import supabase_post  # Your existing module

# Path to Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- Capture text from active browser window ---
def capture_active_window_text():
    try:
        active_window = gw.getActiveWindow()
        if not active_window:
            print("❌ No active window detected.")
            return None, None

        title = active_window.title
        print(f"\n🖥️ Active window title: {title}")

        bbox = (active_window.left, active_window.top, active_window.width, active_window.height)
        screenshot = pyautogui.screenshot(region=bbox)

        text = pytesseract.image_to_string(screenshot)
        print("📄 Extracted text:\n", text)

        return title, text
    except Exception as e:
        print("❌ Error during capture:", e)
        return None, None

# --- Filter only valid service completion pages ---
def is_valid_service_completion(text):
    text = text.lower()
    trigger_keywords = [
        "passport seva", "application submitted", "acknowledgement",
        "arn number", "application reference", "service type",
        "submitted successfully", "document advisor"
    ]
    match_count = sum([1 for word in trigger_keywords if word in text])
    return match_count >= 2

# --- Extract structured fields ---
def extract_fields(text):
    name = "Unknown"
    app_id = "Unknown"
    service = "Unknown"

    # Common OCR patterns
    name_patterns = [
        r"(?i)Given Name[:\-]?\s*([A-Z\s]+)",
        r"(?i)Name[:\-]?\s*([A-Z\s]+)",
        r"(?i)Applicant Name[:\-]?\s*([A-Z\s]+)"
    ]
    id_patterns = [
        r"(?i)(Application ID|ARN Number|Reference Number|Request ID)[:\-]?\s*([A-Z0-9\-]+)"
    ]
    service_patterns = [
        r"(?i)Service Type[:\-]?\s*([A-Za-z\s]+)",
        r"(?i)Service[:\-]?\s*([A-Za-z\s]+)"
    ]

    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            break

    for pattern in id_patterns:
        match = re.search(pattern, text)
        if match:
            app_id = match.group(2).strip()
            break

    for pattern in service_patterns:
        match = re.search(pattern, text)
        if match:
            service = match.group(1).strip()
            break

    return name, app_id, service

# --- Extract URL using OCR (temporary) ---
def extract_url(text):
    match = re.search(r"(https?://[^\s]+)", text)
    if match:
        return match.group(1)
    else:
        match = re.search(r"([a-z0-9\-]+\.gov\.in/[^\s]+)", text, re.IGNORECASE)
        if match:
            return "https://" + match.group(1)
    return "UNKNOWN"

# --- Push to Supabase ---
def log_to_supabase(window_title, name, app_id, service, url):
    data = {
        "browser_title": window_title,
        "customer_name": name,
        "application_id": app_id,
        "service": service,
        "url": url
    }
    print(f"[POST] Table: auto_logs\nData: {data}")
    response = supabase_post("auto_logs", data)
    if response.status_code == 201:
        print("✅ Logged to Supabase successfully.")
    else:
        print("❌ Failed to log:", response.text)

# --- Main continuous background loop ---
if __name__ == "__main__":
    print("@ Starting continuous auto logging... Press Ctrl+C to stop.\n")
    last_logged_app_id = ""

    try:
        while True:
            title, extracted_text = capture_active_window_text()
            if extracted_text:
                if is_valid_service_completion(extracted_text):
                    name, app_id, service = extract_fields(extracted_text)
                    url = extract_url(extracted_text)

                    if app_id != last_logged_app_id:
                        log_to_supabase(title, name, app_id, service, url)
                        last_logged_app_id = app_id
                    else:
                        print("⚠️ Duplicate application ID — skipping log.")
                else:
                    print("⚠️ Not a valid service page — skipping log.")
            else:
                print("❌ No text extracted.")

            time.sleep(20)  # Run every 20 seconds
    except KeyboardInterrupt:
        print("\n🛑 Auto logger stopped by user.")
