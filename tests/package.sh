#!/usr/bin/env bash
set -euo pipefail

recipe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

test_package() (
  # Both recipes provide the same makepkg variables and functions.
  # shellcheck source=opentubex/PKGBUILD
  source "$recipe_dir/$recipe/PKGBUILD"
  [[ " ${arch[*]} " == *" $CARCH "* ]] || {
    printf 'FAIL: %s must declare support for %s\n' "$recipe" "$CARCH" >&2
    exit 1
  }
  [[ " ${arch[*]} " != *' any '* ]]
  source_name="$_pkgname"
  if [[ $recipe == opentubex ]]; then
    source_name+="-$_pkgver"
  fi
  srcdir="$test_dir/$recipe-$CARCH/src"
  pkgdir="$test_dir/$recipe-$CARCH/pkg"
  build_directory=linux-unpacked
  if [[ $CARCH == aarch64 ]]; then
    build_directory=linux-arm64-unpacked
  fi
  resources="$srcdir/$source_name/build/$build_directory/resources"
  mkdir -p "$resources/app.asar.unpacked/dist" "$srcdir/$source_name/_icons"
  printf 'archive fixture for %s\n' "$CARCH" > "$resources/app.asar"
  printf '#!/bin/sh\nprintf "%%s\\n" "%s"\n' "$CARCH" > "$resources/app.asar.unpacked/dist/opentubex-cast"
  chmod +x "$resources/app.asar.unpacked/dist/opentubex-cast"
  touch "$srcdir/$source_name/LICENSE" "$srcdir/$source_name/_icons/icon.svg"
  cp "$recipe_dir/$recipe/opentubex.sh" "$recipe_dir/$recipe/opentubex.desktop" "$srcdir/"

  cd "$srcdir"
  package
  cmp "$resources/app.asar" "$pkgdir/usr/lib/$pkgname/app.asar"
  helper="$pkgdir/usr/lib/$pkgname/app.asar.unpacked/dist/opentubex-cast"
  if [[ ! -x "$helper" ]]; then
    printf 'FAIL: packaged Cast helper is missing or not executable\n' >&2
    exit 1
  fi
  [[ $("$helper" discover) == "$CARCH" ]]
  [[ " ${makedepends[*]} " == *' go '* ]]
  if [[ $recipe == opentubex ]]; then
    rm -rf "$resources/app.asar.unpacked" "$pkgdir"
    cd "$srcdir"
    package
    cmp "$resources/app.asar" "$pkgdir/usr/lib/$pkgname/app.asar"
  fi
  printf 'PASS: %s on %s packages the matching archive and executable Cast helper\n' "$recipe" "$CARCH"
)

for recipe in opentubex opentubex-git; do
  for CARCH in x86_64 aarch64; do
    test_package
  done
done
