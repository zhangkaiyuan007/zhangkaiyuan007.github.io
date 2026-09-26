#!/usr/bin/env bash
# Tools and assets for scripts/modeling/build_rider.py.
# Everything is pinned and checksum-verified, and installed only under the git-ignored .tools/ directory:
#   .tools/rider/downloads/     original archives
#   .tools/rider/blender-user/  isolated Blender user resources (MPFB extension + MakeHuman asset library)
# Nothing is installed system-wide and the normal ~/.config/blender profile is not touched.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
tools="$root/.tools/rider"
dl="$tools/downloads"
user_res="$tools/blender-user"
blender="$root/.tools/blender-4.5.14-linux-x64/blender"
mkdir -p "$dl" "$user_res"

if [[ ! -x "$blender" ]]; then
  "$root/scripts/modeling/setup.sh"          # checksum-verified Blender 4.5.14 LTS
fi

fetch() {  # url file sha256
  local url="$1" file="$dl/$2" sum="$3"
  if [[ ! -f "$file" ]] || ! echo "$sum  $file" | sha256sum --check --status -; then
    # the MakeHuman mirror sometimes closes the connection early: resume until the checksum matches
    for _ in 1 2 3 4 5 6; do
      curl -fL --retry 3 -C - --max-time 1800 -o "$file" "$url" || true
      echo "$sum  $file" | sha256sum --check --status - && break
    done
  fi
  echo "$sum  $file" | sha256sum --check --strict -
}

# MPFB 2.0.17 (MakeHuman plugin for Blender, GPL-3.0-or-later) from the Blender extensions platform
fetch "https://extensions.blender.org/download/sha256:4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87/add-on-mpfb-v2.0.17.zip" \
  add-on-mpfb-v2.0.17.zip 4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87
# MakeHuman asset packs (https://static.makehumancommunity.org/assets/assetpacks.html)
packs="https://files.makehumancommunity.org/asset_packs"
fetch "$packs/makehuman_system_assets/makehuman_system_assets_cc0.zip" makehuman_system_assets_cc0.zip \
  b542127a8e25547c7c29c19f2d1d2adb9a664c80396ecd694095dbc8028a0107            # CC0
fetch "$packs/shirts02/shirts02_ccby.zip" shirts02_ccby.zip \
  d711ca9f73212de855257ac08422e1e0ccb802e5231315c2a360d0fcfea5033e            # CC-BY (jacket)
fetch "$packs/pants01/pants01_cc0.zip" pants01_cc0.zip \
  e4e0ec60db34f279be291a83cfd7b342a7c5cf09bb7676682a5f39f4f6ac4ad9            # CC0 (trousers)

export BLENDER_USER_RESOURCES="$user_res"
if [[ ! -d "$user_res/extensions/user_default/mpfb" ]]; then
  "$blender" --command extension install-file -r user_default -e "$dl/add-on-mpfb-v2.0.17.zip"
fi

# Only the assets the build uses are unpacked into MPFB's user data directory.
data="$user_res/extensions/.user/user_default/mpfb/data"
mkdir -p "$data"
unzip -q -o "$dl/makehuman_system_assets_cc0.zip" -d "$data" \
  'skins/young_asian_male/*' 'eyes/high-poly/*' 'eyes/materials/*' 'eyebrows/eyebrow010/*' \
  'eyelashes/eyelashes01/*' 'clothes/shoes05/*' 'packs/*'
unzip -q -o "$dl/shirts02_ccby.zip" -d "$data" 'clothes/elvs_hooded_sweat_jacket1/*' 'packs/*'
unzip -q -o "$dl/pants01_cc0.zip" -d "$data" 'clothes/toigo_wool_pants/*' 'packs/*'

echo "rider assets ready in $data"
echo "build:  ./scripts/blender --background --factory-startup --python scripts/modeling/build_rider.py -- [--render]"
