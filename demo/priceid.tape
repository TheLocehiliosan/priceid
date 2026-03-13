Output demo/priceid.gif

Require priceid

Set Shell "bash"
Set Width 1200
Set Height 800
Set FontSize 16
Set Padding 10
Set Framerate 15
Set TypingSpeed 80ms

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

Type "priceid"
Enter
Sleep 1.5s

# Set charisma to 18 at the initial prompt
Type "18"
Sleep 500ms
Enter
Sleep 1s

# Search by buy price
Type "b"
Sleep 500ms
Type "200"
Sleep 1.5s
Escape
Sleep 1s

# Search by sell price
Type "s"
Sleep 500ms
Type "75"
Sleep 1.5s
Escape
Sleep 1s

# Identify an item
Type "i"
Sleep 500ms
Type "inv"
Sleep 1s
Enter
Sleep 1s

# Identify another item
Type "i"
Sleep 500ms
Type "conf"
Sleep 1s
Enter
Sleep 1s

# Toggle discovered items off
Type "d"
Sleep 1.5s

# Toggle discovered items back on
Type "d"
Sleep 1.5s

# Quit
Type "q"
Sleep 500ms
