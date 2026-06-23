#!/usr/bin/env bash
# test_notify.sh -- exercise the whole notification pipeline WITHOUT running Cardinal.
# It fabricates synthetic result CSVs that look like a CONVERGED 34 kWt design point,
# runs the real notify_results.py parser on them, and pushes the summary to your ntfy
# topic. If your phone buzzes with a sensible line, the chain works and you can trust the
# real run's notification.
#
#   export NTFY_TOPIC=csnr-cardinal-9f3qz7   # same topic your phone is subscribed to
#   bash test_notify.sh
#
# With no NTFY_TOPIC set it just prints the message (tests the parser, no push).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TOPIC="${NTFY_TOPIC:-}"
T="$(mktemp -d)"

# --- synthetic results: a converged 34 kWt run -------------------------------------
printf 'time,heat_source,k\n15,34000.0,1.00060\n' > "$T/openmc_out.csv"
printf 'time,max_fuel_T,power_imbalance,power_in,surface_heat_out\n100,850.0,-50.0,34000.0,34050.0\n' \
  > "$T/solid_core.csv"
# 37 NaK channels, ~919 W each (sum ~34 kW), outlets ~818 K with one hot channel ~852 K
n=0
for ch in $(seq -w 10 10 370); do
  out=818.0; [ "$ch" = "010" ] && out=852.0
  printf 'time,T_fluid_in_diag,T_fluid_out,heat_added\n100,755.4,%s,919.0\n' "$out" \
    > "$T/openmc_out_solid0_thm${ch}_csv.csv"
  n=$((n + 1))
done

MSG="[TEST] $(python3 "$HERE/notify_results.py" "$T")"
echo "$MSG"
echo "(synthetic: $n channels, ~34 kW total -> the line above should end CONVERGED)"

if [ -n "$TOPIC" ]; then
  curl -s -H "Title: SNAP Cardinal TEST" -d "$MSG" "https://ntfy.sh/$TOPIC" >/dev/null \
    && echo "[pushed TEST to ntfy.sh/$TOPIC -- check your phone]" \
    || echo "[ntfy push FAILED -- check network or topic name]"
else
  echo "[NTFY_TOPIC not set -- parser ran, no push. export NTFY_TOPIC and re-run to test your phone]"
fi
rm -rf "$T"
