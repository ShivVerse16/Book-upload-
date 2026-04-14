import os
import json
import time
import requests
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# 📂 FOLDER IDs
# ==========================================
PDF_SOURCE_ID = '1sBY4jxI_ebK2S0_n4Syp5-cyWYJyPrCM' # New pdf
PDF_DONE_ID   = '19N0ap1-WKWVcvhT0_lXyoYDjABcEJn1X' # Sahitya (Done)
IMG_SOURCE_ID = '1VOQFh2hNn947dojtUqNIYBIOVqv7g1im' # New covers
IMG_DONE_ID   = '1gi4bU5IXyOCno4fZa51PCUXCoPtsNTWG' # Covers done

# API Keys from Secrets
POSTIMAGE_KEY = os.environ.get('POSTIMAGE_API_KEY') # Optional
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')
FREEIMAGE_KEY = os.environ.get('FREEIMAGE_API_KEY')

DB_CONFIG = [
    {"name": "Home", "url": os.environ.get('SUPABASE_URL_1'), "key": os.environ.get('SUPABASE_KEY_1')},
    {"name": "Daily", "url": os.environ.get('SUPABASE_URL_2'), "key": os.environ.get('SUPABASE_KEY_2')}
]

# Google Drive Auth
info = json.loads(os.environ['GDRIVE_CREDENTIALS'])
creds = service_account.Credentials.from_service_account_info(info)
drive_service = build('drive', 'v3', credentials=creds)

# 🧹 Hindi Friendly Cleaner
def get_clean_basename(filename):
    name = filename.rsplit('.', 1)[0]
    return name.strip()

# 🗑️ DELETE DAILY DB (Category 2)
def clear_daily_db():
    print("🧹 Cleaning Daily Database (DB 2)...")
    db = DB_CONFIG[1] # Daily DB
    try:
        # Supabase me saara data delete karne ke liye (id > 0 filter use karte hain)
        res = requests.delete(
            f"{db['url']}?id=gt.0", 
            headers={"apikey": db['key'], "Authorization": f"Bearer {db['key']}"}
        )
        if res.status_code in [200, 204]:
            print("✅ Daily DB cleared successfully.")
        else:
            print(f"⚠️ Daily DB clean-up failed: {res.status_code}")
    except Exception as e:
        print(f"❌ DB Clean-up Error: {e}")

# 🚀 IMAGE PRIORITY CHAIN (PostImage -> ImgBB -> FreeImage)
def upload_image_chain(content, file_name):
    # --- 1. POSTIMAGE ---
    if POSTIMAGE_KEY:
        try:
            print("Trying PostImage...")
            res = requests.post("https://postimage.org/api/2/upload", data={"key": POSTIMAGE_KEY, "image": base64.b64encode(content)}, timeout=20)
            if res.status_code == 200: return res.json()['url']
        except: print("PostImage failed.")

    # --- 2. IMGBB ---
    if IMGBB_API_KEY:
        try:
            print("Trying ImgBB...")
            res = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY, "image": base64.b64encode(content)}, timeout=20)
            if res.status_code == 200: return res.json()['data']['url']
        except: print("ImgBB failed.")

    # --- 3. FREEIMAGE.HOST ---
    if FREEIMAGE_KEY:
        try:
            print("Trying FreeImage...")
            res = requests.post("https://freeimage.host/api/1/upload", data={"key": FREEIMAGE_KEY, "source": base64.b64encode(content), "format": "json"}, timeout=20)
            if res.status_code == 200: return res.json()['image']['url']
        except: print("FreeImage failed.")

    return None

def move_file(file_id, new_parent_id):
    try:
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        drive_service.files().update(fileId=file_id, addParents=new_parent_id, removeParents=previous_parents).execute()
        return True
    except: return False

def main():
    # Pehle Daily DB saaf karein
    clear_daily_db()
    time.sleep(3)

    pdfs = drive_service.files().list(q=f"'{PDF_SOURCE_ID}' in parents and trashed=false", fields="files(id, name)").execute().get('files', [])
    covers = drive_service.files().list(q=f"'{IMG_SOURCE_ID}' in parents and trashed=false", fields="files(id, name)").execute().get('files', [])
    
    print(f"Found {len(pdfs)} PDFs.")

    for pdf in pdfs:
        full_pdf_name = pdf['name']
        pdf_base = get_clean_basename(full_pdf_name)
        print(f"\n--- 📖 Task: {full_pdf_name} ---")
        
        img_url = "https://i.postimg.cc/fMZQLtdC/c8e0e16b-f4ef-4b55-801c-41c600377ea1.jpg" # Fallback
        matched_cover_id = None
        
        # 🖼️ Matching
        for cv in covers:
            if pdf_base == get_clean_basename(cv['name']):
                print(f"🎯 Match Found: {cv['name']}")
                content = drive_service.files().get_media(fileId=cv['id']).execute()
                uploaded_url = upload_image_chain(content, cv['name'])
                if uploaded_url:
                    img_url = uploaded_url
                    matched_cover_id = cv['id']
                    break
        
        # 🔗 DB Upload
        preview_url = f"https://drive.google.com/file/d/{pdf['id']}/preview"
        payload = {"title": pdf_base, "description": "", "poster_url": img_url, "book_url": preview_url}
        
        for idx, db in enumerate(DB_CONFIG):
            try:
                r = requests.post(db['url'], headers={"apikey": db['key'], "Authorization": f"Bearer {db['key']}", "Content-Type": "application/json"}, json=payload)
                print(f"📡 {db['name']} DB Status: {r.status_code}")
                time.sleep(2)
            except: print(f"❌ {db['name']} DB Error")

        # 🧹 Cleanup
        time.sleep(3)
        move_file(pdf['id'], PDF_DONE_ID)
        if matched_cover_id:
            move_file(matched_cover_id, IMG_DONE_ID)
        
        print(f"✅ COMPLETED: {pdf_base}")
        time.sleep(5)

if __name__ == "__main__":
    main()
