#!/usr/bin/env node
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
export declare class PyrightError extends Error implements PyrightDiagnostic {
    readonly diagnostic: PyrightDiagnostic;
    readonly context: string[];
    readonly file: string;
    readonly severity: "error" | "warning" | "information";
    readonly message: string;
    readonly range: Range | undefined;
    readonly rule: string;
    constructor(diagnostic: PyrightDiagnostic, context: string[]);
    formatError(contextLines?: number): string;
}
export declare class Pyright {
    private getContext;
    check(files: string | string[], options?: string[]): Promise<PyrightOutput>;
    checkFile(filePath: string, options?: string[]): Promise<PyrightOutput>;
    checkFiles(files: string[], options?: string[]): Promise<PyrightOutput>;
    checkDirectory(dirPath: string, options?: string[]): Promise<PyrightOutput>;
}
