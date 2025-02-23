#!/usr/bin/env node
"use strict";
var __extends = (this && this.__extends) || (function () {
    var extendStatics = function (d, b) {
        extendStatics = Object.setPrototypeOf ||
            ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
            function (d, b) { for (var p in b) if (Object.prototype.hasOwnProperty.call(b, p)) d[p] = b[p]; };
        return extendStatics(d, b);
    };
    return function (d, b) {
        if (typeof b !== "function" && b !== null)
            throw new TypeError("Class extends value " + String(b) + " is not a constructor or null");
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    };
})();
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
var __spreadArray = (this && this.__spreadArray) || function (to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.Pyright = exports.PyrightError = void 0;
var node_child_process_1 = require("node:child_process");
var promises_1 = require("node:fs/promises");
var node_util_1 = require("node:util");
var kleur_1 = require("kleur");
var bold = kleur_1.default.bold, blue = kleur_1.default.blue, red = kleur_1.default.red, yellow = kleur_1.default.yellow, dim = kleur_1.default.dim, green = kleur_1.default.green;
var PyrightError = /** @class */ (function (_super) {
    __extends(PyrightError, _super);
    function PyrightError(diagnostic, context) {
        var _this = _super.call(this, diagnostic.message) || this;
        _this.diagnostic = diagnostic;
        _this.context = context;
        _this.name = "PyrightError";
        _this.file = diagnostic.file;
        _this.severity = diagnostic.severity;
        _this.message = diagnostic.message;
        _this.range = diagnostic.range;
        _this.rule = diagnostic.rule;
        return _this;
    }
    PyrightError.prototype.formatError = function (contextLines) {
        var _this = this;
        if (contextLines === void 0) { contextLines = 2; }
        var output = [];
        // File location
        output.push(kleur_1.default.blue("".concat(this.file, ":").concat(this.range.start.line + 1, ":").concat(this.range.start.character + 1)));
        // Context lines
        if (this.context.length) {
            var startLine_1 = Math.max(0, this.range.start.line - contextLines);
            this.context.forEach(function (line, i) {
                var lineNum = startLine_1 + i;
                var prefix = lineNum === _this.range.start.line ? ">" : " ";
                var lineNumStr = dim("".concat(lineNum + 1).padStart(3));
                output.push("".concat(prefix, " ").concat(lineNumStr, " \u2502 ").concat(line));
                if (lineNum === _this.range.start.line) {
                    var padding = " ".repeat(_this.range.start.character);
                    var indicator = "^".repeat(_this.range.end.character - _this.range.start.character);
                    output.push("      \u2502 ".concat(padding).concat(red("".concat(indicator, " ").concat(dim(_this.rule)))));
                }
            });
            // Error message
            output.push(dim("      │"));
            output.push(" ".concat(dim("help ~"), " ").concat(red(this.message)));
        }
        return output.join("\n");
    };
    return PyrightError;
}(Error));
exports.PyrightError = PyrightError;
var Pyright = /** @class */ (function () {
    function Pyright() {
    }
    Pyright.prototype.getContext = function (diagnostic_1) {
        return __awaiter(this, arguments, void 0, function (diagnostic, contextLines) {
            var content, lines, startLine, endLine, _a;
            if (contextLines === void 0) { contextLines = 2; }
            return __generator(this, function (_b) {
                switch (_b.label) {
                    case 0:
                        _b.trys.push([0, 2, , 3]);
                        return [4 /*yield*/, (0, promises_1.readFile)(diagnostic.file, "utf-8")];
                    case 1:
                        content = _b.sent();
                        lines = content.split("\n");
                        startLine = Math.max(0, diagnostic.range.start.line - contextLines);
                        endLine = Math.min(lines.length, diagnostic.range.end.line + contextLines + 1);
                        return [2 /*return*/, lines.slice(startLine, endLine)];
                    case 2:
                        _a = _b.sent();
                        return [2 /*return*/, []];
                    case 3: return [2 /*return*/];
                }
            });
        });
    };
    Pyright.prototype.check = function (files_1) {
        return __awaiter(this, arguments, void 0, function (files, options) {
            var fileList, args;
            var _this = this;
            if (options === void 0) { options = []; }
            return __generator(this, function (_a) {
                fileList = Array.isArray(files) ? files : [files];
                args = __spreadArray(__spreadArray(["--outputjson"], options, true), fileList, true);
                return [2 /*return*/, new Promise(function (resolve, reject) {
                        var pyright = (0, node_child_process_1.spawn)("pyright", args);
                        var stdout = "";
                        var stderr = "";
                        pyright.stdout.on("data", function (data) {
                            stdout += data;
                        });
                        pyright.stderr.on("data", function (data) {
                            stderr += data;
                        });
                        pyright.on("close", function (code) { return __awaiter(_this, void 0, void 0, function () {
                            var output, diagnosticsWithContext, error_1;
                            var _this = this;
                            return __generator(this, function (_a) {
                                switch (_a.label) {
                                    case 0:
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
                                            return [2 /*return*/];
                                        }
                                        _a.label = 1;
                                    case 1:
                                        _a.trys.push([1, 3, , 4]);
                                        output = JSON.parse(stdout);
                                        return [4 /*yield*/, Promise.all(output.generalDiagnostics.map(function (diagnostic) { return __awaiter(_this, void 0, void 0, function () {
                                                var context;
                                                return __generator(this, function (_a) {
                                                    switch (_a.label) {
                                                        case 0: return [4 /*yield*/, this.getContext(diagnostic)];
                                                        case 1:
                                                            context = _a.sent();
                                                            return [2 /*return*/, new PyrightError(diagnostic, context)];
                                                    }
                                                });
                                            }); }))];
                                    case 2:
                                        diagnosticsWithContext = _a.sent();
                                        resolve(__assign(__assign({}, output), { generalDiagnostics: diagnosticsWithContext }));
                                        return [3 /*break*/, 4];
                                    case 3:
                                        error_1 = _a.sent();
                                        reject(new Error("Failed to parse pyright output: ".concat(stderr || stdout)));
                                        return [3 /*break*/, 4];
                                    case 4: return [2 /*return*/];
                                }
                            });
                        }); });
                    })];
            });
        });
    };
    Pyright.prototype.checkFile = function (filePath_1) {
        return __awaiter(this, arguments, void 0, function (filePath, options) {
            if (options === void 0) { options = []; }
            return __generator(this, function (_a) {
                return [2 /*return*/, this.check(filePath, options)];
            });
        });
    };
    Pyright.prototype.checkFiles = function (files_1) {
        return __awaiter(this, arguments, void 0, function (files, options) {
            if (options === void 0) { options = []; }
            return __generator(this, function (_a) {
                return [2 /*return*/, this.check(files, options)];
            });
        });
    };
    Pyright.prototype.checkDirectory = function (dirPath_1) {
        return __awaiter(this, arguments, void 0, function (dirPath, options) {
            if (options === void 0) { options = []; }
            return __generator(this, function (_a) {
                return [2 /*return*/, this.check(dirPath, options)];
            });
        });
    };
    return Pyright;
}());
exports.Pyright = Pyright;
function parseArguments() {
    var _a, _b;
    var _c = (0, node_util_1.parseArgs)({
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
    }), values = _c.values, positionals = _c.positionals;
    return {
        args: {
            debug: values.debug,
            verbose: (_b = (_a = values.verbose) === null || _a === void 0 ? void 0 : _a.length) !== null && _b !== void 0 ? _b : 0,
            quiet: values.quiet,
            context: values.context ? Number.parseInt(values.context, 10) : 2,
            showSummary: values["show-summary"],
            help: values.help,
        },
        remaining: positionals,
    };
}
function main() {
    return __awaiter(this, void 0, void 0, function () {
        var _a, args, remaining, pyright, result, _i, _b, diagnostic, error_2;
        return __generator(this, function (_c) {
            switch (_c.label) {
                case 0:
                    _a = parseArguments(), args = _a.args, remaining = _a.remaining;
                    if (args.help) {
                        console.log("\nUsage: pyright-pretty [options] [file ...]\n\nOptions:\n  -v, --verbose           Increase verbosity level\n  -q, --quiet            Suppress all output except errors\n  -c, --context NUM      Number of context lines (default: 2)\n  --show-summary         Show summary after errors\n  --debug                Enable debug logging\n  --help                 Show this help message\n    ");
                        process.exit(0);
                    }
                    pyright = new Pyright();
                    _c.label = 1;
                case 1:
                    _c.trys.push([1, 3, , 4]);
                    return [4 /*yield*/, pyright.check(remaining)];
                case 2:
                    result = _c.sent();
                    if (result.generalDiagnostics.length > 0) {
                        for (_i = 0, _b = result.generalDiagnostics; _i < _b.length; _i++) {
                            diagnostic = _b[_i];
                            if (diagnostic instanceof PyrightError) {
                                console.log("\n".concat(diagnostic.formatError(args.context)));
                            }
                        }
                        if (args.showSummary) {
                            console.log("\n".concat(formatSummary(result.summary)));
                        }
                        process.exit(1);
                    }
                    if (!args.quiet) {
                        console.log("No errors found!");
                    }
                    return [3 /*break*/, 4];
                case 3:
                    error_2 = _c.sent();
                    console.error("Error running pyright:", error_2);
                    process.exit(1);
                    return [3 /*break*/, 4];
                case 4: return [2 /*return*/];
            }
        });
    });
}
function formatSummary(summary) {
    return "\n".concat(bold("Summary:"), "\n  Files analyzed   ").concat(dim("»"), " ").concat(summary.filesAnalyzed, "\n  Errors          ").concat(dim("»"), " ").concat(summary.errorCount ? red(summary.errorCount) : green(summary.errorCount), "\n  Warnings        ").concat(dim("»"), " ").concat(summary.warningCount
        ? yellow(summary.warningCount)
        : green(summary.warningCount), "\n  Information     ").concat(dim("»"), " ").concat(summary.informationCount
        ? blue(summary.informationCount)
        : green(summary.informationCount), "\n  Time            ").concat(dim("»"), " ").concat(bold(summary.timeInSec), "s\n").trim();
}
main().catch(function (error) {
    console.error(error);
    process.exit(1);
});
