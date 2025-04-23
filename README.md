# Text-to-WTFGPT

Text-to-WTFGPT is a Python-based project that generates conversational videos by combining text, images, and audio. It leverages powerful tools like PIL, MoviePy, and Kokoro TTS to create engaging, dynamic content.

## Features
- **Generate Images**: Convert conversation text into stylized images.
- **Create Videos**: Seamlessly combine generated images into a flowing video.
- **Add Audio**: Integrate text-to-speech audio for each message along with sound effects.
- **Dynamic Roles**: Support multiple user roles with customizable profiles.

## Prerequisites

Before you begin, ensure you have the following installed:

To verify your setup:
1. Check your Python version:
  ```bash
  python --version
  ```
2. Check your pip version:
  ```bash
  pip --version
  ```
3. Verify your ffmpeg installation:
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
2. Install the project dependencies:
  ```bash
  pip install -r requirements.txt
  ```
3. Ensure `ffmpeg` is installed and available on your system’s PATH:
  ```bash
  ffmpeg -version
  ```

## Usage
Run the main script to launch the interactive menu:
```bash
python main.py
```
The menu offers the following options:
1. **Generate Images**: Processes the conversation text and creates styled images based on the configured fonts, colors, and layout.
2. **Create Video**: Combines the generated images into a seamless video, displaying each image for a specified duration.
3. **Final Video with Audio**: Adds synchronized text-to-speech audio and sound effects (SFX) to the video.

**Additional Configuration:**
To customize your project setup, create the following files using the template files as guidelines:
- **Conversation**: Create a `util/conversation.json` file. Use `templates/conversation.txt` as a reference to define your conversation flow.
- **Styling**: Create a `util/config.json` file. Refer to `templates/config.txt` for styling options and configuration settings.

## Contributing
We welcome contributions! Please review our [Contributing Guidelines](CONTRIBUTING.md) and adhere to the [Code of Conduct](CODE_OF_CONDUCT.md) before submitting your pull requests.

## License
This project is licensed under the [MIT License](LICENSE).

## Acknowledgments
- [Pillow](https://pillow.readthedocs.io/)
- [MoviePy](https://zulko.github.io/moviepy/)
- [Kokoro TTS](https://github.com/hexgrad/kokoro)

Enjoy creating your WTF-worthy conversations!