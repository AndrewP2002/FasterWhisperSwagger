import srt
import ollama

def translate_srt(created_srt, target_language, model = "llama3.1:8b"):

    #convert the srt file into a list
    try:
        with open(created_srt,'r',encoding='utf-8') as f:
            subtitles_content = list(srt.parse(f.read()))

        #go through every sentence of the srt file and translate it
        for sub in subtitles_content:
            try:
                response = ollama.chat(model=model, messages=[
                    {
                        'role': 'system',
                        'content': f'You are a professional translator. Translate the following text into {target_language}. Output ONLY the translation, no other text.'
                    },
                    {
                        'role': 'user',
                        'content': sub.content
                    },
                ])

                #replace the original sentence with the translated one
                sub.content = response['message']['content']
            except Exception as e:

                #keeps the original line
                print(f"Error translationg line:{e}")
                continue
        file_path = created_srt[:-4]+"_translated.srt"

        #create the new srt in the video folder
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(srt.compose(subtitles_content))
    except FileNotFoundError:
        print(f"file {created_srt} not found")
    
    
       
