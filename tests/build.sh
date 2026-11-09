#!/usr/bin/env bash
set -euo pipefail

recipe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

mkdir -p "$test_dir/bin"

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
if [[ $1 != install && $pkgname == opentubex-git ]]; then
  [[ $GITHUB_SHA == 0123456789012345678901234567890123456789 ]]
fi
printf '%s\n' "$*" >> "$build_test_calls"
SH
cat > "$test_dir/bin/git" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
[[ $* == 'rev-parse HEAD' ]]
printf '%s\n' 0123456789012345678901234567890123456789
SH
chmod +x "$test_dir/bin/pnpm" "$test_dir/bin/git"

for recipe in opentubex opentubex-git; do
  for architecture in x86_64 aarch64; do
    (
      # Both recipes provide the same makepkg variables and functions.
      # shellcheck source=opentubex/PKGBUILD
      source "$recipe_dir/$recipe/PKGBUILD"
      export CARCH="$architecture" pkgname
      export srcdir="$test_dir/$recipe-$CARCH/src"
      source_name="$_pkgname"
      if [[ $recipe == opentubex ]]; then
        source_name+="-$_pkgver"
      fi
      mkdir -p "$srcdir/$source_name"
      export build_test_calls="$test_dir/$recipe-$CARCH/calls"
      export PATH="$test_dir/bin:$PATH"
      # The recipe must also work when inherited temporary storage is unusable.
      export TMPDIR="$test_dir/missing"

      build
      if [[ $recipe == opentubex ]]; then
        build_arch=x64
        [[ $CARCH == aarch64 ]] && build_arch=arm64
        expected_build=$(printf 'run pack\nrun build-release %s' "$build_arch")
      else
        expected_build=build
      fi
      expected_calls=$(printf 'install --frozen-lockfile\n%s' "$expected_build")
      actual_calls=$(cat "$build_test_calls")
      if [[ $actual_calls != "$expected_calls" ]]; then
        printf 'FAIL: %s on %s should run:\n%s\ngot:\n%s\n' \
          "$recipe" "$CARCH" "$expected_calls" "$actual_calls" >&2
        exit 1
      fi
      printf 'PASS: %s on %s builds for its architecture with writable temporary storage\n' "$recipe" "$CARCH"
    )
  done
done
