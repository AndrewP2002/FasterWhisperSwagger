import os
import shutil
import subprocess
import zipfile

from enum import Enum
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from ollama_translate import translate_srt
from fastapi.responses import StreamingResponse
from io import BytesIO

app = FastAPI(title="AI Subtitle Generator")

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
    file_path = os.path.join(UPLOAD_DIR, file_name)
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

#file upload endpoint
@app.post("/upload")
async def process_media(
    background_tasks: BackgroundTasks,
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
    
    #saving the file in the output_dir
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    #processing file
    response_msg = f"File {file.filename} saved. and starting transcription/translation"

    #background task for the transcription/translation
    background_tasks.add_task(
        run_transcribtion_processing,
        file.filename,
        target_language.value if target_language else None,
        needs_translation
    )

    return {
        "filename": file.filename,
        "translation_active": needs_translation,
        "language": target_language if needs_translation else "None",
        "status": response_msg
    }

#function to delete files
def remove_file(path: str):
    if os.path.exists(path):
        os.remove(path)

#downloading subtitles
@app.get("/download-subtitles/{filename}")
async def download_subtitles(
    filename: str,
    background_tasks: BackgroundTasks
    ):

    #variables for all the files
    base_name = os.path.splitext(filename)[0]
    srt_original = os.path.join(UPLOAD_DIR, f"{base_name}.srt")
    srt_translated = os.path.join(UPLOAD_DIR, f"{base_name}_translated.srt")
    print(f"{base_name} {srt_original} {srt_translated}")

    #check whether files exist
    if not os.path.exists(srt_original) or not os.path.exists(srt_translated):
        raise HTTPException(
            status_code=404, 
            detail="Subtitles not found. They might still be processing."
        )

    #create an inmemory zip file to hold both srts
    io_buffer = BytesIO()
    with zipfile.ZipFile(io_buffer, "w") as zip_file:
        zip_file.write(srt_original, arcname=f"{base_name}_original.srt")
        zip_file.write(srt_translated, arcname=f"{base_name}_translated.srt")
    io_buffer.seek(0)

    #create background tasks to dele the files after they have been downloaded
    background_tasks.add_task(remove_file, os.path.join(UPLOAD_DIR, filename))
    background_tasks.add_task(remove_file, srt_original)
    background_tasks.add_task(remove_file, srt_translated)
    
    return StreamingResponse(
        io_buffer, 
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={base_name}_subtitles.zip"}
    )