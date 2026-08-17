#!/usr/bin/env -S npx tsx
/**
 * Run Cursor agents against Soul Harvest from a script or CI.
 *
 * Patterns:
 *   prompt  — Agent.prompt() one-shot (create, run, dispose)
 *   send    — Agent.create() + send + stream + wait (durable, follow-ups via resume)
 *   resume  — Agent.resume() across process boundaries
 */
import { parseArgs } from "node:util";
import {
  Agent,
  Cursor,
  CursorAgentError,
  IntegrationNotConnectedError,
  type AgentOptions,
  type Run,
  type SDKMessage,
} from "@cursor/sdk";

const DEFAULT_MODEL = "composer-2.5";
const DEFAULT_REPO =
  "https://github.com/alexdepasquale2-jpg/solarsystemcalculator";

type Runtime = "local" | "cloud";

type Flags = {
  runtime: Runtime;
  model: string;
  cwd: string;
  repo: string;
  ref: string;
  name?: string;
  pr: boolean;
  quiet: boolean;
  ci: boolean;
  help: boolean;
};

function printHelp(): void {
  process.stdout.write(`Soul Harvest Cursor SDK CLI

Usage:
  npm run agent -- <command> [options] [prompt...]

Commands:
  prompt <text>           One-shot Agent.prompt (create, run, dispose)
  send <text>             Durable Agent.create + send; streams then wait()
  resume <agentId> <text> Continue an existing agent (bc- = cloud)
  models                  List models available to this API key
  list                    List agents for the selected runtime
  get <agentId>           Inspect an agent by ID
  get-run <runId>         Inspect a run (cloud needs --agent <id>)

Options:
  --runtime local|cloud   Explicit runtime (default: local)
  --model <id>            Model id (default: ${DEFAULT_MODEL})
  --cwd <path>            Local working directory
  --repo <url>            Cloud repo URL
  --ref <git-ref>         Cloud starting ref (default: main)
  --agent <id>            Parent agent id for cloud get-run
  --name <name>           Human-readable agent name
  --pr                    Cloud: open a PR when the run finishes
  --quiet                 Skip streaming; only wait() for the result
  --ci                    Cloud: skip reviewer request (also auto in GITHUB_ACTIONS)
  -h, --help              Show this help

Exit codes:
  0  run finished
  1  startup failure (auth, config, network) — CursorAgentError
  2  run executed and failed (result.status === "error")
  3  run cancelled

Examples:
  export CURSOR_API_KEY="cursor_..."
  npm run agent -- prompt "Summarize src/game/engine.ts"
  npm run agent -- send --runtime local "Add a planet after the last one"
  npm run agent -- send --runtime cloud --pr "Balance reaper merge costs"
  npm run agent -- resume agent-abc123 "Also update the README"
`);
}

function requireApiKey(): string {
  const apiKey = process.env.CURSOR_API_KEY?.trim();
  if (!apiKey) {
    console.error(
      "Set CURSOR_API_KEY. User keys: https://cursor.com/dashboard/integrations — service accounts: Team Settings.",
    );
    process.exit(1);
  }
  return apiKey;
}

function parseRuntime(value: string): Runtime {
  if (value === "local" || value === "cloud") return value;
  console.error(`Invalid --runtime "${value}". Use local or cloud.`);
  process.exit(1);
}

function parseCli(argv: string[]): { command: string; rest: string[]; flags: Flags; agentForRun?: string } {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      runtime: { type: "string", default: "local" },
      model: { type: "string", default: DEFAULT_MODEL },
      cwd: { type: "string", default: process.cwd() },
      repo: { type: "string", default: DEFAULT_REPO },
      ref: { type: "string", default: "main" },
      agent: { type: "string" },
      name: { type: "string" },
      pr: { type: "boolean", default: false },
      quiet: { type: "boolean", default: false },
      ci: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
  });

  const flags: Flags = {
    runtime: parseRuntime(values.runtime ?? "local"),
    model: values.model ?? DEFAULT_MODEL,
    cwd: values.cwd ?? process.cwd(),
    repo: values.repo ?? DEFAULT_REPO,
    ref: values.ref ?? "main",
    name: values.name,
    pr: Boolean(values.pr),
    quiet: Boolean(values.quiet),
    ci: Boolean(values.ci),
    help: Boolean(values.help),
  };

  const [command = "", ...rest] = positionals;
  return { command, rest, flags, agentForRun: values.agent };
}

