#!/usr/bin/env bash
set -euo pipefail

recipe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../opentubex" && pwd)
test_dir=$(mktemp -d "$recipe_dir/build-test.XXXXXX")
trap 'rm -rf -- "$test_dir"' EXIT

# shellcheck source=opentubex/PKGBUILD
source "$recipe_dir/PKGBUILD"
srcdir="$test_dir/src"
mkdir -p "$srcdir/$_pkgname-$_pkgver" "$test_dir/bin"

cat > "$test_dir/bin/pnpm" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
[[ ${TMPDIR:-} == "$srcdir/tmp" && -d $TMPDIR ]] || {
  printf 'FAIL: pnpm %s must use temporary storage in srcdir\n' "$1" >&2
  exit 1
}
probe=$(mktemp)
[[ $probe == "$srcdir/tmp/"* ]]
rm -- "$probe"
printf '%s\n' "$1" >> "$build_test_calls"
SH
chmod +x "$test_dir/bin/pnpm"

export srcdir
export build_test_calls="$test_dir/calls"
export PATH="$test_dir/bin:$PATH"
# The recipe must also work when the inherited temporary directory is unusable.
export TMPDIR="$test_dir/missing"

build
[[ $(cat "$build_test_calls") == $'install\nbuild' ]]
printf 'PASS: install and build use writable temporary storage in srcdir\n'
