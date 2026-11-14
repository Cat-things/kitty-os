#!/bin/bash
# Builds the kitty-os ISO. Run as root on Arch with 'archiso' installed,
# after scripts/build-repo.sh has built the packages.
#
#   iso/build.sh
#
# The ISO is the official Arch "releng" live medium plus the kitty-os desktop:
# releng's profile is copied, then iso/overlay and iso/packages.x86_64 are
# laid on top. Result: out/iso/kitty-os-*.iso
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
repo=$(realpath -m "${KITTY_OS_REPO:-$root/out/repo}")
work=$(realpath -m "${KITTY_OS_WORK:-$root/out/work}")
out=$(realpath -m "${KITTY_OS_OUT:-$root/out/iso}")
releng=/usr/share/archiso/configs/releng
profile=$work/profile

die() { echo "build.sh: $*" >&2; exit 1; }

(( EUID == 0 )) || die "mkarchiso needs root"
[[ -d $releng ]] || die "archiso is not installed (pacman -S archiso)"
[[ -f $repo/kitty-os.db ]] || die "no package repository in $repo; run scripts/build-repo.sh first"

rm -rf "$work"
mkdir -p "$profile" "$out"
cp -a "$releng/." "$profile/"

# releng logs in root on the console. Ours logs in the live user instead.
rm -rf "$profile/airootfs/etc/systemd/system/getty@tty1.service.d"
cp -a "$root/iso/overlay/." "$profile/"

# The installer, and a copy of our packages so it works without the online repo.
install -Dm755 "$root/scripts/kittyfy" "$profile/airootfs/usr/local/bin/kittyfy"
install -Dm644 -t "$profile/airootfs/opt/kitty-os-repo" "$repo"/*.pkg.tar.zst

grep -vE '^[[:space:]]*(#|$)' "$root/iso/packages.x86_64" >> "$profile/packages.x86_64"
cat "$root/iso/profiledef.kitty.sh" >> "$profile/profiledef.sh"
cat >> "$profile/pacman.conf" <<CONF

[kitty-os]
SigLevel = Optional TrustAll
Server = file://$repo
CONF

# Boot menus say kitty-os.
grep -rlZ 'Arch Linux' "$profile/grub" "$profile/syslinux" "$profile/efiboot" 2>/dev/null \
    | xargs -0 -r sed -i 's/Arch Linux install medium/kitty-os/g; s/Arch Linux/kitty-os/g'

mkarchiso -v -w "$work/build" -o "$out" "$profile"
echo "==> $(ls "$out"/kitty-os-*.iso)"