function agentOptions(flags: Flags): AgentOptions {
  const apiKey = requireApiKey();
  const model = { id: flags.model };
  const name = flags.name ?? "Soul Harvest SDK agent";

  // Always set local or cloud explicitly. Omitting both silently selects local.
  if (flags.runtime === "cloud") {
    const skipReviewerRequest =
      flags.ci || Boolean(process.env.GITHUB_ACTIONS);
    return {
      apiKey,
      model,
      name,
      cloud: {
        repos: [{ url: flags.repo, startingRef: flags.ref }],
        autoCreatePR: flags.pr,
        skipReviewerRequest,
      },
    };
  }

  return {
    apiKey,
    model,
    name,
    local: { cwd: flags.cwd },
  };
}

function writeEvent(event: SDKMessage): void {
  switch (event.type) {
    case "assistant":
      for (const block of event.message.content) {
        if (block.type === "text") process.stdout.write(block.text);
      }
      break;
    case "thinking":
      if (event.text.trim()) {
        process.stderr.write(`[thinking] ${event.text.replace(/\s+/g, " ").trim()}\n`);
      }
      break;
    case "tool_call":
      process.stderr.write(`[tool] ${event.name}: ${event.status}\n`);
      break;
    case "status":
      process.stderr.write(`[status] ${event.status}\n`);
      break;
    default:
      break;
  }
}

function exitForResult(status: string): never {
  if (status === "finished") process.exit(0);
  if (status === "cancelled") process.exit(3);
  process.exit(2);
}

async function observeRun(run: Run, quiet: boolean): Promise<void> {
  process.stderr.write(`agentId=${run.agentId} runId=${run.id}\n`);

  const cancelIfPossible = async (): Promise<void> => {
    if (run.supports("cancel")) {
      process.stderr.write("cancelling run…\n");
      await run.cancel();
    } else {
      process.stderr.write(
        `cancel unsupported: ${run.unsupportedReason("cancel") ?? "unknown"}\n`,
      );
    }
  };
  process.once("SIGINT", () => {
    void cancelIfPossible();
  });

  if (!quiet && run.supports("stream")) {
    for await (const event of run.stream()) {
      writeEvent(event);
    }
    process.stdout.write("\n");
  } else if (!quiet && !run.supports("stream")) {
    process.stderr.write(
      `stream unsupported: ${run.unsupportedReason("stream") ?? "unknown"}\n`,
    );
  }

  const result = await run.wait();
  process.stderr.write(
    `[done] status=${result.status} durationMs=${result.durationMs ?? "?"}\n`,
  );
  if (result.git?.branches?.length) {
    for (const branch of result.git.branches) {
      process.stderr.write(
        `[git] ${branch.repoUrl} branch=${branch.branch ?? "?"} pr=${branch.prUrl ?? "none"}\n`,
      );
    }
  }
  if (result.status === "error") {
    console.error(`run failed: ${result.id} ${result.error?.message ?? ""}`);
  } else if (quiet && result.result) {
    process.stdout.write(`${result.result}\n`);
  }
  exitForResult(result.status);
}

function handleStartupError(err: unknown): never {
  if (err instanceof IntegrationNotConnectedError) {
    console.error(
      `startup failed: ${err.message} retryable=${err.isRetryable} provider=${err.provider} helpUrl=${err.helpUrl}`,
    );
    process.exit(1);
  }
  if (err instanceof CursorAgentError) {
    console.error(
      `startup failed: ${err.message} retryable=${err.isRetryable}` +
        (err.requestId ? ` requestId=${err.requestId}` : ""),
    );
    process.exit(1);
  }
  throw err;
}

async function cmdPrompt(prompt: string, flags: Flags): Promise<void> {
  const result = await Agent.prompt(prompt, agentOptions(flags));
  process.stderr.write(`runId=${result.id} status=${result.status}\n`);
  if (result.result) process.stdout.write(`${result.result}\n`);
  if (result.status === "error") {
    console.error(`run failed: ${result.id} ${result.error?.message ?? ""}`);
  }
  exitForResult(result.status);
}

