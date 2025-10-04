import gradio as gr
import edge_tts
import asyncio
import os
import re
from moviepy.editor import *
import numpy as np
from PIL import Image

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

# ฟังก์ชันสร้างวิดีโอจากเสียงและรูปภาพ (แบบง่าย)
async def create_video_with_images(text, speaker_data, speaker_images, supported_voices):
    if not text.strip():
        raise gr.Error("กรุณาใส่ข้อความก่อนสร้างวิดีโอ")
    
    # ตรวจสอบว่ามีไฟล์เสียงหรือไม่
    audio_file = os.path.join(os.path.dirname(__file__), "output_multispeaker.mp3")
    if not os.path.exists(audio_file):
        raise gr.Error("กรุณากด 'สร้างเสียง Multi-Speaker' ก่อนสร้างวิดีโอ")
    
    speaker_segments = parse_multispeaker_text(text)
    
    try:
        # กำหนดขนาดมาตรฐานสำหรับวิดีโอ
        video_width, video_height = 1280, 720  # HD 720p
        
        # สร้างวิดีโอคลิป
        video_clips = []
        
        for i, (speaker, content) in enumerate(speaker_segments):
            # ประมาณเวลาพูดจากจำนวนคำ (คำละ 0.5 วินาที)
            word_count = len(content.split())
            duration = max(word_count * 0.5, 2.0)  # ขั้นต่ำ 2 วินาที
            
            # ใช้รูปภาพของ speaker
            speaker_image = speaker_images.get(speaker)
            
            if speaker_image:
                # ปรับขนาดรูปภาพให้เป็นขนาดมาตรฐาน
                resized_image = speaker_image.resize((video_width, video_height), Image.Resampling.LANCZOS)
                
                # แปลง PIL เป็น numpy array
                img_array = np.array(resized_image)
                
                # สร้าง ImageClip
                img_clip = ImageClip(img_array, duration=duration)
                video_clips.append(img_clip)
            else:
                # ถ้าไม่มีรูป ใช้พื้นหลังสีดำ
                color_clip = ColorClip(size=(video_width, video_height), color=(0, 0, 0), duration=duration)
                video_clips.append(color_clip)
        
        # รวมคลิปทั้งหมด
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        # เพิ่มเสียง
        audio_clip = AudioFileClip(audio_file)
        
        # ปรับความยาววิดีโอให้ตรงกับเสียง
        if final_video.duration > audio_clip.duration:
            final_video = final_video.subclip(0, audio_clip.duration)
        elif final_video.duration < audio_clip.duration:
            # ขยายวิดีโอให้ยาวเท่าเสียง
            last_clip = video_clips[-1]
            extended_clip = last_clip.set_duration(audio_clip.duration - (final_video.duration - last_clip.duration))
            video_clips[-1] = extended_clip
            final_video = concatenate_videoclips(video_clips, method="compose")
        
        final_video = final_video.set_audio(audio_clip)
        
        # บันทึกวิดีโอ
        output_video = os.path.join(os.path.dirname(__file__), "output_video.mp4")
        final_video.write_videofile(output_video, fps=24, verbose=False, logger=None)
        
        return output_video
        
    except Exception as e:
        raise gr.Error(f"เกิดข้อผิดพลาดในการสร้างวิดีโอ: {str(e)}")

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
                video_btn = gr.Button("ดาวน์โหลดเป็นวิดีโอ (เสียง + รูป)", variant="secondary")
                
            with gr.Column():
                gr.Markdown("### การตั้งค่า Speaker (สูงสุด 10 speakers)")
                gr.Markdown("**💡 คำแนะนำ:** อัปโหลดรูปภาพขนาด 1280x720 หรือสัดส่วน 16:9 เพื่อผลลัพธ์ที่ดีที่สุด")
                
                # เริ่มต้นด้วย Speaker 1 และ 2
                with gr.Group():
                    gr.Markdown("**Speaker 1**")
                    speaker1_voice = gr.Dropdown(
                        choices=voice_choices,
                        value=voice_choices[1] if len(voice_choices) > 1 else voice_choices[0],
                        label="เสียง",
                        interactive=True
                    )
                    speaker1_image = gr.Image(label="รูปภาพ Speaker 1", type="pil", height=100)
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
                    speaker2_image = gr.Image(label="รูปภาพ Speaker 2", type="pil", height=100)
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
                    speaker3_image = gr.Image(label="รูปภาพ Speaker 3", type="pil", height=100)
                    with gr.Row():
                        speaker3_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker3_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker4_group = gr.Group(visible=False)
                with speaker4_group:
                    gr.Markdown("**Speaker 4**")
                    speaker4_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    speaker4_image = gr.Image(label="รูปภาพ Speaker 4", type="pil", height=100)
                    with gr.Row():
                        speaker4_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker4_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker5_group = gr.Group(visible=False)
                with speaker5_group:
                    gr.Markdown("**Speaker 5**")
                    speaker5_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    speaker5_image = gr.Image(label="รูปภาพ Speaker 5", type="pil", height=100)
                    with gr.Row():
                        speaker5_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker5_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker6_group = gr.Group(visible=False)
                with speaker6_group:
                    gr.Markdown("**Speaker 6**")
                    speaker6_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    speaker6_image = gr.Image(label="รูปภาพ Speaker 6", type="pil", height=100)
                    with gr.Row():
                        speaker6_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker6_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker7_group = gr.Group(visible=False)
                with speaker7_group:
                    gr.Markdown("**Speaker 7**")
                    speaker7_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    speaker7_image = gr.Image(label="รูปภาพ Speaker 7", type="pil", height=100)
                    with gr.Row():
                        speaker7_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker7_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker8_group = gr.Group(visible=False)
                with speaker8_group:
                    gr.Markdown("**Speaker 8**")
                    speaker8_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    speaker8_image = gr.Image(label="รูปภาพ Speaker 8", type="pil", height=100)
                    with gr.Row():
                        speaker8_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker8_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker9_group = gr.Group(visible=False)
                with speaker9_group:
                    gr.Markdown("**Speaker 9**")
                    speaker9_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    speaker9_image = gr.Image(label="รูปภาพ Speaker 9", type="pil", height=100)
                    with gr.Row():
                        speaker9_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker9_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                speaker10_group = gr.Group(visible=False)
                with speaker10_group:
                    gr.Markdown("**Speaker 10**")
                    speaker10_voice = gr.Dropdown(choices=voice_choices, value=voice_choices[0], label="เสียง", interactive=True)
                    speaker10_image = gr.Image(label="รูปภาพ Speaker 10", type="pil", height=100)
                    with gr.Row():
                        speaker10_rate = gr.Slider(-100, 100, step=1, value=0, label="ความเร็ว")
                        speaker10_volume = gr.Slider(-100, 100, step=1, value=0, label="ระดับเสียง")
                
                with gr.Row():
                    add_speaker_btn = gr.Button("+ เพิ่ม Speaker", variant="secondary")
                    remove_speaker_btn = gr.Button("- ลบ Speaker", variant="secondary")
                
                audio = gr.Audio(label="เสียงที่สร้าง", interactive=False)
                video_output = gr.Video(label="วิดีโอที่สร้าง", interactive=False)
                clear = gr.Button("ล้าง")
        
        # State สำหรับเก็บข้อมูล speaker
        speaker_count = gr.State(2)
        speaker_data_state = gr.State({
            "speaker1": {"voice": voice_choices[1] if len(voice_choices) > 1 else voice_choices[0], "rate": 0, "volume": 0},
            "speaker2": {"voice": voice_choices[0], "rate": 0, "volume": 0}
        })
        supported_voices_state = gr.State(supported_voices)
        
        # State สำหรับเก็บรูปภาพ
        speaker_images_state = gr.State({})
        
        # ฟังก์ชันอัปเดตรูปภาพ
        def update_speaker_images(img1, img2, img3, img4, img5, img6, img7, img8, img9, img10):
            return {
                "speaker1": img1, "speaker2": img2, "speaker3": img3, "speaker4": img4, "speaker5": img5,
                "speaker6": img6, "speaker7": img7, "speaker8": img8, "speaker9": img9, "speaker10": img10
            }
        
        # Event handlers สำหรับรูปภาพ
        all_images = [speaker1_image, speaker2_image, speaker3_image, speaker4_image, speaker5_image,
                     speaker6_image, speaker7_image, speaker8_image, speaker9_image, speaker10_image]
        
        for img in all_images:
            img.change(
                fn=update_speaker_images,
                inputs=all_images,
                outputs=[speaker_images_state]
            )
        
        video_btn.click(
            fn=create_video_with_images,
            inputs=[text, speaker_data_state, speaker_images_state, supported_voices_state],
            outputs=[video_output]
        )
        
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
