# Real-time Audio Processing with OpenAI API

This project implements a real-time audio processing system using the OpenAI API. It captures audio from your microphone, sends it to the OpenAI API, and plays back the API's audio response in real-time.

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

## Setup

1. Clone this repository to your local machine.

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory of the project.

4. Add your OpenAI API key to the `.env` file:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
   Replace `your_api_key_here` with your actual OpenAI API key.

## Usage

1. Ensure your microphone is connected and working properly.

2. Run the main script:
   ```
   python code_01.py
   ```
   or
   ```
   python code_02.py
   ```
3. Follow the prompts to select a voice for the AI assistant.

4. Speak into your microphone. The script will capture your audio, send it to the OpenAI API, and play back the response in real-time.

5. To stop the program, use the keyboard interrupt (Ctrl+C or Ctrl+Break).

## Important Notes

- Keep your `.env` file secure and do not share it publicly, as it contains your API key.
- Ensure you have sufficient API credits in your OpenAI account to use the real-time audio processing feature.
- This script uses the PyAudio library, which may require additional system-level dependencies depending on your operating system. If you encounter issues installing PyAudio, please refer to the PyAudio documentation for your specific OS.
