import azure.functions as func
import json
from shareplum import Site
from shareplum import Office365
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.files.file import File 

from shareplum.site import Version
import logging
import os , io , re
import requests
import numpy as np
import cv2
import spacy
import keras_ocr
import matplotlib.pyplot as plt
from PIL import Image
import fitz
from tqdm import tqdm
import environ
import assemblyai as aai
from moviepy.editor import *

env= environ.Env()  
environ.Env().read_env()

nlp_bc5cdr = spacy.load("en_ner_bc5cdr_md")
nlp_bionlp13cg = spacy.load("en_ner_bionlp13cg_md")

pipeline = keras_ocr.pipeline.Pipeline()
#.venv\Scripts\activate
#python -m venv .venv


SHAREPOINT_AUTH_URL = env('sharepoint_auth_url')
SHAREPOINT_URL_SITE = env('sharepoint_url_site')
USERNAME = env('sharepoint_email')
PASSWORD = env('sharepoint_password')
SHAREPOINT_DOC_LIBRARY = env('sharepoint_doc_library')
CED_SHAREPOINT_URL = env('sharepoint_site_name') 
TARGET_FOLDER_URL = env('target_folder_url')
aai.settings.api_key = env('aai_settings_api_key')


def download_file_from_sharepoint(file_name):  
        conn = UserCredential(USERNAME, PASSWORD)
        abs_file_url = "{sharepoint_url}/ProspectIndexing/{file_site_name}".format(
        sharepoint_url = SHAREPOINT_URL_SITE ,
        file_site_name = file_name
        )
        file_name = os.path.basename(abs_file_url)
        # Create the directory if it doesn't exist
            #os.makedirs(os.path.join(os.environ["HOME"], "downloads"), exist_ok=True)
        with open(os.path.join("downloads", file_name), "wb") as local_file:
            file = (
                File.from_url(abs_file_url)
                .with_credentials(conn)
                .download(local_file)
                .execute_query()
            )
        print(
            "'{0}' file has been downloaded into {1}".format(
                file.server_relative_path, local_file.name
            )
        )

def blackout_Image(img_path, pipeline):
    img_list = [keras_ocr.tools.read(img_path)]
    
    for i, img in tqdm(enumerate(img_list)):
        prediction_groups = pipeline.recognize([img])

        for box in prediction_groups[0]:
            text = re.sub('(\.,)', ". ", box[0])
            text = re.sub('[\d\W]', ' ', text)
            x0, y0 = box[1][0]
            x1, y1 = box[1][1]
            x2, y2 = box[1][2]
            x3, y3 = box[1][3]

            # Calculate the bounding box dimensions
            x_min, y_min = min(x0, x1), min(y0, y1)
            x_max, y_max = max(x2, x3), max(y2, y3)

            # Convert the bounding box dimensions to np.int32
            x_min, y_min, x_max, y_max = map(np.int32, [x_min, y_min, x_max, y_max])

            # Process the text with SpaCy for disease and chemical labels
            doc = nlp_bc5cdr(text)
            doc1 = nlp_bionlp13cg(text)
            if doc.ents == ():
                text = text + " "+ text
                doc = nlp_bc5cdr(text)
            if doc1.ents == ():
                text = text + " "+ text
                doc1 = nlp_bc5cdr(text)
            if any(ent.label_ in {"DISEASE", "CHEMICAL"} for ent in doc.ents):
                cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)
            if any(ent.label_ in {"ORGAN" , "ORGANISM", "TISSUE","GENE_OR_GENE_PRODUCT", "CANCER", "CELL"} for ent in doc1.ents):
                cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

        img_list[i] = img

    return img_list

def extract_sensitive_data(sentences):
    sensitive_data = set()
    for text in sentences:

        text = re.sub('[^\w\s]', ' ', text)
        text = re.sub('\d', ' ', text)

        doc = nlp_bc5cdr(" ".join(re.sub('(\.,)', ". ", word) for word in text.split()))     
        doc1 = nlp_bionlp13cg(" ".join(re.sub('(\.,)', ". ", word) for word in text.split())) 
        if not doc.ents :
            # If doc.ents is empty, process each word individually
            words = text.split()
            for word in words:
                word_doc = nlp_bc5cdr(word)
                sensitive_data.update(ent.text for ent in word_doc.ents if ent.label_ in {"DISEASE", "CHEMICAL"})
        else:
            # Process each sentence normally
            sensitive_data.update(ent.text for ent in doc.ents if ent.label_ in {"DISEASE", "CHEMICAL"})

        if not doc1.ents :
            # If doc.ents is empty, process each word individually
            words = text.split()
            for word in words:
                word_doc_bionlp13cg = nlp_bionlp13cg(word)
                sensitive_data.update(ent.text for ent in word_doc_bionlp13cg.ents if ent.label_ in {"ORGAN", "ORGANISM", "TISSUE", "GENE_OR_GENE_PRODUCT", "CANCER", "CELL"})
        else:
            # Process each sentence normally
            sensitive_data.update(ent.text for ent in doc1.ents if ent.label_ in {"ORGAN", "ORGANISM", "TISSUE", "GENE_OR_GENE_PRODUCT", "CANCER", "CELL"})
    return list(sensitive_data)

