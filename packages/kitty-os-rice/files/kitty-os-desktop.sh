# kitty-os: logging in on the first console starts the desktop.
# Sourced by /etc/profile. Opt out with: touch ~/.config/kitty-os/no-autostart

if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ] \
        && [ "${XDG_VTNR:-0}" = 1 ] && [ "$(id -u)" -ge 1000 ] \
        && [ ! -e "$HOME/.config/kitty-os/no-autostart" ] \
        && command -v sway >/dev/null 2>&1; then
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
