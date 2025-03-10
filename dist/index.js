#!/usr/bin/env node
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { parseArgs } from "node:util";
import kleur from "kleur";
const { bold, blue, red, yellow, dim, green } = kleur;
export class PyrightError extends Error {
    constructor(diagnostic, context) {
        super(diagnostic.message);
        this.diagnostic = diagnostic;
        this.context = context;
        this.name = "PyrightError";
        this.file = diagnostic.file;
        this.severity = diagnostic.severity;
        this.message = diagnostic.message;
        this.range = diagnostic.range;
        this.rule = diagnostic.rule;
    }
    formatError(contextLines = 2) {
        const output = [];
        // File location
        output.push(kleur.blue(`${this.file}:${this.range.start.line + 1}:${this.range.start.character + 1}`));
        // Context lines
        if (this.context.length) {
            const startLine = Math.max(0, this.range.start.line - contextLines);
            this.context.forEach((line, i) => {
                const lineNum = startLine + i;
                const prefix = lineNum === this.range.start.line ? ">" : " ";
                const lineNumStr = dim(`${lineNum + 1}`.padStart(3));
                output.push(`${prefix} ${lineNumStr} │ ${line}`);
                if (lineNum === this.range.start.line) {
                    const padding = " ".repeat(this.range.start.character);
                    const indicator = "^".repeat(this.range.end.character - this.range.start.character);
                    output.push(`      │ ${padding}${red(`${indicator} ${dim(this.rule)}`)}`);
                }
            });
            // Error message
            output.push(dim("      │"));
            output.push(` ${dim("help ~")} ${red(this.message)}`);
        }
        return output.join("\n");
    }
}
export class Pyright {
    async getContext(diagnostic, contextLines = 2) {
        try {
            const content = await readFile(diagnostic.file, "utf-8");
            const lines = content.split("\n");
            const startLine = Math.max(0, diagnostic.range.start.line - contextLines);
            const endLine = Math.min(lines.length, diagnostic.range.end.line + contextLines + 1);
            return lines.slice(startLine, endLine);
        }
        catch {
            return [];
        }
    }
    async check(files, options = []) {
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
                    const output = JSON.parse(stdout);
                    // Enhance diagnostics with context
                    const diagnosticsWithContext = await Promise.all(output.generalDiagnostics.map(async (diagnostic) => {
                        const context = await this.getContext(diagnostic);
                        return new PyrightError(diagnostic, context);
                    }));
                    resolve({
                        ...output,
                        generalDiagnostics: diagnosticsWithContext,
                    });
                }
                catch (error) {
                    reject(new Error(`Failed to parse pyright output: ${stderr || stdout}`));
                }
            });
        });
    }
    async checkFile(filePath, options = []) {
        return this.check(filePath, options);
    }
    async checkFiles(files, options = []) {
        return this.check(files, options);
    }
    async checkDirectory(dirPath, options = []) {
        return this.check(dirPath, options);
    }
}
function parseArguments() {
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
        if (result.generalDiagnostics.length > 0) {
            for (const diagnostic of result.generalDiagnostics) {
                if (diagnostic instanceof PyrightError) {
                    console.log(`\n${diagnostic.formatError(args.context)}`);
                }
            }
            if (args.showSummary) {
                console.log(`\n${formatSummary(result.summary)}`);
            }
            process.exit(1);
        }
        if (!args.quiet) {
            console.log("No errors found!");
        }
    }
    catch (error) {
        console.error("Error running pyright:", error);
        process.exit(1);
    }
}
function formatSummary(summary) {
    return `
${bold("Summary:")}
  Files analyzed   ${dim("»")} ${summary.filesAnalyzed}
  Errors          ${dim("»")} ${summary.errorCount ? red(summary.errorCount) : green(summary.errorCount)}
  Warnings        ${dim("»")} ${summary.warningCount
        ? yellow(summary.warningCount)
        : green(summary.warningCount)}
  Information     ${dim("»")} ${summary.informationCount
        ? blue(summary.informationCount)
        : green(summary.informationCount)}
  Time            ${dim("»")} ${bold(summary.timeInSec)}s
`.trim();
}
main().catch((error) => {
    console.error(error);
    process.exit(1);
});
