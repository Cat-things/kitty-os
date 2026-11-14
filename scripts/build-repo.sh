#!/bin/bash
# Builds every package in packages/ and turns the result into a pacman
# repository. Run on Arch as a normal user (makepkg refuses to run as root).
#
#   scripts/build-repo.sh [OUTPUT_DIR]     default: out/repo
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
out=$(realpath -m "${1:-$root/out/repo}")

mkdir -p "$out"
rm -f "$out"/*.pkg.tar.* "$out"/kitty-os.db* "$out"/kitty-os.files*

for pkgbuild in "$root"/packages/*/PKGBUILD; do
    echo "==> $(basename "$(dirname "$pkgbuild")")"
    # --nodeps: nothing here compiles, so the build needs none of the
    # runtime dependencies installed.
    (cd "$(dirname "$pkgbuild")" && PKGDEST="$out" makepkg --force --nodeps --clean)
done

cd "$out"
repo-add kitty-os.db.tar.gz ./*.pkg.tar.zst
# repo-add leaves kitty-os.db and kitty-os.files as symlinks. Hosts like
# GitHub Releases cannot store symlinks, so make them real files.
for name in kitty-os.db kitty-os.files; do
    cp --remove-destination "$(readlink -f "$name")" "$name"
done
rm -f ./*.old

echo "==> Repository ready in $out"
ls -1 "$out"
