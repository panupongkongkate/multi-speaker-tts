import gradio as gr
import edge_tts
import asyncio
import os
import re

# ดึงรายการเสียงทั้งหมดและกรองเฉพาะไทยและ MultilingualNeural
async def get_supported_voices():
    voices = await edge_tts.list_voices()
    supported = {}
    
    for voice in voices:
        short_name = voice['ShortName']
        gender = voice['Gender']
        
        # กรองเฉพาะเสียงไทยและ MultilingualNeural
        if 'th-TH' in short_name or 'MultilingualNeural' in short_name:
            # ใช้ ShortName พร้อมเพศ
            clean_name = f"{short_name} ({'F' if gender == 'Female' else 'M'})"
            supported[clean_name] = short_name
    
    return supported

# ตัวอย่างนิทาน
EXAMPLE_STORIES = {
    "กบกับนกยูง": """[speaker1] กาลครั้งหนึ่งนานมาแล้ว มีกบตัวหนึ่งอาศัยอยู่ในบึงเล็กๆ
[speaker2] วันหนึ่งนกยูงสวยงามบินมาหยุดพักที่ริมบึง
[speaker1] กบมองดูนกยูงด้วยความอิจฉา แล้วพูดว่า ข้าอยากมีขนสวยเหมือนเจ้า
[speaker2] นกยูงหัวเราะแล้วตอบว่า แต่เจ้ากระโดดในน้ำได้ ส่วนข้าทำไม่ได้
[speaker1] กบจึงเข้าใจว่า ทุกคนมีความสามารถที่แตกต่างกัน""",
    
    "เต่ากับกระต่าย": """[speaker1] เต่าและกระต่ายตัดสินใจแข่งวิ่งกัน
[speaker2] กระต่ายวิ่งเร็วมาก แล้วคิดว่า ข้าวิ่งเร็วกว่าเต่ามาก จะหยุดพักสักหน่อย
[speaker1] เต่าเดินช้าๆ แต่ไม่หยุดพัก เดินต่อไปเรื่อยๆ
[speaker2] เมื่อกระต่ายตื่นขึ้นมา เต่าได้วิ่งผ่านเส้นชัยไปแล้ว
[speaker1] เต่าพูดว่า ช้าแต่มั่นคง ดีกว่าเร็วแต่ประมาท""",
    
    "มดกับตั๊กแตน": """[speaker1] ฤดูร้อนมดขยันเก็บอาหารไว้
[speaker2] ตั๊กแตนเห็นแล้วหัวเราะ ทำไมต้องเหนื่อยแบบนั้น มาเล่นกับข้าเถอะ
[speaker1] มดตอบว่า ข้าต้องเตรียมอาหารไว้สำหรับฤดูหนาว
[speaker2] เมื่อฤดูหนาวมาถึง ตั๊กแตนหิวโหย จึงมาขออาหารจากมด
[speaker1] มดให้อาหารแล้วพูดว่า การเตรียมตัวล่วงหน้าเป็นสิ่งสำคัญ""",
    
    "สุนัขกับแมว": """[speaker1] สุนัขและแมวเป็นเพื่อนรักกัน
[speaker2] วันหนึ่งแมวพูดว่า เราไปหาอาหารกันเถอะ
[speaker1] สุนัขตอบว่า ดีนะ ข้าหิวแล้ว
[speaker2] พวกเขาออกไปหาอาหารด้วยกัน และแบ่งปันทุกอย่างเท่าๆ กัน
[speaker1] สุนัขพูดว่า มิตรภาพที่แท้จริงคือการแบ่งปันและช่วยเหลือกัน"""
}

def load_example_story(story_name):
    return EXAMPLE_STORIES[story_name]

# แยกข้อความตาม speaker tags
def parse_multispeaker_text(text):
    pattern = r'\[([^\]]+)\]\s*([^\[]*?)(?=\[|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    return [(speaker.strip(), content.strip()) for speaker, content in matches if content.strip()]

# แปลงข้อความ multi-speaker แบบแยกไฟล์
async def textToSpeechMultiSeparate(text, speaker_voices, rate, volume, supported_voices):
    if not text.strip():
        raise gr.Error("กรุณาใส่ข้อความที่ต้องการแปลงเป็นเสียง")
    
    speaker_segments = parse_multispeaker_text(text)
    
    if not speaker_segments:
        raise gr.Error("ไม่พบ speaker tags ในข้อความ กรุณาใช้รูปแบบ [speaker1] ข้อความ [speaker2] ข้อความ")
    
    try:
        all_audio_data = []
        
        for i, (speaker, content) in enumerate(speaker_segments):
            if speaker not in speaker_voices:
                raise gr.Error(f"ไม่พบการตั้งค่าเสียงสำหรับ {speaker}")
            
            voice_id = supported_voices[speaker_voices[speaker]]
            rate_str = f"+{rate}%" if rate >= 0 else f"{rate}%"
            volume_str = f"+{volume}%" if volume >= 0 else f"{volume}%"
            
            communicate = edge_tts.Communicate(
                text=content,
                voice=voice_id,
                rate=rate_str,
                volume=volume_str
            )
            
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            all_audio_data.append(audio_data)
        
        combined_audio = b"".join(all_audio_data)
        
        output_file = os.path.join(os.path.dirname(__file__), "output_multispeaker.mp3")
        with open(output_file, "wb") as f:
            f.write(combined_audio)
        
        return output_file
        
    except Exception as e:
        raise gr.Error(f"เกิดข้อผิดพลาด: {str(e)}")

