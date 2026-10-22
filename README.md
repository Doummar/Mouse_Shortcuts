# Mouse Buttons as Review Shortcuts

Use your mouse as a configurable shortcut controller for Anki reviews.

**Mouse Buttons as Review Shortcuts** lets you assign review actions to mouse buttons, scroll-wheel movements, and long presses. Answer cards, reveal answers, undo a review action, and control your review workflow without relying on keyboard shortcuts.

Designed for mouse-only review, gaming mice, multi-button mice, and anyone who wants a more flexible Anki review setup.

## Features

- **Configurable mouse controls** — assign actions to supported mouse inputs.
- **Right-click and middle-click support** — trigger review actions directly.
- **Scroll-wheel shortcuts** — assign actions to scrolling up and down.
- **Extra mouse buttons** — use supported Back and Forward buttons.
- **Long-press actions** — assign secondary actions to a sustained press.
- **Separate question and answer actions** — configure different behaviour for each side of a card.
- **Review actions** — Show Answer, Again, Hard, Good, Easy, Do Nothing, and Undo (`Ctrl+Z`).
- **Live enable/disable toggle** — turn the add-on on or off during review.
- **Optional action feedback** — display feedback for the triggered action.
- **Instant settings updates** — changes are saved and applied without requiring a restart.
- **Configurable long-press duration** — adjust how long a button must be held before its secondary action triggers.

Compatibility with individual mouse buttons can depend on your mouse hardware and operating system.

## Preview

### Mouse Shortcuts in Action

![Mouse Shortcuts demo](https://i.postimg.cc/52hmrFdk/1.gif)

### Settings

![Mouse Shortcuts settings](https://i.postimg.cc/sxpDRqys/1.png)

Configure mouse actions and change settings for your review workflow.

### Assign Review Actions

![Review action configuration](https://i.postimg.cc/VNNqdwfD/image.png)

Choose actions for the question and answer sides, including answer reveal, review ratings, and no action.

### Long-Press Actions

![Long-press action configuration](https://i.postimg.cc/1zRkX8VB/image.png)

Configure secondary actions, such as Undo (`Ctrl+Z`), using a long press.

## How to Use

1. Install the add-on from AnkiWeb.
2. Open **Tools → Mouse Shortcuts** in Anki Desktop.
3. Assign actions to your preferred mouse inputs.
4. Configure separate actions for the question and answer sides.
5. Optionally configure long-press actions and the feedback indicator.
6. Start reviewing and use your mouse to trigger the configured actions.

Settings are saved and applied immediately, so you can adjust your setup without restarting Anki.

## Example Configuration

For example, you could configure your mouse like this:

| Mouse input | Question side | Answer side |
|---|---|---|
| Right click | Show Answer | Good |
| Scroll up | Do Nothing | Easy |
| Scroll down | Do Nothing | Again |
| Middle click | Show Answer | Undo (`Ctrl+Z`) via long press |

This is only an example. You can choose the actions that suit your own workflow.

## Installation

### Install from AnkiWeb

Download the add-on:

**[Mouse Buttons as Review Shortcuts — AnkiWeb](https://ankiweb.net/shared/info/418106886)**

After installation, restart Anki if required and open **Tools → Mouse Shortcuts** to configure it.

### Manual Installation

1. Download or clone this repository.
2. Place the add-on folder in Anki's `addons21` directory.
3. Restart Anki.

Default add-on directories:

**Windows**
```text
%APPDATA%\Anki2\addons21\
```

**macOS**
```text
~/Library/Application Support/Anki2/addons21/
```

**Linux**
```text
~/.local/share/Anki2/addons21/
```

For most users, installing through AnkiWeb is the simplest option.

## Related Add-ons

These add-ons can complement a customized Anki review workflow:

- [FocusFlow](https://ankiweb.net/shared/info/454655166) — Pomodoro timer, study sessions, and progress tracking.
- [Minimalistic Drawing Panel](https://ankiweb.net/shared/info/1062267970) — draw, write, and annotate directly during review.
- [Focus Mode Suite](https://ankiweb.net/shared/info/441544076) — reduce interface distractions during Anki reviews.

## Bug Reports and Feature Requests

Found a bug, encountered a compatibility issue, or have an idea for improving the add-on?

[Open an issue on GitHub](https://github.com/Doummar/Mouse_Answer/issues).

When reporting a problem, include your Anki version, operating system, mouse model (if relevant), and the steps needed to reproduce the issue.

## About

Mouse Buttons as Review Shortcuts began as a tool for my own daily study sessions. Its features have grown from practical use and feedback, with the goal of making Anki reviews more comfortable and flexible.

Contributions, suggestions, and reports of reproducible issues are welcome.


