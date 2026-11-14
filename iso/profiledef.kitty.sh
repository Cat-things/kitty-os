
# --- kitty-os: appended to the releng profiledef.sh by iso/build.sh ---
iso_name="kitty-os"
iso_label="KITTYOS_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="kitty-os <https://github.com/cat-things/kitty-os>"
iso_application="kitty-os live and install medium"
file_permissions+=(
  ["/etc/sudoers.d"]="0:0:750"
  ["/etc/sudoers.d/00-kitty-live"]="0:0:440"
  ["/usr/local/bin/kitty-live-user"]="0:0:755"
  ["/usr/local/bin/kittyfy"]="0:0:755"
)