def clearSpeech():
    output_file = os.path.join(os.path.dirname(__file__), "output_multispeaker.mp3")
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except Exception:
            pass
    return None, None

# สร้าง UI
async def create_interface():
    # โหลดเสียงทั้งหมด
    supported_voices = await get_supported_voices()
    voice_choices = list(supported_voices.keys())
    
    print(f"พบเสียงที่รองรับ {len(supported_voices)} เสียง:")
    for name in voice_choices:
        print(f"- {name}")
    
    with gr.Blocks(css="""
        .wrap-inner.svelte-1hfxrpf {
            font-size: 12px !important;
            line-height: 1.2 !important;
        }
        .dropdown select {
            font-size: 12px !important;
        }
        """, title="Dynamic Multi-Speaker TTS") as demo:
        gr.Markdown(f"""
        # Dynamic Multi-Speaker Text-to-Speech
        รองรับการสร้างเสียงหลาย speaker ในข้อความเดียว (พบ {len(supported_voices)} เสียง)
        
        **วิธีใช้:** ใช้ [speaker1] ข้อความ [speaker2] ข้อความ เช่น:
        ```
        [speaker1] สวัสดีครับ
        [speaker2] สวัสดีค่ะ
        [speaker1] ว่ายังไงบ้าง
        ```
        """)
        
        with gr.Row():
            with gr.Column():
                text = gr.TextArea(
                    label="ข้อความ Multi-Speaker", 
                    placeholder="[speaker1] สวัสดีครับ\n[speaker2] สวัสดีค่ะ\n[speaker1] ว่ายังไงบ้าง",
                    value="[speaker1] สวัสดีครับ\n[speaker2] สวัสดีค่ะ\n[speaker1] ว่ายังไงบ้าง",
                    lines=8
                )
                
                gr.Markdown("### ตัวอย่างนิทาน")
                with gr.Row():
                    story1_btn = gr.Button("กบกับนกยูง", size="sm")
                    story2_btn = gr.Button("เต่ากับกระต่าย", size="sm")
                with gr.Row():
                    story3_btn = gr.Button("มดกับตั๊กแตน", size="sm")
                    story4_btn = gr.Button("สุนัขกับแมว", size="sm")
                
                with gr.Row():
                    rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็วเสียง")
                    volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                btn = gr.Button("สร้างเสียง Multi-Speaker", variant="primary")
                
            with gr.Column():
                gr.Markdown("### เลือกเสียงสำหรับแต่ละ Speaker")
                
                speaker1_voice = gr.Dropdown(
                    choices=voice_choices,
                    value=voice_choices[1] if len(voice_choices) > 1 else voice_choices[0],
                    label="Speaker 1",
                    interactive=True
                )
                
                speaker2_voice = gr.Dropdown(
                    choices=voice_choices,
                    value=voice_choices[0],
                    label="Speaker 2",
                    interactive=True
                )
                
                speaker3_voice = gr.Dropdown(
                    choices=voice_choices,
                    value=voice_choices[2] if len(voice_choices) > 2 else voice_choices[0],
                    label="Speaker 3 (ถ้ามี)",
                    interactive=True
                )
                
                speaker4_voice = gr.Dropdown(
                    choices=voice_choices,
                    value=voice_choices[3] if len(voice_choices) > 3 else voice_choices[0],
                    label="Speaker 4 (ถ้ามี)",
                    interactive=True
                )
                
                audio = gr.Audio(label="เสียงที่สร้าง", interactive=False)
                clear = gr.Button("ล้าง")
        
        # สร้าง state สำหรับเก็บ speaker voices
        speaker_voices_state = gr.State({
            "speaker1": voice_choices[1] if len(voice_choices) > 1 else voice_choices[0],
            "speaker2": voice_choices[0],
            "speaker3": voice_choices[2] if len(voice_choices) > 2 else voice_choices[0],
            "speaker4": voice_choices[3] if len(voice_choices) > 3 else voice_choices[0]
        })
        
        supported_voices_state = gr.State(supported_voices)
        
        # อัปเดต speaker voices เมื่อมีการเปลี่ยนแปลง
        for i, dropdown in enumerate([speaker1_voice, speaker2_voice, speaker3_voice, speaker4_voice]):
            dropdown.change(
                fn=lambda *args: {f"speaker{j+1}": voice for j, voice in enumerate(args)},
                inputs=[speaker1_voice, speaker2_voice, speaker3_voice, speaker4_voice],
                outputs=[speaker_voices_state]
            )
        
        btn.click(
            fn=textToSpeechMultiSeparate,
            inputs=[text, speaker_voices_state, rate, volume, supported_voices_state],
            outputs=[audio]
        )
        
        clear.click(
            fn=clearSpeech,
            outputs=[text, audio]
        )
        
        # Event handlers for story buttons
        story1_btn.click(fn=lambda: load_example_story("กบกับนกยูง"), outputs=[text])
        story2_btn.click(fn=lambda: load_example_story("เต่ากับกระต่าย"), outputs=[text])
        story3_btn.click(fn=lambda: load_example_story("มดกับตั๊กแตน"), outputs=[text])
        story4_btn.click(fn=lambda: load_example_story("สุนัขกับแมว"), outputs=[text])
    
    return demo

if __name__ == "__main__":
    demo = asyncio.run(create_interface())
    demo.launch()
