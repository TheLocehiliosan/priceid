Output demo/priceid-small.gif

Require priceid

Set Shell "bash"
Set Width 800
Set Height 500
Set FontSize 16
Set Padding 10
Set Framerate 15
Set TypingSpeed 120ms

Hide
Type "export PS1='> ' && unset PROMPT_COMMAND"
Enter
Sleep 500ms
Type "unset NO_COLOR"
Enter
Sleep 500ms
Type "rm -f ~/.config/priceid/state.json"
Enter
Sleep 500ms
Type "clear"
Enter
Sleep 500ms
Show

Type "priceid --small"
Enter
Sleep 2s

# Set charisma to 18 at the initial prompt
Type "18"
Sleep 800ms
Enter
Sleep 1.5s

# Scroll down through the full view
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 400ms
Type "j"
Sleep 1.5s

# Scroll back up
Ctrl+U
Sleep 1.5s

# Search by buy price
Type "b"
Sleep 800ms
Type "67"
Sleep 2.5s
Escape
Sleep 1.5s

# Search by sell price
Type "s"
Sleep 800ms
Type "75"
Sleep 2.5s
Escape
Sleep 1.5s

# Identify an item
Type "i"
Sleep 800ms
Type "!speed"
Sleep 1.5s
Enter
Sleep 1.5s

# Identify another item
Type "i"
Sleep 800ms
Type "?identify"
Sleep 1.5s
Enter
Sleep 1.5s

# Toggle discovered items off
Type "d"
Sleep 2.5s

# Toggle discovered items back on
Type "d"
Sleep 2.5s

# Show the legend
Type@150ms "?"
Sleep 3s
Type "j"
Sleep 100ms
Type "j"
Sleep 100ms
Type "j"
Sleep 100ms
Type "j"
Sleep 100ms
Type "j"
Sleep 100ms
Type "j"
Sleep 100ms
Type "j"
Sleep 100ms
Type "j"
Sleep 100ms
Type "j"
Sleep 1.5s
Type "q"
Sleep 1.5s

# Quit
Type "q"
Sleep 1s
