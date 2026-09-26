#!/usr/bin/env bash
# Isolated, checksum-verified Blender. Does not install or change GPU drivers.
set -euo pipefail
model_root="$(cd "$(dirname "$0")/../.." && pwd)"
model_version=4.5.14
model_package="blender-${model_version}-linux-x64.tar.xz"
model_dir="$model_root/.tools/blender-${model_version}-linux-x64"
if [[ ! -x "$model_dir/blender" ]]; then
  model_tmp="$(mktemp -d)"
  trap 'rm -rf "$model_tmp"' EXIT
  curl -fL --retry 2 "https://mirror.blender.org/release/Blender4.5/$model_package" -o "$model_tmp/$model_package"
  curl -fL --retry 2 "https://mirror.blender.org/release/Blender4.5/blender-${model_version}.sha256" -o "$model_tmp/checksums"
  (cd "$model_tmp"; awk -v file="$model_package" '$2==file' checksums | sha256sum --check --strict -)
  mkdir -p "$model_root/.tools"
  tar -xJf "$model_tmp/$model_package" -C "$model_root/.tools"
fi
"$model_dir/blender" --background --factory-startup --python-expr "import bpy; p=bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type='OPTIX'; p.get_devices(); print('RENDER_DEVICES', [(d.name,d.type) for d in p.devices])"
