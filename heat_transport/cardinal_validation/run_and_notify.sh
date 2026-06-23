#!/usr/bin/env bash
# Run the Layer 2 Cardinal validation and push a phone notification with the parsed
# results when it finishes (or fails), so you can walk away from the PC.
#
# ONE-TIME SETUP:
#   1. Install the "ntfy" app on your phone (iOS/Android), open it, and subscribe to a
#      topic you pick, e.g.  csnr-cardinal-9f3qz7  (make it long/random; anyone who knows
#      the topic can read the messages, and these are just k-eff and temperatures).
#   2. On the PC, in the moose env, export that same topic:
#        export NTFY_TOPIC=csnr-cardinal-9f3qz7
#      (add it to ~/.bashrc to make it stick.)
#
# RUN (moose env, model.xml already built, OPENMC_CROSS_SECTIONS set):
#   cd ~/csnr/heat_transport/cardinal_validation
#   bash run_and_notify.sh
#
# To survive an SSH/terminal disconnect, run it detached:
#   nohup bash run_and_notify.sh >notify.out 2>&1 &
#
# Override the run command or core count if needed via env: NP, NTHREADS.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
RUNDIR="$HERE/../layer2_core"
TOPIC="${NTFY_TOPIC:-}"
NP="${NP:-10}"
NTHREADS="${NTHREADS:-2}"

cd "$RUNDIR" || { echo "no $RUNDIR"; exit 1; }
echo "Running Cardinal in $RUNDIR (np=$NP, threads=$NTHREADS) ..."
mpiexec -np "$NP" ~/cardinal/cardinal-opt -i openmc.i --n-threads="$NTHREADS" 2>&1 | tee run.log
STATUS=${PIPESTATUS[0]}

if [ "$STATUS" -eq 0 ]; then
  MSG="$(python3 "$HERE/notify_results.py" "$RUNDIR")"
else
  MSG="SNAP Cardinal run FAILED (exit $STATUS): $(tail -n 2 run.log | tr '\n' ' ')"
fi
echo "$MSG"

if [ -n "$TOPIC" ]; then
  curl -s -H "Title: SNAP Cardinal" -d "$MSG" "https://ntfy.sh/$TOPIC" >/dev/null \
    && echo "[pushed to ntfy.sh/$TOPIC]" \
    || echo "[ntfy push failed; check network]"
else
  echo "[NTFY_TOPIC not set -- no push sent; export it to enable notifications]"
fi
