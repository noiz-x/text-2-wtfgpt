# Text-to-WTFGPT

Text-to-WTFGPT is a Python-based project that generates conversational videos with text, images, and audio. It uses tools like PIL, MoviePy, and Kokoro TTS to create engaging and dynamic content.

## Features
- **Generate Images**: Converts conversation text into styled images.
- **Create Videos**: Combines generated images into a video.
- **Add Audio**: Integrates text-to-speech audio for each message.
- **Dynamic Roles**: Supports multiple user roles with customizable profiles.
## Prerequisites

Before you begin, ensure you have the following installed:

To verify your setup:

1. Check Python version:
  ```bash
  python --version
  ```
2. Check pip version:
  ```bash
  pip --version
  ```
3. Verify ffmpeg installation:
  ```bash
  ffmpeg -version
  ```
- Python 3.12
- pip (Python package manager)
- ffmpeg (for video processing)

## Installation
1. Clone the repository:
  ```bash
  git clone https://github.com/noiz-x/text-2-wtfgpt.git
  cd text-2-wtfgpt
  ```
2. Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
3. Ensure `ffmpeg` is installed and accessible from the command line:
  ```bash
  ffmpeg -version
  ```

## Usage
Run the main script to access the interactive menu:
```bash
python main.py
```

1. **Generate Images**: Processes the conversation text and generates styled images for each message. The images are created based on the configuration settings, including fonts, colors, and layout.

2. **Create Video**: Combines the generated images into a seamless video, ensuring the conversation flows naturally with each image displayed for the specified duration.

3. **Final Video with Audio**: Adds text-to-speech audio to the video, synchronizing the audio with the corresponding messages and integrating sound effects (SFX) where specified.
- **Conversation**: Edit `utils/conversation.json` to define the conversation flow.
- **Styling**: Customize `templates/config.txt` for colors, fonts, and layout.

## Contributing
We welcome contributions! Please read the [Contributing Guidelines](CONTRIBUTING.md) and adhere to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License
This project is licensed under the [MIT License](LICENSE).

## Acknowledgments
- [Pillow](https://pillow.readthedocs.io/)
- [MoviePy](https://zulko.github.io/moviepy/)
- [Kokoro TTS](https://github.com/hexgrad/kokoro)

Enjoy creating your WTF-worthy conversations!  