def blackout_pdf(path):
    doc = fitz.open(path)
    filename = os.path.basename(path)
    modified_filename = f"redacted_{filename}"
    modified_pdf_path = os.path.join("redacted_documents", modified_filename)

    for page_number, page in enumerate(doc, start=1):
        # Redact text
        page.wrap_contents()
        text = page.get_text("text").split('\n')
        sensitive = extract_sensitive_data(text)
        for data in sensitive:
            areas = page.search_for(data)
            [page.add_redact_annot(area, fill=(0, 0, 0)) for area in areas]
        page.apply_redactions()
        # Check for images
        images = page.get_images(full=True)
        if images:
            img_paths = []
            for img_index in range(len(images)):
                img_bytes = page.get_pixmap()
                img_path = os.path.join("redacted_documents", f"page_{page_number}_image_{img_index}.png")
                img_bytes.save(img_path)
                img_paths.append(img_path) 
           
            # Process images
            for img_path in img_paths:
                modified_images=blackout_Image(img_path , pipeline)

            # Replace images in PDF with modified ones
            for img_path, modified_img in zip(img_paths, modified_images):
                modified_img_pil = Image.fromarray(cv2.cvtColor(modified_img, cv2.COLOR_BGR2RGB))
                modified_img_bytes = io.BytesIO()
                modified_img_pil.save(modified_img_bytes, format='png')
                modified_img_bytes.seek(0)
                rect = fitz.Rect(0, 0, modified_img.shape[1], modified_img.shape[0])
                page.insert_image(rect, stream=modified_img_bytes.read())
                os.remove(img_path)
    
    doc.save(modified_pdf_path)
    doc.close()
    with open(modified_pdf_path, 'rb') as file_obj:
        file_content = file_obj.read()
    return file_content

def redact_mp4_videos(video_path , filename) :
        config = aai.TranscriptionConfig().set_redact_pii(
            policies=[
                aai.PIIRedactionPolicy.person_name,
                aai.PIIRedactionPolicy.medical_process,
                aai.PIIRedactionPolicy.medical_condition,
                aai.PIIRedactionPolicy.blood_type,
                aai.PIIRedactionPolicy.drug,
                aai.PIIRedactionPolicy.injury,
            ],
            redact_audio=True,
            substitution=aai.PIISubstitutionPolicy.hash,
        )
        transcript = aai.Transcriber().transcribe(video_path, config)
        audio_path= transcript.get_redacted_audio_url()

        print(transcript)
        print(audio_path)

        # Create instances of VideoFileClip and AudioFileClip
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)

        video_clip_with_audio = video_clip.set_audio(audio_clip)

        # Write the merged video file to a new file
        video_clip_with_audio.write_videofile(os.path.join("redacted_documents",f"redacted_{filename}"))
        with open(f"redacted_documents/redacted_{filename}", 'rb') as file_obj:
            file_content = file_obj.read()
    
        return file_content


def process_files_in_directory(directory):
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            if filename.endswith('.pdf'):
                new_file_content = blackout_pdf(filepath)
                modify_and_upload_file(filename, new_file_content)

            elif filename.endswith(('.jpg', '.jpeg', '.png', '.tif')):
                blackout_images = blackout_Image(filepath, pipeline)
                cv2.imwrite(os.path.join("redacted_documents", f"redacted_{filename}"), cv2.cvtColor(blackout_images[0], cv2.COLOR_BGR2RGB))
                with open(f"redacted_documents/redacted_{filename}", 'rb') as file_obj:
                    new_file_content = file_obj.read()
                modify_and_upload_file(filename, new_file_content)

            elif filename.endswith('.mp4'):
                new_file_content = redact_mp4_videos(filepath , filename)
                modify_and_upload_file(filename, new_file_content)

def delete_files_in_directory(directory):       
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
                os.remove(filepath) 

def _auth():
        conn = ClientContext(SHAREPOINT_URL_SITE).with_credentials(
            UserCredential(
                USERNAME,
                PASSWORD ))
        return conn

