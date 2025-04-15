#!/usr/bin/env node
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import kleur from "kleur";
const { bold, blue, red, yellow, dim, green } = kleur;

const dimRed = (s: string) => dim(red(s));

export interface Location {
  line: number;
  character: number;
}

export interface Range {
  start: Location;
  end: Location;
}

export interface PyrightDiagnostic {
  file: string;
  severity: "error" | "warning" | "information";
  message: string;
  range: Range | undefined;
  rule: string;
}

export interface PyrightSummary {
  filesAnalyzed: number;
  errorCount: number;
  warningCount: number;
  informationCount: number;
  timeInSec: number;
}

export interface PyrightOutput {
  version: string;
  time: string;
  generalDiagnostics: PyrightDiagnostic[];
  summary: PyrightSummary;
}

function pushHelp(
  output: string[],
  message: string,
  color: (s: string) => string = red
) {
  output.push(` ${dim("help ~")} ${color(message)}`);
}

function pushError(output: string[], message: string) {
  output.push(`     ${red("^ ")} ${dimRed(message)}`);
}

function buildIndicator(start: number, length: number, message = "") {
  const padding = " ".repeat(start);
  const indicator = red("^".repeat(length));
  return `${padding}${indicator}${message ? ` ${dimRed(message)}` : ""}`;
}

function pushFile(output: string[], diagnostic: PyrightDiagnostic) {
  let formatted = "";
  if (diagnostic.range !== undefined) {
    const startLine = diagnostic.range.start.line + 1;
    const startChar = diagnostic.range.start.character + 1;
    formatted = blue(`${diagnostic.file}:${startLine}:${startChar}`);
  } else {
    formatted = blue(diagnostic.file);
  }

  const formattedRule = diagnostic.rule ? ` → ${dimRed(diagnostic.rule)}` : "";
  const formattedSeverity =
    diagnostic.severity === "error"
      ? red("error")
      : diagnostic.severity === "warning"
      ? yellow("warning")
      : green("information");

  output.push(`${formattedSeverity} ${formatted}${formattedRule}`);
}

function pushLine(output: string[], line: string) {
  output.push(line);
}

function pushNumberedLine(
  output: string[],
  line: string,
  lineNum: number,
  indicated = false
) {
  output.push(
    `${indicated ? ">" : " "}${dim(`${lineNum + 1}`.padStart(4))} │ ${line}`
  );
}
function pushContext(
  output: string[],
  context: string | string[] = "",
  color: (s: string) => string = (s) => s
) {
  if (typeof context === "string") {
    output.push(`      │ ${color(context)}`);
  } else {
    for (const line of context) {
      output.push(`      │ ${color(line)}`);
    }
  }
}

export class PyrightError extends Error implements PyrightDiagnostic {
  readonly file: string;
  readonly severity: "error" | "warning" | "information";
  readonly message: string;
  readonly range: Range | undefined;
  readonly rule: string;

  constructor(
    public readonly diagnostic: PyrightDiagnostic,
    public readonly context: string[]
  ) {
    super(diagnostic.message);
    this.name = "PyrightError";
    this.file = diagnostic.file;
    this.severity = diagnostic.severity;
    this.message = diagnostic.message;
    this.range = diagnostic.range;
    this.rule = diagnostic.rule;
  }

  formatError(contextLines = 2): string {
    const output: string[] = [];

    if (this.range === undefined) {
      // file-level errors
      pushFile(output, this);

      switch (this.rule) {
        case "reportImportCycles": {
          const errorLines = this.message.split("\n");
          const helpMsg = errorLines[0];
          const cycleImports = errorLines.slice(1);

          for (const cycleImport of cycleImports) {
            output.push(`>     │     ${cycleImport.trim()}`);
          }
          pushHelp(output, helpMsg, kleur.dim);
          break;
        }

        default: {
          pushError(output, this.message);
          pushHelp(output, this.rule, kleur.dim);
          pushLine(output, `---> ${this.rule} needs custom handling`);
        }
      }
      return output.join("\n");
    }

    // File location
    pushFile(output, this);

    // Context lines
    if (this.context.length) {
      const startLine = Math.max(0, this.range.start.line - contextLines);

      this.context.forEach((line, i) => {
        if (this.range === undefined) return;

        const lineNum = startLine + i;
        const isErrorStartLine = lineNum === this.range.start.line;
        const isWithinErrorLineRange =
          lineNum >= this.range.start.line && lineNum <= this.range.end.line;

        let formattedLine = line;
        if (isWithinErrorLineRange) {
          const startChar =
            lineNum === this.range.start.line ? this.range.start.character : 0;
          const endChar =
            lineNum === this.range.end.line
              ? this.range.end.character
              : line.length; // Highlight to end if start/middle of multi-line

          const before = line.substring(0, startChar);
          const highlighted = red(line.substring(startChar, endChar));
          const after = line.substring(endChar);
          formattedLine = before + highlighted + after;
        }

        pushNumberedLine(
          output,
          formattedLine,
          lineNum,
          isWithinErrorLineRange
        );

        // Indicator logic
        const isSingleLineError = this.range.start.line === this.range.end.line;

        // Single-line error: Underline the range on the start line
        if (isErrorStartLine && isSingleLineError) {
          const rangeLength = Math.max(
            1,
            this.range.end.character - this.range.start.character
          );

          pushContext(
            output,
            buildIndicator(this.range.start.character, rangeLength, this.rule)
          );
        }

        // Multi-line error: Place caret under the end character on the end line
        if (lineNum === this.range.end.line && !isSingleLineError) {
          // Subtract 1 from end character for correct alignment
          pushContext(
            output,
            buildIndicator(this.range.end.character - 1, 1, this.rule)
          );
        }
      });

      // Error message
      pushHelp(output, this.message);
    }

    return output.join("\n");
  }
}

