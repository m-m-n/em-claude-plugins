#!/usr/bin/env bun
// em-sdd Stop hook: prevent /em-sdd:sdd orchestrator from halting mid-workflow.
//
// Behavior:
//   - Activates only when sdd.yaml exists in cwd/doc/tasks/*/ AND was
//     modified within the last RECENCY_WINDOW seconds.
//   - If the workflow has a non-completed step (excluding failed /
//     needs_update which require user intervention), exits 2 with a message
//     to stderr instructing Claude to continue the loop.
//   - Per (session_id, step_id) retry counter caps consecutive blocks at
//     MAX_RETRIES to prevent infinite loops.
//   - In any other case, exits 0 (silent no-op).
//
// Input: stdin JSON with { session_id, cwd, ... }
// Output:
//   exit 0 → Claude finishes turn normally
//   exit 2 → stderr fed to Claude as continuation instruction

import { existsSync, readdirSync } from "node:fs";
import { mkdir, readFile, stat, unlink, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

const RECENCY_WINDOW = Number.parseInt(
  process.env.EM_SDD_STOP_GUARD_RECENCY ?? "600",
  10,
);
const MAX_RETRIES = Number.parseInt(
  process.env.EM_SDD_STOP_GUARD_MAX_RETRIES ?? "3",
  10,
);

interface HookInput {
  session_id?: string;
  cwd?: string;
}

interface NextStep {
  id: string;
  status: string;
}

async function readStdin(): Promise<string> {
  const chunks: Uint8Array[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk as Uint8Array);
  }
  return Buffer.concat(chunks).toString("utf8");
}

function findSddYaml(cwd: string): string | null {
  const tasksDir = join(cwd, "doc", "tasks");
  if (!existsSync(tasksDir)) return null;

  let entries: string[];
  try {
    entries = readdirSync(tasksDir);
  } catch {
    return null;
  }

  for (const entry of entries) {
    const candidate = join(tasksDir, entry, "sdd.yaml");
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

// Minimal YAML parser tailored to sdd.yaml's `workflow:` array.
// Returns the first step whose status is not "completed", or null if all
// steps are completed (or workflow section is missing/malformed).
function findFirstNonCompleted(yamlContent: string): NextStep | null {
  const lines = yamlContent.split("\n");
  let inWorkflow = false;
  let currentId = "";

  for (const line of lines) {
    if (/^workflow:\s*$/.test(line)) {
      inWorkflow = true;
      continue;
    }
    if (inWorkflow && /^[a-zA-Z]/.test(line)) {
      break; // left workflow section (e.g. "requirements:" follows)
    }
    if (!inWorkflow) continue;

    const idMatch = /^ {2}- id:\s*(\S+)/.exec(line);
    if (idMatch) {
      currentId = idMatch[1].replace(/[",]/g, "");
      continue;
    }

    const statusMatch = /^ {4}status:\s*(\S+)/.exec(line);
    if (statusMatch && currentId) {
      const status = statusMatch[1].replace(/[",]/g, "");
      if (status !== "completed") {
        return { id: currentId, status };
      }
      currentId = "";
    }
  }
  return null;
}

function sanitize(s: string): string {
  return s.replace(/[^A-Za-z0-9_-]/g, "_");
}

async function readCounter(path: string): Promise<number> {
  if (!existsSync(path)) return 0;
  try {
    return Number.parseInt(await readFile(path, "utf8"), 10) || 0;
  } catch {
    return 0;
  }
}

function emitContinuationInstruction(sddYaml: string, next: NextStep): void {
  const lines = [
    `[em-sdd Stop hook] SDD workflow がまだ未完了です (step: ${next.id}, status: ${next.status})。`,
    "",
    "あなたは sdd オーケストレータとして起動しています。ターンを終わらせる前に、以下を必ず実行してください:",
    `  1. ${sddYaml} を Read し直す`,
    "  2. workflow の最初の status != completed ステップを特定する",
    "  3. Skill tool で対応する em-sdd:sdd-N-* skill を呼ぶ",
    "     (create-spec→sdd-1, create-plan→sdd-2, verify-plan→sdd-3,",
    "      implement→sdd-4, check→sdd-5, verify→sdd-6)",
    "",
    "ユーザーへの確認や終了報告は、全 step が completed になるまで挟まないこと。",
    `(この Stop hook は同じ step に対して最大 ${MAX_RETRIES} 回まで継続を強制します)`,
  ];
  console.error(lines.join("\n"));
}

async function main(): Promise<number> {
  let input: HookInput;
  try {
    input = JSON.parse(await readStdin()) as HookInput;
  } catch {
    return 0;
  }

  const cwd = input.cwd;
  if (!cwd || !existsSync(cwd)) return 0;

  const sddYaml = findSddYaml(cwd);
  if (!sddYaml) return 0;

  // Recency check
  let mtimeMs: number;
  try {
    mtimeMs = (await stat(sddYaml)).mtimeMs;
  } catch {
    return 0;
  }
  const ageSec = (Date.now() - mtimeMs) / 1000;
  if (ageSec > RECENCY_WINDOW) return 0;

  // Find first non-completed step
  let yamlContent: string;
  try {
    yamlContent = await readFile(sddYaml, "utf8");
  } catch {
    return 0;
  }
  const next = findFirstNonCompleted(yamlContent);
  if (!next) return 0;

  // User intervention required → don't auto-continue
  if (next.status === "failed" || next.status === "needs_update") return 0;

  // Retry guard (prevent infinite loop)
  const cacheDir = join(
    process.env.XDG_CACHE_HOME ?? join(homedir(), ".cache"),
    "em-sdd",
  );
  await mkdir(cacheDir, { recursive: true }).catch(() => {});

  const sessionId = input.session_id ?? "unknown";
  const counterFile = join(
    cacheDir,
    `stop-guard-${sanitize(sessionId)}-${sanitize(next.id)}`,
  );

  const count = (await readCounter(counterFile)) + 1;
  await writeFile(counterFile, String(count)).catch(() => {});

  if (count > MAX_RETRIES) {
    await unlink(counterFile).catch(() => {});
    return 0; // escape hatch
  }

  emitContinuationInstruction(sddYaml, next);
  return 2;
}

main()
  .then((code) => process.exit(code))
  .catch(() => process.exit(0));