async function cmdSend(prompt: string, flags: Flags): Promise<void> {
  await using agent = await Agent.create(agentOptions(flags));
  process.stderr.write(`agentId=${agent.agentId}\n`);
  const run = await agent.send(prompt);
  await observeRun(run, flags.quiet);
}

async function cmdResume(agentId: string, prompt: string, flags: Flags): Promise<void> {
  const apiKey = requireApiKey();
  // Runtime is auto-detected from the ID prefix (bc- = cloud). Still pass the
  // matching options object so follow-ups don't silently flip to local.
  const cloud = agentId.startsWith("bc-");
  await using agent = await Agent.resume(agentId, {
    apiKey,
    model: { id: flags.model },
    ...(cloud
      ? {
          cloud: {
            repos: [{ url: flags.repo, startingRef: flags.ref }],
            autoCreatePR: flags.pr,
            skipReviewerRequest: flags.ci || Boolean(process.env.GITHUB_ACTIONS),
          },
        }
      : { local: { cwd: flags.cwd } }),
  });
  process.stderr.write(`resumed agentId=${agent.agentId}\n`);
  const run = await agent.send(prompt);
  await observeRun(run, flags.quiet);
}

async function cmdModels(): Promise<void> {
  const apiKey = requireApiKey();
  const models = await Cursor.models.list({ apiKey });
  for (const model of models) {
    const params = model.parameters?.map((p) => p.id).join(",") ?? "";
    process.stdout.write(`${model.id}${params ? ` params=${params}` : ""}\n`);
  }
}

async function cmdList(flags: Flags): Promise<void> {
  const apiKey = requireApiKey();
  const { items } = await Agent.list(
    flags.runtime === "cloud"
      ? { runtime: "cloud", apiKey }
      : { runtime: "local", cwd: flags.cwd },
  );
  for (const info of items) {
    process.stdout.write(`${info.agentId}\t${info.name ?? ""}\t${info.status ?? ""}\n`);
  }
}

async function cmdGet(agentId: string, flags: Flags): Promise<void> {
  const apiKey = requireApiKey();
  const info = await Agent.get(agentId, { apiKey, cwd: flags.cwd });
  process.stdout.write(`${JSON.stringify(info, null, 2)}\n`);
}

async function cmdGetRun(runId: string, flags: Flags, agentId?: string): Promise<void> {
  const apiKey = requireApiKey();
  const run =
    flags.runtime === "cloud"
      ? await Agent.getRun(runId, {
          runtime: "cloud",
          agentId: agentId ?? fail("cloud get-run requires --agent <id>"),
          apiKey,
        })
      : await Agent.getRun(runId, { runtime: "local", cwd: flags.cwd });
  process.stdout.write(
    `${JSON.stringify(
      {
        id: run.id,
        agentId: run.agentId,
        status: run.status,
        result: run.result,
        error: run.error,
        durationMs: run.durationMs,
        git: run.git,
      },
      null,
      2,
    )}\n`,
  );
}

function fail(message: string): never {
  console.error(message);
  process.exit(1);
}

async function main(): Promise<void> {
  const { command, rest, flags, agentForRun } = parseCli(process.argv.slice(2));

  if (flags.help || command === "help" || command === "") {
    printHelp();
    process.exit(command && command !== "help" ? 1 : 0);
  }

  try {
    switch (command) {
      case "prompt":
        await cmdPrompt(rest.join(" ").trim() || fail("prompt requires a message"), flags);
        break;
      case "send":
        await cmdSend(rest.join(" ").trim() || fail("send requires a message"), flags);
        break;
      case "resume": {
        const [agentId, ...promptParts] = rest;
        if (!agentId) fail("resume requires <agentId> <prompt>");
        await cmdResume(agentId, promptParts.join(" ").trim() || fail("resume requires a prompt"), flags);
        break;
      }
      case "models":
        await cmdModels();
        break;
      case "list":
        await cmdList(flags);
        break;
      case "get":
        await cmdGet(rest[0] || fail("get requires <agentId>"), flags);
        break;
      case "get-run":
        await cmdGetRun(rest[0] || fail("get-run requires <runId>"), flags, agentForRun);
        break;
      default:
        fail(`Unknown command: ${command}\nRun with --help for usage.`);
    }
  } catch (err) {
    handleStartupError(err);
  }
}

await main();