export class Pyright {
  private async getContext(
    diagnostic: PyrightDiagnostic,
    contextLines = 2
  ): Promise<string[]> {
    try {
      if (!diagnostic.range) {
        return [];
      }

      const content = await readFile(diagnostic.file, "utf-8");
      const lines = content.split("\n");
      const startLine = Math.max(0, diagnostic.range.start.line - contextLines);
      const endLine = Math.min(
        lines.length,
        diagnostic.range.end.line + contextLines + 1
      );
      return lines.slice(startLine, endLine);
    } catch {
      return [];
    }
  }

  async check(
    files: string | string[],
    options: string[] = []
  ): Promise<PyrightOutput> {
    const fileList = Array.isArray(files) ? files : [files];
    const args = ["--outputjson", ...options, ...fileList];

    return new Promise((resolve, reject) => {
      const pyright = spawn("pyright", args);
      let stdout = "";
      let stderr = "";

      pyright.stdout.on("data", (data) => {
        stdout += data;
      });

      pyright.stderr.on("data", (data) => {
        stderr += data;
      });

      pyright.on("close", async (code) => {
        if (code === 0) {
          resolve({
            version: "",
            time: "",
            generalDiagnostics: [],
            summary: {
              filesAnalyzed: fileList.length,
              errorCount: 0,
              warningCount: 0,
              informationCount: 0,
              timeInSec: 0,
            },
          });
          return;
        }

        try {
          const output: PyrightOutput = JSON.parse(stdout);

          // Enhance diagnostics with context
          const diagnosticsWithContext = await Promise.all(
            output.generalDiagnostics.map(async (diagnostic) => {
              const context = await this.getContext(diagnostic);
              return new PyrightError(diagnostic, context);
            })
          );

          resolve({
            ...output,
            generalDiagnostics: diagnosticsWithContext,
          });
        } catch (error) {
          reject(
            new Error(`Failed to parse pyright output: ${stderr || stdout}`)
          );
        }
      });
    });
  }

  async checkFile(
    filePath: string,
    options: string[] = []
  ): Promise<PyrightOutput> {
    return this.check(filePath, options);
  }

  async checkFiles(
    files: string[],
    options: string[] = []
  ): Promise<PyrightOutput> {
    return this.check(files, options);
  }

  async checkDirectory(
    dirPath: string,
    options: string[] = []
  ): Promise<PyrightOutput> {
    return this.check(dirPath, options);
  }
}

interface PyrightArgs {
  debug?: boolean;
  verbose?: number;
  quiet?: boolean;
  context?: number;
  showSummary?: boolean;
  help?: boolean;
}

function parseArguments(): { args: PyrightArgs; remaining: string[] } {
  const { values, positionals } = parseArgs({
    options: {
      debug: { type: "boolean" },
      verbose: { type: "string", short: "v", multiple: true },
      quiet: { type: "boolean", short: "q" },
      context: { type: "string", short: "c" },
      "show-summary": { type: "boolean" },
      global: { type: "boolean", short: "g" },
      help: { type: "boolean" },
    },
    allowPositionals: true,
  });

  return {
    args: {
      debug: values.debug,
      verbose: values.verbose?.length ?? 0,
      quiet: values.quiet,
      context: values.context ? Number.parseInt(values.context, 10) : 2,
      showSummary: values["show-summary"],
      help: values.help,
    },
    remaining: positionals,
  };
}

async function main() {
  const { args, remaining } = parseArguments();
  if (args.help) {
    console.log(`
Usage: pyright-pretty [options] [file ...]

Options:
  -v, --verbose           Increase verbosity level
  -q, --quiet            Suppress all output except errors
  -c, --context NUM      Number of context lines (default: 2)
  --show-summary         Show summary after errors
  --debug                Enable debug logging
  --help                 Show this help message
    `);
    process.exit(0);
  }

  const pyright = new Pyright();

  try {
    const result = await pyright.check(remaining);

    if (args.debug) {
      console.log(JSON.stringify(result, null, 2));
    }

    if (result.generalDiagnostics.length > 0) {
      for (const diagnostic of result.generalDiagnostics) {
        if (diagnostic instanceof PyrightError) {
          console.log(`\n${diagnostic.formatError(args.context)}`);
        } else {
          console.error(`unknown error: ${JSON.stringify(diagnostic)}`);
        }
      }
      console.log("");
      if (args.showSummary) {
        console.log(`\n${formatSummary(result.summary)}`);
      }
      process.exit(1);
    }

    if (!args.quiet) {
      console.log("No errors found!");
    }
  } catch (error) {
    console.error("Error running pyright:", error);
    process.exit(1);
  }
}

function formatSummary(summary: PyrightSummary): string {
  return `
${bold("Summary:")}
  Files analyzed   ${dim("»")} ${summary.filesAnalyzed}
  Errors          ${dim("»")} ${
    summary.errorCount ? red(summary.errorCount) : green(summary.errorCount)
  }
  Warnings        ${dim("»")} ${
    summary.warningCount
      ? yellow(summary.warningCount)
      : green(summary.warningCount)
  }
  Information     ${dim("»")} ${
    summary.informationCount
      ? blue(summary.informationCount)
      : green(summary.informationCount)
  }
  Time            ${dim("»")} ${bold(summary.timeInSec)}s
`.trim();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
