# Text-to-WTFGPT

Text-to-WTFGPT is a Python-based project that generates conversational videos with text, images, and audio. It uses tools like PIL, MoviePy, and Kokoro TTS to create engaging and dynamic content.

## Features
- **Generate Images**: Converts conversation text into styled images.
- **Create Videos**: Combines generated images into a video.
- **Add Audio**: Integrates text-to-speech audio for each message.
- **Dynamic Roles**: Supports multiple user roles with customizable profiles.

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

## Usage
Run the main script to access the interactive menu:
```bash
python main.py
```

### Menu Options
1. **Generate Images**: Creates images for each conversation message.
2. **Create Video**: Combines images into a video.
3. **Final Video with Audio**: Adds text-to-speech audio to the video.

## Configuration
- **Conversation**: Edit `utils/conversation.json` to define the conversation flow.
- **Styling**: Customize `templates/config.txt` for colors, fonts, and layout.

## Contributing
We welcome contributions! Please read the [Contributing Guidelines](CONTRIBUTING.md) and adhere to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License
This project is licensed under the [MIT License](LICENSE).

## Acknowledgments
- [Pillow](https://python-pillow.org/)
- [MoviePy](https://zulko.github.io/moviepy/)
- [Kokoro TTS](https://kokoro.ai/)

Enjoy creating your WTF-worthy conversations!  