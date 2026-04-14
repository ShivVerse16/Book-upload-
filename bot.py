import os
import json
import time
import requests
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- FOLDER IDs (Yahan apni IDs dalo) ---
PDF_SOURCE_ID = '1sBY4jxI_ebK2S0_n4Syp5-cyWYJyPrCM' # New PDF
PDF_DONE_ID   = '19N0ap1-WKWVcvhT0_lXyoYDjABcEJn1X' # Sahitya (Done PDF)
IMG_SOURCE_ID = '1gi4bU5IXyOCno4fZa51PCUXCoPtsNTWG' # New Covers
IMG_DONE_ID   = '1gi4bU5IXyOCno4fZa51PCUXCoPtsNTWG'                     # Covers Done (New Folder ID)

# Auth Setup
try:
    info = json.loads(os.environ['GDRIVE_CREDENTIALS'])
    creds = service_account.Credentials.from_service_account_info(info)
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"Auth Error: {e}")

def move_file(file_id, new_parent_id):
    try:
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        drive_service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        return True
    except Exception as e:
        print(f"Move Error: {e}")
        return False

def get_files(folder_id):
    query = f"'{folder_id}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    return results.get('files', [])

def upload_to_imgbb(file_id):
    # Download from Drive
    content = drive_service.files().get_media(fileId=file_id).execute()
    # Upload to ImgBB
    res = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": os.environ['IMGBB_API_KEY'],
            "image": base64.b64encode(content)
        }
    )
    return res.json()['data']['url'] if res.status_code == 200 else None

def main():
    pdfs = get_files(PDF_SOURCE_ID)
    covers = get_files(IMG_SOURCE_ID)
    
    print(f"Found {len(pdfs)} PDFs to process.")

    for pdf in pdfs:
        pdf_name_clean = pdf['name'].replace('.pdf', '').split('-')[0].strip().lower()
        print(f"\nProcessing: {pdf['name']}")
        
        img_url = "https://i.postimg.cc/fMZQLtdC/c8e0e16b-f4ef-4b55-801c-41c600377ea1.jpg" # Fallback
        matched_cover_id = None
        
        # Matching Cover
        for cv in covers:
            if pdf_name_clean in cv['name'].lower():
                print(f"Matched Cover: {cv['name']}")
                url = upload_to_imgbb(cv['id'])
                if url:
                    img_url = url
                    matched_cover_id = cv['id']
                break
        
        # Supabase Upload
        db_data = {
            "title": pdf['name'].replace('.pdf', ''),
            "description": "",
            "poster_url": img_url,
            "book_url": f"https://drive.google.com/file/d/{pdf['id']}/preview"
        }
        
        # Double DB Upload
        for i in range(1, 3):
            requests.post(
                os.environ[f'SUPABASE_URL_{i}'],
                headers={"apikey": os.environ[f'SUPABASE_KEY_{i}'], "Content-Type": "application/json"},
                json=db_data
            )
        print("Data sent to Supabase.")

        # Cleanup: Move Files
        move_file(pdf['id'], PDF_DONE_ID) # Move PDF to Sahitya
        print("PDF moved to Sahitya.")
        
        if matched_cover_id:
            move_file(matched_cover_id, IMG_DONE_ID) # Move Cover to Covers Done
            print("Cover moved to Covers Done.")
        
        print(f"Success: {pdf['name']}")
        time.sleep(3) # 3 sec delay

if __name__ == "__main__":
    main()
