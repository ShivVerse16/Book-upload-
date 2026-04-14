import os
import json
import time
import requests
import base64
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# 📂 FOLDER IDs (Verified from your links)
# ==========================================
PDF_SOURCE_ID = '1sBY4jxI_ebK2S0_n4Syp5-cyWYJyPrCM' # 📥 New pdf
PDF_DONE_ID   = '19N0ap1-WKWVcvhT0_lXyoYDjABcEJn1X' # 📤 Sahitya (Done)
IMG_SOURCE_ID = '1VOQFh2hNn947dojtUqNIYBIOVqv7g1im' # 📥 New covers
IMG_DONE_ID   = '1gi4bU5IXyOCno4fZa51PCUXCoPtsNTWG' # 📤 Covers done

# Secrets from GitHub
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')
DB_CONFIG = [
    {"url": os.environ.get('SUPABASE_URL_1'), "key": os.environ.get('SUPABASE_KEY_1')},
    {"url": os.environ.get('SUPABASE_URL_2'), "key": os.environ.get('SUPABASE_KEY_2')}
]

# Google Drive Auth
try:
    info = json.loads(os.environ['GDRIVE_CREDENTIALS'])
    creds = service_account.Credentials.from_service_account_info(info)
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"❌ AUTH ERROR: Check your GDRIVE_CREDENTIALS Secret! {e}")

# 🧹 String Cleaner: matching me problem na aaye isliye
def clean_string(text):
    # Extension hataye, hyphen ke baad ka hataye, aur sirf letters/numbers rakhe
    name = text.lower().split('.')[0].split('-')[0]
    return re.sub(r'[^a-z0-9]', '', name).strip()

def move_file(file_id, new_parent_id):
    try:
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        drive_service.files().update(
            fileId=file_id, addParents=new_parent_id, removeParents=previous_parents, fields='id, parents'
        ).execute()
        return True
    except Exception as e:
        print(f"❌ Move Error: {e}")
        return False

def get_files(folder_id):
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, pageSize=100, fields="files(id, name)").execute()
        return results.get('files', [])
    except: return []

def upload_to_imgbb(file_id, file_name):
    try:
        print(f"DEBUG: Processing Image: {file_name}")
        content = drive_service.files().get_media(fileId=file_id).execute()
        res = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY, "image": base64.b64encode(content)},
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
    pdfs = get_files(PDF_SOURCE_ID)
    covers = get_files(IMG_SOURCE_ID)
    
    print(f"📊 Total in Folders: {len(pdfs)} PDFs | {len(covers)} Covers")

    for pdf in pdfs:
        full_pdf_name = pdf['name'].replace('.pdf', '')
        # PDF ka clean naam (e.g. 'richdad')
        pdf_clean = clean_string(pdf['name'])
        
        print(f"\n--- 📖 Task: {full_pdf_name} ---")
        print(f"Matching logic using: '{pdf_clean}'")
        
        img_url = "https://i.postimg.cc/fMZQLtdC/c8e0e16b-f4ef-4b55-801c-41c600377ea1.jpg" # Fallback
        matched_cover_id = None
        
        # 🖼️ SMART MATCHING LOOP
        for cv in covers:
            cv_clean = clean_string(cv['name'])
            # Check if PDF name is in Cover name or vice-versa
            if pdf_clean and cv_clean and (pdf_clean in cv_clean or cv_clean in pdf_clean):
                print(f"🎯 MATCH FOUND: '{cv['name']}'")
                uploaded_url = upload_to_imgbb(cv['id'], cv['name'])
                if uploaded_url:
                    img_url = uploaded_url
                    matched_cover_id = cv['id']
                    break
        
        if not matched_cover_id:
            print("⚠️ NO COVER MATCHED in Folder. Fallback used.")

        # 🔗 Supabase Upload
        preview_url = f"https://drive.google.com/file/d/{pdf['id']}/preview"
        payload = {"title": full_pdf_name, "description": "", "poster_url": img_url, "book_url": preview_url}
        
        for idx, db in enumerate(DB_CONFIG):
            try:
                if db['url'] and db['key']:
                    r = requests.post(
                        db['url'], 
                        headers={"apikey": db['key'], "Authorization": f"Bearer {db['key']}", "Content-Type": "application/json", "Prefer": "return=minimal"}, 
                        json=payload
                    )
                    print(f"📡 DB {idx+1} Status: {r.status_code}")
            except: print(f"❌ DB {idx+1} Error")

        # 🧹 Cleanup (Move Files)
        print("Wait 3s for cleanup...")
        time.sleep(3)
        
        # 1. Move PDF to Sahitya
        if move_file(pdf['id'], PDF_DONE_ID):
            print(f"📦 PDF moved to Sahitya.")
        
        # 2. Move Cover to Covers done
        if matched_cover_id:
            if move_file(matched_cover_id, IMG_DONE_ID):
                print(f"🖼️ Cover moved to Covers done.")
        
        print(f"✅ COMPLETED: {full_pdf_name}")
        time.sleep(4) # Delay before next book

if __name__ == "__main__":
    main()
