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
async def textToSpeechMultiSeparate(text, speaker_data, supported_voices):
    if not text.strip():
        raise gr.Error("กรุณาใส่ข้อความที่ต้องการแปลงเป็นเสียง")
    
    speaker_segments = parse_multispeaker_text(text)
    
    if not speaker_segments:
        raise gr.Error("ไม่พบ speaker tags ในข้อความ กรุณาใช้รูปแบบ [speaker1] ข้อความ [speaker2] ข้อความ")
    
    # ตรวจสอบว่ามี speaker เพียงพอหรือไม่
    required_speakers = set(speaker for speaker, _ in speaker_segments)
    available_speakers = set(speaker_data.keys())
    missing_speakers = required_speakers - available_speakers
    
    if missing_speakers:
        missing_list = ", ".join(sorted(missing_speakers))
        raise gr.Error(f"ไม่พบการตั้งค่าสำหรับ {missing_list} กรุณาเพิ่ม speaker หรือแก้ไขข้อความ")
    
    # ตรวจสอบว่า speaker ที่ใช้มีการตั้งค่าครบถ้วน
    for speaker in required_speakers:
        if not speaker_data[speaker].get('voice'):
            raise gr.Error(f"{speaker} ยังไม่ได้เลือกเสียง กรุณาตั้งค่าให้ครบถ้วน")
    
    try:
        all_audio_data = []
        
        for i, (speaker, content) in enumerate(speaker_segments):
            settings = speaker_data[speaker]
            voice_id = supported_voices[settings['voice']]
            
            rate_str = f"+{settings['rate']}%" if settings['rate'] >= 0 else f"{settings['rate']}%"
            volume_str = f"+{settings['volume']}%" if settings['volume'] >= 0 else f"{settings['volume']}%"
            
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
                
                btn = gr.Button("สร้างเสียง Multi-Speaker", variant="primary")
                
            with gr.Column():
                gr.Markdown("### การตั้งค่า Speaker (สูงสุด 10 speakers)")
                
                # เริ่มต้นด้วย Speaker 1 และ 2
                with gr.Group():
                    gr.Markdown("**Speaker 1**")
                    speaker1_voice = gr.Dropdown(
                        choices=voice_choices,
                        value=voice_choices[1] if len(voice_choices) > 1 else voice_choices[0],
                        label="เสียง",
                        interactive=True
                    )
                    with gr.Row():
                        speaker1_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker1_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                with gr.Group():
                    gr.Markdown("**Speaker 2**")
                    speaker2_voice = gr.Dropdown(
                        choices=voice_choices,
                        value=voice_choices[0],
                        label="เสียง",
                        interactive=True
                    )
                    with gr.Row():
                        speaker2_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker2_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                # Dynamic speakers container
                dynamic_speakers = gr.Column()
                
                # Hidden speakers (จะแสดงเมื่อกดเพิ่ม)
                speaker3_group = gr.Group(visible=False)
                with speaker3_group:
                    gr.Markdown("**Speaker 3**")
                    speaker3_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker3_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker3_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker4_group = gr.Group(visible=False)
                with speaker4_group:
                    gr.Markdown("**Speaker 4**")
                    speaker4_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker4_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker4_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker5_group = gr.Group(visible=False)
                with speaker5_group:
                    gr.Markdown("**Speaker 5**")
                    speaker5_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker5_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker5_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker6_group = gr.Group(visible=False)
                with speaker6_group:
                    gr.Markdown("**Speaker 6**")
                    speaker6_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker6_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker6_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker7_group = gr.Group(visible=False)
                with speaker7_group:
                    gr.Markdown("**Speaker 7**")
                    speaker7_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker7_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker7_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker8_group = gr.Group(visible=False)
                with speaker8_group:
                    gr.Markdown("**Speaker 8**")
                    speaker8_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker8_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker8_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker9_group = gr.Group(visible=False)
                with speaker9_group:
                    gr.Markdown("**Speaker 9**")
                    speaker9_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker9_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker9_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker10_group = gr.Group(visible=False)
                with speaker10_group:
                    gr.Markdown("**Speaker 10**")
                    speaker10_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    with gr.Row():
                        speaker10_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker10_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                with gr.Row():
                    add_speaker_btn = gr.Button("+ เพิ่ม Speaker", variant="secondary")
                    remove_speaker_btn = gr.Button("- ลบ Speaker", variant="secondary")
                
                audio = gr.Audio(label="เสียงที่สร้าง", interactive=False)
                clear = gr.Button("ล้าง")
        
        # State สำหรับเก็บข้อมูล speaker
        speaker_count = gr.State(2)
        speaker_data_state = gr.State({
            "speaker1": {"voice": voice_choices[1] if len(voice_choices) > 1 else voice_choices[0], "rate": 0, "volume": 0},
            "speaker2": {"voice": voice_choices[0], "rate": 0, "volume": 0}
        })
        supported_voices_state = gr.State(supported_voices)
        
        # ฟังก์ชันอัปเดตข้อมูล speaker
        def update_speaker_data(s1_voice, s1_rate, s1_vol, s2_voice, s2_rate, s2_vol):
            return {
                "speaker1": {"voice": s1_voice, "rate": s1_rate, "volume": s1_vol},
                "speaker2": {"voice": s2_voice, "rate": s2_rate, "volume": s2_vol}
            }
        
        # ฟังก์ชันอัปเดตข้อมูล speaker แบบ dynamic (10 speakers)
        def update_all_speakers(*args):
            count = args[-1]  # ตัวสุดท้ายคือ count
            voices_rates_volumes = args[:-1]  # ที่เหลือคือ voice, rate, volume
            
            data = {}
            for i in range(min(count, 10)):
                speaker_key = f"speaker{i+1}"
                idx = i * 3
                data[speaker_key] = {
                    "voice": voices_rates_volumes[idx],
                    "rate": voices_rates_volumes[idx + 1], 
                    "volume": voices_rates_volumes[idx + 2]
                }
            return data
        
        # รายการ speaker groups
        speaker_groups = [None, None, speaker3_group, speaker4_group, speaker5_group, 
                         speaker6_group, speaker7_group, speaker8_group, speaker9_group, speaker10_group]
        
        # ฟังก์ชันเพิ่ม speaker
        def add_speaker_real(current_count):
            if current_count < 10:
                new_count = current_count + 1
                updates = []
                for i in range(2, 10):  # speaker3 ถึง speaker10
                    if i == new_count - 1:
                        updates.append(gr.update(visible=True))
                    else:
                        updates.append(gr.update())
                return [new_count] + updates
            else:
                return [current_count] + [gr.update() for _ in range(8)]
        
        # ฟังก์ชันลบ speaker  
        def remove_speaker_real(current_count):
            if current_count > 2:
                new_count = current_count - 1
                updates = []
                for i in range(2, 10):  # speaker3 ถึง speaker10
                    if i == current_count - 1:
                        updates.append(gr.update(visible=False))
                    else:
                        updates.append(gr.update())
                return [new_count] + updates
            else:
                return [current_count] + [gr.update() for _ in range(8)]
        
        # Event handlers สำหรับ speaker controls (ทุกตัว)
        all_controls = [
            speaker1_voice, speaker1_rate, speaker1_volume, 
            speaker2_voice, speaker2_rate, speaker2_volume,
            speaker3_voice, speaker3_rate, speaker3_volume, 
            speaker4_voice, speaker4_rate, speaker4_volume,
            speaker5_voice, speaker5_rate, speaker5_volume, 
            speaker6_voice, speaker6_rate, speaker6_volume,
            speaker7_voice, speaker7_rate, speaker7_volume, 
            speaker8_voice, speaker8_rate, speaker8_volume,
            speaker9_voice, speaker9_rate, speaker9_volume, 
            speaker10_voice, speaker10_rate, speaker10_volume
        ]
        
        for control in all_controls:
            control.change(
                fn=update_all_speakers,
                inputs=all_controls + [speaker_count],
                outputs=[speaker_data_state]
            )
        
        # Event handlers สำหรับปุ่มเพิ่ม/ลบ
        add_speaker_btn.click(
            fn=add_speaker_real,
            inputs=[speaker_count],
            outputs=[speaker_count] + [speaker3_group, speaker4_group, speaker5_group, 
                    speaker6_group, speaker7_group, speaker8_group, speaker9_group, speaker10_group]
        )
        
        remove_speaker_btn.click(
            fn=remove_speaker_real,
            inputs=[speaker_count],
            outputs=[speaker_count] + [speaker3_group, speaker4_group, speaker5_group, 
                    speaker6_group, speaker7_group, speaker8_group, speaker9_group, speaker10_group]
        )
        
        btn.click(
            fn=textToSpeechMultiSeparate,
            inputs=[text, speaker_data_state, supported_voices_state],
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
