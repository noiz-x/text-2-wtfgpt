# 🔧 Optimized TODO List for Discord-Style Chat Video Generator

---

## 1. Layout, Interactions & Animations

### UI Components
- [ ] Integrate a top channel header (e.g. `#general`) directly in `generate_message_block()`.
- [ ] Implement an optional sidebar showing user avatars or text channels.
- [ ] Simulate a chat input box at the bottom with a blinking caret (`|`).

### Unified Animation Module
- [ ] Create a shared utility to handle animations, including:
  - Typing indicator (“Bingus is typing…”) 3-frame animation in `iter_message_blocks()`.
  - Reaction pop-in scale effects.
  - Spoiler reveal transitions (mask to text).
  - Optional flash transition for gray “(edited)” labels.

### Thread Management & Markdown Enhancements
- [ ] Detect replies using a `"reply_to"` field, prepend headers (e.g. “Replying to @Bingus”), and apply indentation.
- [ ] Enhance `parse_markdown()` to support:
  - Blockquotes (`> text`)
  - Lists (`- item`)
  - Checkboxes (`- [x]`)
  - Syntax-highlighted code blocks (triple-backtick ```js)

---

## 2. User Presence, Avatars & Multimedia

### Profile & Status Indicators
- [ ] Add presence dots (green/yellow/red) on avatars in `generate_avatar()`.
- [ ] Overlay Nitro/role badges alongside avatars and display role tags like “Mod”, “Admin”, “Bot” in `generate_message_block()`.

### Voice & Media Simulation
- [ ] Display notifications such as “Bingus joined Voice Channel” in `iter_system_images()`.
- [ ] Add a dynamic mic icon that pulses in sync with TTS (`sfx.py`, using `tts_clip`).
- [ ] Render a floating voice panel UI with multiple avatars and mute/unmute icons.
- [ ] Enhance `draw_link_preview()` to display a title, description, and thumbnail (mocked).
- [ ] Support image/file attachments in messages (e.g. “bingus.png”) and in-message YouTube embeds (thumbnail + play button).
- [ ] Build poll UI cards with a poll question, emoji options, and percent bars.

---

## 3. System Feedback, Themes & Commands

### System Notifications & Moderation
- [ ] Simulate mod actions with system banners (e.g. “@User muted for 10 mins”, “NSFW filtered”).
- [ ] Implement pinned message bars and trigger entry/leave sounds via `sfx_events` in `sfx.py`.

### Themable UI & Enhanced Markdown
- [ ] Enable theme switching in `config.json` based on series tag (e.g. dark mode, light mode, 2015 retro, glitch).
- [ ] Apply theme overrides in `merge_config()` and through dynamic UI styling.
- [ ] Render slash commands (e.g. `/ping`, `/ban Bingus`) in a monospaced gray font and update `parse_markdown()` to color inline tags (`@username`, `#channel`).

---

## 4. Advanced Features & Configurations

### Context-Aware Playback & JSON Extensions
- [ ] Align TTS pacing in `sfx.py` with the unified animation transitions.
- [ ] Add timed reaction sounds triggered by specific emojis (e.g. 🥁 for drum sounds).
- [ ] Expand conversation JSON support by including keys for `reply_to`, `attachments`, `embeds`, `poll`, `status`, and `theme`.
- [ ] Auto-select UI and text effects (e.g. glitch text for “Reality Breaks” mode) based on the selected series.

