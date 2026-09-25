#!/bin/sh
#
# Render alertmanager.yml for the one-shot service alertmanager-config-render.
#
# Runs in the prom/alertmanager image (BusyBox sh/awk plus amtool): offline, read-only root
# filesystem, no capabilities. POSIX sh on purpose - the image has no bash. No pipes, so no
# pipefail is needed. Findings F26 (modes), F35 (no swallowed errors), F36 (escaping),
# F8 (no runtime package install).
#
# Environment:
#   ALERT_EMAIL_ENABLED       "1" renders the email receivers; anything else renders none
#   ALERT_EMAIL_TO, ALERT_SMTP_SMARTHOST, ALERT_SMTP_FROM, ALERT_SMTP_AUTH_USERNAME,
#   ALERT_SMTP_AUTH_PASSWORD  required when enabled; no control characters
#   ALERT_SMTP_REQUIRE_TLS    required when enabled; "true" or "false"
#   RENDER_IN_DIR             default /in    (alertmanager.yml.tmpl, optional templates/)
#   RENDER_OUT_DIR            default /out   (alertmanager.yml, templates/)
#   RENDER_GROUP              default 65534  (alertmanager's group; may read the output)
#
# Exit codes: 0 rendered; 2 invalid input or template; any other = the failing command.
# Error messages name the variable, never its value.

set -eu

in_dir="${RENDER_IN_DIR:-/in}"
out_dir="${RENDER_OUT_DIR:-/out}"
group="${RENDER_GROUP:-65534}"
template="$in_dir/alertmanager.yml.tmpl"
out="$out_dir/alertmanager.yml"
tmp="$out.tmp"

fail() {
  echo "ERROR: $*" >&2
  exit 2
}

# require NAME: NAME must be set, non-empty and free of control characters (this includes
# newlines, which would otherwise inject YAML lines).
require() {
  eval "value=\${$1:-}"
  [ -n "$value" ] || fail "missing $1"
  case "$value" in
    *[[:cntrl:]]*) fail "$1 contains a control character" ;;
  esac
}

[ -f "$template" ] || fail "template not found: $template"

enabled=0
if [ "${ALERT_EMAIL_ENABLED:-0}" = "1" ]; then
  enabled=1
  for name in ALERT_EMAIL_TO ALERT_SMTP_SMARTHOST ALERT_SMTP_FROM \
    ALERT_SMTP_AUTH_USERNAME ALERT_SMTP_AUTH_PASSWORD ALERT_SMTP_REQUIRE_TLS; do
    require "$name"
  done
  case "$ALERT_SMTP_REQUIRE_TLS" in
    true | false) ;;
    *) fail "ALERT_SMTP_REQUIRE_TLS must be 'true' or 'false'" ;;
  esac
fi

# The rendered config may hold the SMTP password: nothing below is for "other" (F26).
umask 027
trap 'rm -f "$tmp"' EXIT

# Replace the two placeholder lines with receiver blocks. Values are read from ENVIRON (never
# interpolated into the program) and emitted as double-quoted YAML scalars with \ and "
# escaped character by character - portable across gawk and BusyBox awk (F36).
awk -v enabled="$enabled" '
  function q(s,    out, i, c) {
    out = ""
    for (i = 1; i <= length(s); i++) {
      c = substr(s, i, 1)
      if (c == "\\" || c == "\"") out = out "\\"
      out = out c
    }
    return "\"" out "\""
  }
  function block() {
    if (enabled != 1) {
      print "    webhook_configs: [] # Disabled by IAC"
      return
    }
    print "    email_configs:"
    print "      - to: " q(ENVIRON["ALERT_EMAIL_TO"])
    print "        from: " q(ENVIRON["ALERT_SMTP_FROM"])
    print "        smarthost: " q(ENVIRON["ALERT_SMTP_SMARTHOST"])
    print "        auth_username: " q(ENVIRON["ALERT_SMTP_AUTH_USERNAME"])
    print "        auth_password: " q(ENVIRON["ALERT_SMTP_AUTH_PASSWORD"])
    print "        require_tls: " ENVIRON["ALERT_SMTP_REQUIRE_TLS"]
    print "        send_resolved: true"
  }
  $0 == "${ALERT_EMAIL_CRITICAL_YAML}" { block(); critical++; next }
  $0 == "${ALERT_EMAIL_WARNING_YAML}" { block(); warning++; next }
  { print }
  END { if (critical != 1 || warning != 1) exit 3 }
' "$template" >"$tmp" || fail "template must contain each receiver placeholder exactly once"

test -s "$tmp"
# amtool ships with the image; host-side tests (tests/guards/test_31) run without it.
if command -v amtool >/dev/null 2>&1; then
  amtool check-config "$tmp"
fi

chgrp "$group" "$tmp"
chmod 0640 "$tmp"
mv -f "$tmp" "$out"

# No cp -a: preserving the repo owner needs CAP_CHOWN, which is dropped (F35).
mkdir -p "$out_dir/templates"
if [ -d "$in_dir/templates" ]; then
  cp -R "$in_dir/templates/." "$out_dir/templates/"
fi
chgrp -R "$group" "$out_dir/templates"
chmod -R u=rwX,g=rX,o= "$out_dir/templates"

echo "Rendered $out and copied templates to $out_dir/templates"
