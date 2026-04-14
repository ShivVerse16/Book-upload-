import os
import json
import time
import requests
import base64
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# 📂 FOLDER IDs
# ==========================================
PDF_SOURCE_ID = '1sBY4jxI_ebK2S0_n4Syp5-cyWYJyPrCM'
PDF_DONE_ID   = '19N0ap1-WKWVcvhT0_lXyoYDjABcEJn1X'
IMG_SOURCE_ID = '1VOQFh2hNn947dojtUqNIYBIOVqv7g1im'
IMG_DONE_ID   = '1gi4bU5IXyOCno4fZa51PCUXCoPtsNTWG'

# 🔑 API KEY (Get it from freeimage.host/page/api)
FREEIMAGE_API_KEY = "6D3G77685655596521456654845" # <--- APNI KEY YAHAN DALO YA SECRET ME

DB_CONFIG = [
    {"url": os.environ.get('SUPABASE_URL_1'), "key": os.environ.get('SUPABASE_KEY_1')},
    {"url": os.environ.get('SUPABASE_URL_2'), "key": os.environ.get('SUPABASE_KEY_2')}
]

# Google Drive Auth
info = json.loads(os.environ['GDRIVE_CREDENTIALS'])
creds = service_account.Credentials.from_service_account_info(info)
drive_service = build('drive', 'v3', credentials=creds)

def clean_name(text):
    text = text.lower().split('.')[0].split('-')[0]
    return re.sub(r'[^a-z0-9\s]', '', text).strip()

def move_file(file_id, new_parent_id):
    try:
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        drive_service.files().update(fileId=file_id, addParents=new_parent_id, removeParents=previous_parents).execute()
        return True
    except: return False

# 🚀 NEW: Freeimage.host API Upload
def upload_image(file_id, file_name):
    try:
        print(f"DEBUG: Downloading {file_name} for upload...")
        content = drive_service.files().get_media(fileId=file_id).execute()
        base64_img = base64.b64encode(content).decode('utf-8')
        
        url = "https://freeimage.host/api/1/upload"
        params = {
            "key": os.environ.get('FREEIMAGE_API_KEY', FREEIMAGE_API_KEY),
            "source": base64_img,
            "format": "json"
        }
        
        res = requests.post(url, data=params, timeout=40)
        if res.status_code == 200:
            img_url = res.json()['image']['url']
            print(f"✅ Upload Success: {img_url}")
            return img_url
        else:
            print(f"❌ API Error: {res.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    return None

def main():
    pdfs = drive_service.files().list(q=f"'{PDF_SOURCE_ID}' in parents and trashed=false").execute().get('files', [])
    covers = drive_service.files().list(q=f"'{IMG_SOURCE_ID}' in parents and trashed=false").execute().get('files', [])
    
    print(f"Found {len(pdfs)} PDFs and {len(covers)} Covers.")

    for pdf in pdfs:
        full_pdf_name = pdf['name'].replace('.pdf', '')
        pdf_clean = clean_name(pdf['name'])
        pdf_words = set(pdf_clean.split())
        
        print(f"\n--- 📖 Task: {full_pdf_name} ---")
        img_url = "https://i.postimg.cc/fMZQLtdC/c8e0e16b-f4ef-4b55-801c-41c600377ea1.jpg" # Fallback
        matched_cover_id = None
        
        # 🖼️ SMART MATCHING
        for cv in covers:
            cv_clean = clean_name(cv['name'])
            cv_words = set(cv_clean.split())
            
            # Logic: Agar 1 bhi common word mile ya naam match ho
            if pdf_clean == cv_clean or pdf_clean in cv_clean or cv_clean in pdf_clean or (pdf_words & cv_words):
                print(f"🎯 MATCH: {cv['name']}")
                uploaded_url = upload_image(cv['id'], cv['name'])
                if uploaded_url:
                    img_url = uploaded_url
                    matched_cover_id = cv['id']
                    break
        
        if not matched_cover_id: print("⚠️ NO MATCH. Using Fallback.")
        time.sleep(3) # ⏱️ Delay 3 sec

        # 🔗 Supabase Upload
        preview_url = f"https://drive.google.com/file/d/{pdf['id']}/preview"
        payload = {"title": full_pdf_name, "description": "", "poster_url": img_url, "book_url": preview_url}
        
        for idx, db in enumerate(DB_CONFIG):
            try:
                r = requests.post(db['url'], headers={"apikey": db['key'], "Authorization": f"Bearer {db['key']}", "Content-Type": "application/json"}, json=payload)
                print(f"📡 DB {idx+1} Status: {r.status_code}")
                time.sleep(2) # ⏱️ Delay between DBs
            except: print("❌ DB Error")

        # 🧹 Cleanup
        time.sleep(3)
        if move_file(pdf['id'], PDF_DONE_ID): print("📦 PDF moved.")
        if matched_cover_id:
            if move_file(matched_cover_id, IMG_DONE_ID): print("🖼️ Cover moved.")
        
        print(f"✅ DONE: {full_pdf_name}")
        time.sleep(5) # ⏱️ Delay before next book

if __name__ == "__main__":
    main()
