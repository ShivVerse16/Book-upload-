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
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')
DB_CONFIG = [
    {"url": os.environ.get('SUPABASE_URL_1'), "key": os.environ.get('SUPABASE_KEY_1')},
    {"url": os.environ.get('SUPABASE_URL_2'), "key": os.environ.get('SUPABASE_KEY_2')}
]

# Google Drive Auth
info = json.loads(os.environ['GDRIVE_CREDENTIALS'])
creds = service_account.Credentials.from_service_account_info(info)
drive_service = build('drive', 'v3', credentials=creds)

# 🧹 Hindi Friendly Cleaner: Sirf extension hatayega aur extra space saaf karega
def get_clean_basename(filename):
    # Extension hataye (.pdf, .jpg, .png etc)
    name = filename.rsplit('.', 1)[0]
    return name.strip()

def move_file(file_id, new_parent_id):
    try:
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        drive_service.files().update(fileId=file_id, addParents=new_parent_id, removeParents=previous_parents).execute()
        return True
    except Exception as e:
        print(f"Move Error: {e}")
        return False

def upload_to_imgbb(file_id, file_name):
    try:
        print(f"DEBUG: Downloading {file_name} for ImgBB...")
        content = drive_service.files().get_media(fileId=file_id).execute()
        
        res = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": IMGBB_API_KEY,
                "image": base64.b64encode(content)
            },
            timeout=30
        )
        if res.status_code == 200:
            url = res.json()['data']['url']
            print(f"✅ ImgBB Success: {url}")
            return url
        else:
            print(f"❌ ImgBB Error: {res.text}")
    except Exception as e:
        print(f"❌ Upload Exception: {e}")
    return None

def main():
    # Get files from folders
    pdfs = drive_service.files().list(q=f"'{PDF_SOURCE_ID}' in parents and trashed=false", fields="files(id, name)").execute().get('files', [])
    covers = drive_service.files().list(q=f"'{IMG_SOURCE_ID}' in parents and trashed=false", fields="files(id, name)").execute().get('files', [])
    
    print(f"Found {len(pdfs)} PDFs and {len(covers)} Covers.")

    for pdf in pdfs:
        full_pdf_name = pdf['name']
        pdf_base = get_clean_basename(full_pdf_name)
        
        print(f"\n--- 📖 Task: {full_pdf_name} ---")
        print(f"Looking for cover matching: '{pdf_base}'")
        
        img_url = "https://i.postimg.cc/fMZQLtdC/c8e0e16b-f4ef-4b55-801c-41c600377ea1.jpg" # Fallback
        matched_cover_id = None
        
        # 🖼️ SMART HINDI MATCHING
        for cv in covers:
            cv_base = get_clean_basename(cv['name'])
            
            # Agar PDF ka naam aur Image ka naam bilkul same hai
            if pdf_base == cv_base:
                print(f"🎯 EXACT MATCH FOUND: {cv['name']}")
                uploaded_url = upload_to_imgbb(cv['id'], cv['name'])
                if uploaded_url:
                    img_url = uploaded_url
                    matched_cover_id = cv['id']
                    break
        
        if not matched_cover_id:
            print(f"⚠️ NO MATCH for '{pdf_base}'. Using Fallback.")

        time.sleep(3) # ⏱️ Delay 3 sec before DB

        # 🔗 Supabase DB Upload
        preview_url = f"https://drive.google.com/file/d/{pdf['id']}/preview"
        payload = {"title": pdf_base, "description": "", "poster_url": img_url, "book_url": preview_url}
        
        for idx, db in enumerate(DB_CONFIG):
            try:
                if db['url'] and db['key']:
                    r = requests.post(db['url'], headers={"apikey": db['key'], "Authorization": f"Bearer {db['key']}", "Content-Type": "application/json"}, json=payload)
                    print(f"📡 DB {idx+1} Status: {r.status_code}")
                    time.sleep(2) # ⏱️ Micro delay
            except: print("❌ DB Error")

        # 🧹 Cleanup (Move to Done folders)
        time.sleep(3) # ⏱️ Delay before moving
        if move_file(pdf['id'], PDF_DONE_ID):
            print(f"📦 PDF '{full_pdf_name}' moved to Sahitya.")
        
        if matched_cover_id:
            if move_file(matched_cover_id, IMG_DONE_ID):
                print(f"🖼️ Cover moved to Covers done.")
        
        print(f"✅ COMPLETED: {pdf_base}")
        time.sleep(5) # ⏱️ Final Delay before next book

if __name__ == "__main__":
    main()
