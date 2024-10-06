# modiflied code of https://github.com/personabb/OpenAI_RealtimeAPI_Python_SampleCode (blog: https://zenn.dev/asap/articles/4368fd306b592a )

import asyncio
import websockets
import pyaudio
import numpy as np
import base64
import json
import wave
import io
import os

API_KEY = os.environ.get('OPENAI_API_KEY')

# WebSocket URL 和標頭資訊
WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
HEADERS = {
    "Authorization": "Bearer " + API_KEY, 
    "OpenAI-Beta": "realtime=v1"
}

# 將音訊轉換為 PCM16 格式的函數
def base64_to_pcm16(base64_audio):
    audio_data = base64.b64decode(base64_audio)
    return audio_data

# 發送音訊的非同步函數
async def send_audio(websocket, stream, CHUNK):
    def read_audio_block():
        """同步讀取音訊資料的函數"""
        try:
            return stream.read(CHUNK, exception_on_overflow=False)
        except Exception as e:
            print(f"音訊讀取錯誤：{e}")
            return None

    print("正在從麥克風獲取音訊並發送...")
    while True:
        # 從麥克風獲取音訊
        audio_data = await asyncio.get_event_loop().run_in_executor(None, read_audio_block)
        if audio_data is None:
                continue  # 如果讀取失敗則跳過

        # 將 PCM16 資料編碼為 Base64
        base64_audio = base64.b64encode(audio_data).decode("utf-8")

        audio_event = {
            "type": "input_audio_buffer.append",
            "audio": base64_audio
        }

        # 通過 WebSocket 發送音訊資料
        await websocket.send(json.dumps(audio_event))

        await asyncio.sleep(0)

# 從伺服器接收音訊並播放的非同步函數
async def receive_audio(websocket, output_stream):
    print("正在接收並播放來自伺服器的音訊...")
    print("助理：", end="", flush=True)
    loop = asyncio.get_event_loop()
    while True:
        # 接收來自伺服器的回應
        response = await websocket.recv()
        response_data = json.loads(response)

        # 即時顯示來自伺服器的回應
        if "type" in response_data and response_data["type"] == "response.audio_transcript.delta":
            print(response_data["delta"], end="", flush=True)
        # 獲取伺服器回應完成的訊息
        elif "type" in response_data and response_data["type"] == "response.audio_transcript.done":
            print("\n助理：", end="", flush=True)
        # 輸出使用者發言的文字轉錄
        elif "type" in response_data and response_data["type"] == "conversation.item.input_audio_transcription.completed":
            print("\n↪︎使用者訊息：", response_data["transcript"])
        # 獲取速率限制資訊
        elif "type" in response_data and response_data["type"] == "rate_limits.updated":
            if response_data["rate_limits"][0]["remaining"] == 0:
                print(f"速率限制：剩餘 {response_data['rate_limits'][0]['remaining']} 個請求。")

        # 檢查伺服器的回應中是否包含音訊資料
        if "delta" in response_data:
            if response_data["type"] == "response.audio.delta":
                base64_audio_response = response_data["delta"]
                if base64_audio_response:
                    pcm16_audio = base64_to_pcm16(base64_audio_response)
                    # 如果有音訊資料，則從輸出流播放
                    await loop.run_in_executor(None, output_stream.write, pcm16_audio)

# 從麥克風獲取音訊並通過 WebSocket 發送，同時播放來自伺服器的音訊回應的非同步函數
async def stream_audio_and_receive_response():
    # 讓使用者選擇聲音
    print("請選擇助理的聲音：")
    print("1. alloy")
    print("2. echo")
    print("3. shimmer")
    
    while True:
        choice = input("請輸入你的選擇（1、2 或 3）：")
        if choice in ['1', '2', '3']:
            voice_options = ['alloy', 'echo', 'shimmer']
            selected_voice = voice_options[int(choice) - 1]
            break
        else:
            print("無效的選擇，請重新輸入。")

    # 連接到 WebSocket
    async with websockets.connect(WS_URL, extra_headers=HEADERS) as websocket:
        print("已連接到 WebSocket。")

        # 初始請求（模態設置）
        init_request = {
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"],
                "instructions": "用台灣繁體中文回應",
                "voice": selected_voice
            }
        }

        await websocket.send(json.dumps(init_request))

        # 如果要啟用使用者發言的文字識別，需要以下設置
        update_request = {
            "type": "session.update",
            "session": {
                "input_audio_transcription":{
                    "model": "whisper-1"
                }
            }
        }
        await websocket.send(json.dumps(update_request))
        
        print(f"已發送初始請求，選擇的聲音是：{selected_voice}")
        
        # PyAudio 設置
        CHUNK = 2048          # 從麥克風輸入的資料塊大小
        FORMAT = pyaudio.paInt16  # PCM16 格式
        CHANNELS = 1          # 單聲道
        RATE = 24000          # 取樣率（24kHz）

        # PyAudio 實例
        p = pyaudio.PyAudio()

        # 初始化麥克風串流
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

        # 初始化用於播放伺服器回應音訊的串流
        output_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

        print("開始麥克風輸入和伺服器音訊播放...")

        try:
            # 非同步並行執行音訊發送任務和音訊接收任務
            send_task = asyncio.create_task(send_audio(websocket, stream, CHUNK))
            receive_task = asyncio.create_task(receive_audio(websocket, output_stream))

            # 等待任務完成
            await asyncio.gather(send_task, receive_task)

        except KeyboardInterrupt:
            # 鍵盤中斷時結束
            print("正在結束...")
        finally:
            # 關閉串流
            if stream.is_active():
                stream.stop_stream()
            stream.close()
            output_stream.stop_stream()
            output_stream.close()
            p.terminate()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(stream_audio_and_receive_response())
