#!/usr/bin/env node
/**
 * Tiny test harness binary used by tests/runner-failure.test.mjs to
 * exercise the runClaude generator without spawning real `claude -p`.
 *
 * Modes (set via argv):
 *   --mode=success           exit 0 immediately
 *   --mode=success-after=Nms write `ok` to stdout, sleep N, exit 0
 *   --mode=fail-with=N       exit with code N
 *   --mode=sleep=Nms         sleep N and exit 0 (for timeout tests)
 *   --mode=stdout-loop=Nms   write a line every N ms forever (until killed)
 *
 * Default behaviour: exit 0.
 */

const args = Object.fromEntries(
  process.argv.slice(2).map((arg) => {
    const m = arg.match(/^--([^=]+)=(.+)$/);
    if (m) return [m[1], m[2]];
    return [arg.replace(/^--/, ""), "true"];
  }),
);

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  const mode = args.mode ?? "success";

  if (mode === "success") {
    process.stdout.write("ok\n");
    process.exit(0);
  }

  if (mode.startsWith("success-after=")) {
    const ms = parseInt(mode.split("=")[1], 10);
    await delay(ms);
    process.stdout.write("ok-after\n");
    process.exit(0);
  }

  if (mode.startsWith("fail-with=")) {
    const code = parseInt(mode.split("=")[1], 10);
    process.stderr.write(`fake-claude failing with code ${code}\n`);
    process.exit(code);
  }

  if (mode.startsWith("sleep=")) {
    const ms = parseInt(mode.split("=")[1], 10);
    // Make it visible that we started.
    process.stdout.write("starting long sleep\n");
    await delay(ms);
    process.stdout.write("woke up\n");
    process.exit(0);
  }

  if (mode.startsWith("stdout-loop=")) {
    const ms = parseInt(mode.split("=")[1], 10);
    let i = 0;
    setInterval(() => {
      process.stdout.write(`tick ${++i}\n`);
    }, ms);
    // Keep process alive forever — test harness must SIGTERM us.
    return new Promise(() => {});
  }

  process.stderr.write(`unknown fake-claude mode: ${mode}\n`);
  process.exit(2);
}

main();
