#!/usr/bin/env bash
# Common helpers for Raspberry Pi host runtime maintenance scripts.

section() {
  printf '\n== %s ==\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 2
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

require_command() {
  command_exists "$1" || fail "required command missing: $1"
}

is_raspberry_pi() {
  grep -qi 'raspberry' /proc/device-tree/model 2>/dev/null
}

require_pi() {
  if ! is_raspberry_pi; then
    fail "this script is Pi-only; run it on the Raspberry Pi deploy target"
  fi
}

sudo_required() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return $?
  fi

  require_command sudo
  sudo "$@"
}

sudo_optional() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return $?
  fi

  if ! command_exists sudo; then
    warn "sudo is not available; skipped: $*"
    return 0
  fi

  if sudo -n true 2>/dev/null; then
    sudo "$@"
    return $?
  fi

  warn "sudo credentials are not available non-interactively; skipped: $*"
  return 0
}

git_work_tree() {
  git rev-parse --show-toplevel 2>/dev/null || true
}

show_git_state() {
  local root status

  if ! command_exists git; then
    warn "git is not available"
    return 0
  fi

  root="$(git_work_tree)"
  if [ -z "$root" ]; then
    warn "not inside a Git repository"
    return 0
  fi

  cd "$root" || fail "cannot enter Git work tree: $root"
  printf 'repo: %s\n' "$root"
  printf 'commit: %s\n' "$(git rev-parse --short HEAD)"

  status="$(git status --short)"
  if [ -z "$status" ]; then
    echo "OK: working tree clean"
  else
    echo "WARN: working tree has local changes:"
    printf '%s\n' "$status"
  fi
}

require_clean_git_tree() {
  local root status

  require_command git
  root="$(git_work_tree)"
  if [ -z "$root" ]; then
    fail "not inside a Git repository; host updates must run from the GitOps checkout"
  fi

  cd "$root" || fail "cannot enter Git work tree: $root"
  status="$(git status --short)"
  if [ -n "$status" ]; then
    echo "Refusing host runtime update because the working tree is not clean:" >&2
    printf '%s\n' "$status" >&2
    fail "commit, stash, or discard local changes before continuing"
  fi
}

print_reboot_status() {
  if [ -f /var/run/reboot-required ]; then
    echo "REBOOT_REQUIRED=yes"
    cat /var/run/reboot-required
    if [ -f /var/run/reboot-required.pkgs ]; then
      echo "Packages requiring reboot:"
      cat /var/run/reboot-required.pkgs
    fi
  else
    echo "REBOOT_REQUIRED=no"
  fi
}

print_apt_holds() {
  local holds

  holds="$(apt-mark showhold 2>/dev/null || true)"
  if [ -n "$holds" ]; then
    echo "Held packages:"
    printf '%s\n' "$holds"
  else
    echo "No held packages reported by apt-mark."
  fi
}

print_upgradable_packages() {
  apt list --upgradable 2>/dev/null || true
}

print_docker_versions() {
  if ! command_exists docker; then
    warn "docker is not available"
    return 0
  fi

  docker version || warn "docker version failed"
  docker compose version || warn "docker compose plugin is not available or failed"
}

print_docker_package_state() {
  local pkg status
  local packages=(
    docker-ce
    docker-ce-cli
    containerd.io
    docker-buildx-plugin
    docker-compose-plugin
  )

  if ! command_exists dpkg-query; then
    warn "dpkg-query is not available"
    return 0
  fi

  for pkg in "${packages[@]}"; do
    status="$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)"
    if [ "$status" = "install ok installed" ]; then
      echo "$pkg: installed"
      apt-cache policy "$pkg" 2>/dev/null | sed 's/^/  /' || true
    else
      echo "$pkg: not installed"
    fi
  done
}
