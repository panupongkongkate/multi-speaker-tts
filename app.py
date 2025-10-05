import gradio as gr
import edge_tts
import asyncio
import os

# รายการเสียงที่รองรับ
SUPPORTED_VOICES = {
    'Premwadee-เปรมวดี (Thai) - หญิง': 'th-TH-PremwadeeNeural',
    'Niwat-นิวัฒน์ (Thai) - ชาย': 'th-TH-NiwatNeural',
    'Ava-อวา (English/Thai) - หญิง': 'en-US-AvaMultilingualNeural',
    'Brian-ไบรอัน (English/Thai) - ชาย': 'en-US-BrianMultilingualNeural',
    'Emma-เอ็มม่า (English/Thai) - หญิง': 'en-US-EmmaMultilingualNeural',
    'Andrew-แอนดรูว์ (English/Thai) - ชาย': 'en-US-AndrewMultilingualNeural',
    'Seraphina-เซราฟินา (German/Thai) - หญิง': 'de-DE-SeraphinaMultilingualNeural',
    'Florian-ฟลอเรียน (German/Thai) - ชาย': 'de-DE-FlorianMultilingualNeural',
    'Vivienne-วีเวียน (French/Thai) - หญิง': 'fr-FR-VivienneMultilingualNeural',
    'Remy-เรมี่ (French/Thai) - ชาย': 'fr-FR-RemyMultilingualNeural'
}

# ตัวอย่างประโยคสำหรับแต่ละเสียง
EXAMPLE_SENTENCES = {
    'th-TH-PremwadeeNeural': "สวัสดีค่ะ ยินดีต้อนรับ",
    'th-TH-NiwatNeural': "สวัสดีครับ ยินดีที่ได้รู้จัก",
    'en-US-AvaMultilingualNeural': "Hello สวัสดีค่ะ Welcome ยินดีต้อนรับค่ะ",
    'en-US-BrianMultilingualNeural': "Hi สวัสดีครับ Nice to meet you ยินดีที่ได้รู้จักครับ",
    'en-US-EmmaMultilingualNeural': "Good Morning สวัสดีตอนเช้า Have a nice day ขอให้เป็นวันที่ดี",
    'en-US-AndrewMultilingualNeural': "Welcome to Thailand ยินดีต้อนรับสู่ประเทศไทย",
    'de-DE-SeraphinaMultilingualNeural': "Guten Tag สวัสดี Willkommen ยินดีต้อนรับ",
    'de-DE-FlorianMultilingualNeural': "Hello สวัสดี Danke ขอบคุณ",
    'fr-FR-VivienneMultilingualNeural': "Bonjour สวัสดี Merci beaucoup ขอบคุณมาก",
    'fr-FR-RemyMultilingualNeural': "Hello สวัสดี Au revoir ลาก่อน"
}

def update_example_text(voice):
    voice_id = SUPPORTED_VOICES[voice]
    return EXAMPLE_SENTENCES[voice_id]

# แปลงข้อความเป็นเสียง
async def textToSpeech(text, voices, rate, volume):
    if not text.strip():
        raise gr.Error("กรุณาใส่ข้อความที่ต้องการแปลงเป็นเสียง")
        
    try:
        output_file = os.path.join(os.path.dirname(__file__), "output.mp3")
        voice_id = SUPPORTED_VOICES[voices]
        
        # แปลงค่า rate และ volume
        rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
        volume_str = f"+{volume}%" if volume >= 0 else f"{volume}%"

        # สร้าง instance ของ Communicate
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate_str,
            volume=volume_str
        )

        # ลบไฟล์เก่าถ้ามี
        if os.path.exists(output_file):
            os.remove(output_file)

        # บันทึกเสียง
        await communicate.save(output_file)

        # ตรวจสอบว่าไฟล์ถูกสร้างขึ้นจริง
        if not os.path.exists(output_file):
            raise Exception("ไม่สามารถสร้างไฟล์เสียงได้")
            
        if os.path.getsize(output_file) == 0:
            raise Exception("ไฟล์เสียงมีขนาดเป็น 0")

        return output_file

    except Exception as e:
        error_msg = str(e)
        if "No audio was received" in error_msg:
            raise gr.Error("ไม่สามารถสร้างเสียงได้ กรุณาตรวจสอบข้อความและลองใหม่อีกครั้ง")
        else:
            raise gr.Error(f"เกิดข้อผิดพลาด: {error_msg}")

# ล้างผลลัพธ์การแปลง
def clearSpeech():
    output_file = os.path.join(os.path.dirname(__file__), "output.mp3")
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except Exception:
            pass
    return None, None

# สร้าง UI
with gr.Blocks(css="style.css", title="แปลงข้อความเป็นเสียงหลายภาษา") as demo:
    gr.Markdown("""
    # Microsoft Edge แปลงข้อความเป็นเสียงหลายภาษา
    รองรับภาษาไทย อังกฤษ เยอรมัน และฝรั่งเศส
    """)
    
    with gr.Row():
        with gr.Column():
            text = gr.TextArea(
                label="ข้อความ", 
                placeholder="พิมพ์ข้อความที่ต้องการแปลงเป็นเสียงที่นี่",
                elem_classes="text-area",
                value=EXAMPLE_SENTENCES['th-TH-PremwadeeNeural']  # เพิ่มค่าเริ่มต้น
            )
            btn = gr.Button("สร้าง", elem_id="submit-btn", variant="primary")
        with gr.Column():
            voices = gr.Dropdown(
                choices=list(SUPPORTED_VOICES.keys()),
                value=list(SUPPORTED_VOICES.keys())[0],
                label="เสียง",
                info="กรุณาเลือกเสียงผู้พูด",
                interactive=True
            )
            
            rate = gr.Slider(
                -100,
                100,
                step=1,
                value=0,
                label="ความเร็วเสียง",
                info="เพิ่มหรือลดความเร็วของเสียง (-100 ถึง +100)",
                interactive=True
            )
            
            volume = gr.Slider(
                -100,
                100,
                step=1,
                value=0,
                label="ระดับเสียง",
                info="เพิ่มหรือลดระดับเสียง (-100 ถึง +100)",
                interactive=True
            )
            
            audio = gr.Audio(
                label="เสียงที่สร้าง",
                interactive=False,
                elem_classes="audio"
            )
            
            clear = gr.Button("ล้าง", elem_id="clear-btn")
            
            # เพิ่มการอัปเดตตัวอย่างข้อความเมื่อเปลี่ยนเสียง
            voices.change(
                fn=update_example_text,
                inputs=[voices],
                outputs=[text]
            )
            
            btn.click(
                fn=textToSpeech,
                inputs=[text, voices, rate, volume],
                outputs=[audio]
            )
            clear.click(
                fn=clearSpeech,
                outputs=[text, audio]
            )

if __name__ == "__main__":
    demo.launch()