# main.py

import curses
import subprocess
import sys
import time

MENU_OPTIONS = [
    "1. Generate Images from Conversation",
    "2. Create Video from Generated Images",
    "3. Create Final Video with Audio",
    "4. Quit"
]

# Mapping of menu option index to a command list (adjust as needed)
COMMAND_MAPPING = {
    0: ["python", "generate_image.py"],
    1: ["python", "create_video.py"],
    2: ["python", "sfx.py", "--cleanup"],
}

def run_command(command):
    """Suspend curses, run the command and wait for completion."""
    curses.endwin()  # Temporarily end curses mode
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command {command} failed: {e}")
    input("\nPress Enter to return to the main menu...")
    
def draw_menu(stdscr, selected_index):
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    title = "Conversation Video Creator"
    stdscr.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD | curses.A_UNDERLINE)
    
    for idx, menu_item in enumerate(MENU_OPTIONS):
        x = (width - len(menu_item)) // 2
        y = 3 + idx
        if idx == selected_index:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(y, x, menu_item)
            stdscr.attroff(curses.A_REVERSE)
        else:
            stdscr.addstr(y, x, menu_item)
    stdscr.refresh()

def curses_menu(stdscr):
    # Hide the cursor
    curses.curs_set(0)
    selected_index = 0

    while True:
        draw_menu(stdscr, selected_index)
        key = stdscr.getch()
        
        # Use arrow keys to navigate the menu
        if key in [curses.KEY_UP, ord('k')]:
            selected_index = (selected_index - 1) % len(MENU_OPTIONS)
        elif key in [curses.KEY_DOWN, ord('j')]:
            selected_index = (selected_index + 1) % len(MENU_OPTIONS)
        elif key in [curses.KEY_ENTER, 10, 13]:
            # User pressed Enter
            if selected_index == len(MENU_OPTIONS) - 1:  # Quit option selected
                break
            else:
                # Get corresponding command and run it
                command = COMMAND_MAPPING.get(selected_index)
                if command:
                    run_command(command)
        elif key in [ord('q'), ord('Q')]:
            break

def main():
    try:
        curses.wrapper(curses_menu)
    except Exception as e:
        # In case of error, ensure terminal settings are restored
        curses.endwin()
        print(f"Error in curses application: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