def get_content_file(file_name):
        conn = _auth()
        target_folder_url = f'/sites/ProspectDMS/ProspectIndexing/{file_name}'
        file = File.open_binary(conn, target_folder_url)
        return file.content


def modify_and_upload_file(file_name, new_file_content):

    ctx_auth = AuthenticationContext(SHAREPOINT_URL_SITE)
    if ctx_auth.acquire_token_for_user(USERNAME, PASSWORD):
        ctx = ClientContext(SHAREPOINT_URL_SITE, ctx_auth)
        target_folder = ctx.web.get_folder_by_server_relative_url(TARGET_FOLDER_URL)
        files = target_folder.files
        ctx.load(files)
        ctx.execute_query()

        existing_file = None
        for file in files:
            if file.properties["Name"] == file_name:
                existing_file = file
                break
        if existing_file is None:
            print(f"File '{file_name}' not found in the folder.")
            return False

        existing_file.save_binary(server_relative_url=existing_file.properties['ServerRelativeUrl'], context=ctx, content=new_file_content)
        ctx.execute_query()

        return True
    else:
        print(ctx_auth.get_last_error())
        return False



def modify_txt_file(file_content):
    file_content = file_content.decode('utf-8')  # Decode bytes to string
    doc = nlp_bc5cdr(file_content)
    doc1 = nlp_bionlp13cg(file_content)
    tab = []
    if not doc.ents:
        print("no entities found")
    else:
        tab.extend(ent.text for ent in doc.ents if ent.label_ in {"DISEASE", "CHEMICAL"})
        tab.extend(ent.text for ent in doc1.ents if ent.label_ in {"ORGAN", "ORGANISM", "TISSUE", "GENE_OR_GENE_PRODUCT", "CANCER", "CELL"})
    new_file_content = file_content
    for entity in tab:
        new_file_content = new_file_content.replace(entity, 'XXXX')
    file_content_bytes = new_file_content.encode('utf-8')  # Encode string to bytes
    return file_content_bytes

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    auth = Office365(SHAREPOINT_AUTH_URL, username=USERNAME, password=PASSWORD)
    site = Site(SHAREPOINT_URL_SITE, version=Version.v2016, authcookie=auth.GetCookies())
    authcookie = auth.GetCookies()

        # Verify that authentication was successful
    if authcookie:
            # Return a positive response if authentication worked
        response = {
                "status": "Authenticated",
                "username": USERNAME
            }

        # Get the document library
        libraries = site.fields
        # Get the document library
        document_library = site.List(SHAREPOINT_DOC_LIBRARY)
        documents = document_library.GetListItems()
        req_body = req.get_json()
        
        _payload = {
            "Attachments": req_body.get('Attachments'),
            "bcc": req_body.get('bcc'),
            "EmailCc": req_body.get('cc'),
            "Comments": req_body.get('comments'),
            "dossierNumber": req_body.get('dossierNumber'),
            "emailPriority": req_body.get('emailPriority'),
            "EmailSubject": req_body.get('emailSubject'),
            "EmailFrom": req_body.get('from'),
            "HasAttachments": req_body.get('hasAttachments'),
            "isEmailOutgoing": req_body.get('isEmailOutgoing'),
            "EmailMessage": req_body.get('messageBody'),
            "Id": req_body.get('postId'),
            "EmailTo": req_body.get('to')  }

        has_attachments = _payload["HasAttachments"]
        if has_attachments:
            attachments = _payload["Attachments"]
            valid_extensions = ['jpg', 'jpeg', 'png', 'tiff', 'pdf','mp4']
            txt_attachments = [a for a in attachments if a.split('.')[-1].lower() == "txt"]
            filtered_attachments = [a for a in attachments if a.split('.')[-1].lower() in valid_extensions]
            
            for doc in documents:
                file_name = doc['Name'].split('#')[-1]
                if file_name in filtered_attachments:
                    download_file_from_sharepoint(file_name) 
                elif file_name in txt_attachments:
                    file_content = get_content_file(file_name)
                    new_file_content = modify_txt_file(file_content)
                    modify_and_upload_file(file_name , new_file_content)
            if len(filtered_attachments) > 0:       
                process_files_in_directory("downloads") 
                delete_files_in_directory("redacted_documents")
                


        return func.HttpResponse(json.dumps({"status": "success !"}), mimetype="application/json")

    else:
        return func.HttpResponse(
                json.dumps({"status": "Authentication Failed"}),
                mimetype="application/json",
                status_code=401)
