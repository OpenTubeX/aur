#!/usr/bin/env bash
set -euo pipefail

recipe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

source "$recipe_dir/opentubex/PKGBUILD"
source_name="$_pkgname-$_pkgver"
srcdir="$test_dir/src"
pkgdir="$test_dir/pkg"
resources="$srcdir/$source_name/build/linux-unpacked/resources"
mkdir -p "$resources/app.asar.unpacked/dist" "$srcdir/$source_name/_icons"
printf 'archive fixture\n' > "$resources/app.asar"
printf '#!/bin/sh\nprintf "[]\\n"\n' > "$resources/app.asar.unpacked/dist/opentubex-cast"
chmod +x "$resources/app.asar.unpacked/dist/opentubex-cast"
touch "$srcdir/$source_name/LICENSE" "$srcdir/$source_name/_icons/icon.svg"
cp "$recipe_dir/opentubex/opentubex.sh" "$recipe_dir/opentubex/opentubex.desktop" "$srcdir/"

cd "$srcdir"
package
cmp "$resources/app.asar" "$pkgdir/usr/lib/$pkgname/app.asar"
helper="$pkgdir/usr/lib/$pkgname/app.asar.unpacked/dist/opentubex-cast"
if [[ ! -x "$helper" ]]; then
  printf 'FAIL: packaged Cast helper is missing or not executable\n' >&2
  exit 1
fi
[[ $("$helper" discover) == '[]' ]]
[[ " ${makedepends[*]} " == *' go '* ]]
rm -rf "$resources/app.asar.unpacked" "$pkgdir"
cd "$srcdir"
package
cmp "$resources/app.asar" "$pkgdir/usr/lib/$pkgname/app.asar"
printf 'PASS: preserves the executable Cast helper, declares Go, and packages releases without unpacked resources\n'
