import os
import shutil
import subprocess
import zipfile
import re

from enum import Enum
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from ollama_translate import translate_srt
from fastapi.responses import StreamingResponse
from io import BytesIO
from contextlib import asynccontextmanager

#function to delete all files in the upload dir after the server closes
@asynccontextmanager
async def lifespan(app:FastAPI):
    print("Server is starting up!")
    yield
    print("Server is shutting down!")
    
    #cleaning up all the leftover files
    if os.path.exists(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR): 
            file_path = os.path.join(UPLOAD_DIR, filename)
            try:
                os.unlink(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}, reason {e}")
    print("Cleanup complete!")
app = FastAPI(lifespan=lifespan, title="AI Subtitle Generator")    

#class for the dropdown menu
class LanguageOptions(str, Enum):
    english = "English"
    spanish = "Spanish"
    ukrainian = "Ukrainian"
    french = "French"
    german = "German"
    russian = "Russian"

#uploaded media directory
UPLOAD_DIR = "uploaded_media"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def run_transcribtion_processing(file_name:str, language: Optional[str], translate:bool):
    print(f"Background transcribtion started for {file_name}")
        #starting transcribtion
    script_path = os.path.abspath(__file__)
    script_directory = os.path.dirname(script_path)

    #variables to for better readability
    file_path = os.path.join(script_directory, "uploaded_media/" + file_name)
    whisper_folder = os.path.join(script_directory,"Faster-Whisper-XXL")
    whisper_file = os.path.join(whisper_folder, "faster-whisper-xxl.exe")

    #command for whisper
    command = whisper_file + " " + file_path + " --model medium --output_dir source"
    subprocess.run(command, check = True, capture_output=True, text=True)

    srt_original = file_path[:-4]+".srt"
    #ollama translation
    if translate:
        print(f"Begining translation to {language}")
        translate_srt(srt_original, language)
    print(f"Background transcribtion ended for {file_name}")

def create_zip_file(file_name, clean_name, needs_translation,):
    #variables for all the files
    base_name = os.path.splitext(clean_name)[0]
    srt_original = os.path.join(UPLOAD_DIR, f"{base_name}.srt")
    if needs_translation: 
        srt_translated = os.path.join(UPLOAD_DIR, f"{base_name}_translated.srt")
    io_buffer = BytesIO()
    with zipfile.ZipFile(io_buffer, "w") as zip_file:
        zip_file.write(srt_original, arcname=f"{file_name}.srt")
        if needs_translation: 
            zip_file.write(srt_translated, arcname=f"{file_name}_translated.srt")
    io_buffer.seek(0)
    return io_buffer

#file upload endpoint
@app.post("/upload")
async def process_media(
    #background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    #checkbox for ollama translation
    needs_translation: bool = Form(...), 
    #drop down menu with languages(optional because translation not always required)
    target_language: Optional[LanguageOptions] = Form(None) 
):   
    #if the translation box is checked
    if needs_translation and target_language is None:
        raise HTTPException(
            status_code=400, 
            detail="You must select a target language if translation is enabled."
        )
    #cleaning the file name from illegal symbols
    clean_name = re.sub(r'[^\w\d.]', '_', file.filename)
    #saving the file in the output_dir with the cleaned name
    file_path = os.path.join(UPLOAD_DIR, clean_name)
    if os.path.exists(file_path):
        return StreamingResponse(
        create_zip_file(file.filename,clean_name, needs_translation), 
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={file.filename}_subtitles.zip"}
        )  
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    #starting the translation process
    run_transcribtion_processing(clean_name, target_language.value if target_language else None, needs_translation)

    #response with the created zip file
    return StreamingResponse(
        create_zip_file(file.filename,clean_name, needs_translation), 
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={file.filename}_subtitles.zip"}
    )  