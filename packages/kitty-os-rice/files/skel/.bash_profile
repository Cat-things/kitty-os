# kitty-os ~/.bash_profile

[[ -f ~/.bashrc ]] && . ~/.bashrc

# Logging in on the first console starts the desktop.
if [[ -z $WAYLAND_DISPLAY && ${XDG_VTNR:-0} -eq 1 ]] && command -v sway >/dev/null; then
    export XDG_CURRENT_DESKTOP=sway
    export MOZ_ENABLE_WAYLAND=1
    export QT_QPA_PLATFORM='wayland;xcb'
    export _JAVA_AWT_WM_NONREPARENTING=1
    if systemd-detect-virt --quiet 2>/dev/null; then
        # Virtual machines often have no usable GPU.
        export WLR_RENDERER_ALLOW_SOFTWARE=1
        export WLR_NO_HARDWARE_CURSORS=1
    fi
    sway
fi
