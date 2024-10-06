import streamlit as st
import pyaudio
import websocket
import json
import base64
import threading
import os
import time
import queue

# Configuration and constants
WEBSOCKET_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Audio handling class
class AudioHandler:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True, frames_per_buffer=1024)
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()

    def enqueue_audio(self, audio_data):
        self.audio_queue.put(audio_data)

    def play_audio(self):
        while not self.stop_event.is_set():
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                self.stream.write(audio_data)
            except queue.Empty:
                continue

    def close(self):
        self.stop_event.set()
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

# WebSocket client class
class RealtimeAPIClient:
    def __init__(self, api_key, websocket_url, audio_handler):
        self.api_key = api_key
        self.websocket_url = websocket_url
        self.audio_handler = audio_handler
        self.ws = None
        self.send_lock = threading.Lock()
        self.response_text = ""
        self.transcript_text = ""
        self.voice = "alloy"
        self.update_event = threading.Event()
        self.response_complete = threading.Event()

    def on_message(self, ws, message):
        event = json.loads(message)
        print(f"Received event: {event['type']}")
        if event['type'] == 'response.audio.delta':
            audio_bytes = base64.b64decode(event['delta'])
            self.audio_handler.enqueue_audio(audio_bytes)
        elif event['type'] == 'response.text.delta':
            self.response_text += event['delta']
            self.update_event.set()
        elif event['type'] == 'response.audio_transcript.delta':
            self.transcript_text += event.get('delta', '')
            self.update_event.set()
        elif event['type'] == 'response.done':
            print("Response completed")
            self.response_complete.set()

    def send_audio(self, audio_data):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            base64_audio = base64.b64encode(audio_data).decode('utf-8')
            event = {
                "type": "input_audio_buffer.append",
                "audio": base64_audio
            }
            with self.send_lock:
                self.ws.send(json.dumps(event))

    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.websocket_url,
            header=[f"Authorization: Bearer {self.api_key}", "OpenAI-Beta: realtime=v1"],
            on_message=self.on_message,
            on_open=self.on_open
        )
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

    def on_open(self, ws):
        print("WebSocket connection opened")
        self.send_session_update()

    def send_session_update(self):
        event = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": "請說中文",
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 200
                },
                "tools": [],
                "tool_choice": "auto",
            }
        }
        with self.send_lock:
            self.ws.send(json.dumps(event))
        print("Sent session.update event")

# Streamlit application
def main():
    st.title("OpenAI Realtime API Demo")

    if 'audio_handler' not in st.session_state:
        st.session_state.audio_handler = AudioHandler()
        audio_thread = threading.Thread(target=st.session_state.audio_handler.play_audio)
        audio_thread.daemon = True
        audio_thread.start()

    if 'client' not in st.session_state:
        st.session_state.client = RealtimeAPIClient(OPENAI_API_KEY, WEBSOCKET_URL, st.session_state.audio_handler)
        st.session_state.client.connect()

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Move the "Press & Talk" button to the bottom
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        if st.button("Press & Talk"):
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=24000, input=True, frames_per_buffer=1024)

            st.session_state.client.send_session_update()
            with st.spinner("Recording..."):
                for _ in range(100):  # Record for about 4 seconds
                    audio_data = stream.read(1024)
                    st.session_state.client.send_audio(audio_data)

            stream.stop_stream()
            stream.close()
            p.terminate()

            # Add user message to chat
            if st.session_state.client.transcript_text:
                st.session_state.messages.append({"role": "user", "content": st.session_state.client.transcript_text})
                with chat_container.chat_message("user"):
                    st.markdown(st.session_state.client.transcript_text)

            # Wait for and display AI response progressively
            with chat_container.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                while not st.session_state.client.response_complete.is_set():
                    if st.session_state.client.update_event.is_set():
                        new_content = st.session_state.client.response_text[len(full_response):]
                        full_response += new_content
                        message_placeholder.markdown(full_response + "▌")
                        st.session_state.client.update_event.clear()
                    time.sleep(0.1)
                
                # Display final message
                message_placeholder.markdown(full_response)
                
            # Add the full response to messages
            st.session_state.messages.append({"role": "assistant", "content": full_response})

            # Reset client state
            st.session_state.client.response_text = ""
            st.session_state.client.transcript_text = ""
            st.session_state.client.update_event.clear()
            st.session_state.client.response_complete.clear()

    # Display debug info (can be removed in production)
    with st.expander("Debug Info"):
        st.text(f"Response Text: {st.session_state.client.response_text}")
        st.text(f"Transcript Text: {st.session_state.client.transcript_text}")

if __name__ == "__main__":
    main()
