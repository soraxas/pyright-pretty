from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from enum import Enum
from functools import reduce, singledispatchmethod
from inspect import cleandoc
from pathlib import Path
from typing import Any, ClassVar, Literal, Self, TextIO

from pydantic import BaseModel, Field
from rich.console import Console
from rich.logging import RichHandler

logger = logging.getLogger(__name__)

console = Console()
InstallersT = Literal["bun", "yarn", "npm"]


class PyrightDiagnosticRule(str, Enum):
    strictListInference = """When inferring the type of a list, use strict type assumptions. For example, the expression `[1, 'a', 3.4]` could be inferred to be of type `list[Any]` or `list[int | str | float]`. If this setting is true, it will use the latter (stricter) type. The default value for this setting is `false`."""
    strictDictionaryInference = """When inferring the type of a dictionary’s keys and values, use strict type assumptions. For example, the expression `{'a': 1, 'b': 'a'}` could be inferred to be of type `dict[str, Any]` or `dict[str, int | str]`. If this setting is true, it will use the latter (stricter) type. The default value for this setting is `false`."""
    strictSetInference = """When inferring the type of a set, use strict type assumptions. For example, the expression `{1, 'a', 3.4}` could be inferred to be of type `set[Any]` or `set[int | str | float]`. If this setting is true, it will use the latter (stricter) type. The default value for this setting is `false`."""
    analyzeUnannotatedFunctions = """Analyze and report errors for functions and methods that have no type annotations for input parameters or return types. The default value for this setting is `true`."""
    strictParameterNoneValue = """PEP 484 indicates that when a function parameter is assigned a default value of None, its type should implicitly be Optional even if the explicit type is not. When enabled, this rule requires that parameter type annotations use Optional explicitly in this case. The default value for this setting is `true`."""
    enableTypeIgnoreComments = """PEP 484 defines support for "# type: ignore" comments. This switch enables or disables support for these comments. The default value for this setting is `true`. This does not affect "# pyright: ignore" comments."""
    deprecateTypingAliases = """PEP 585 indicates that aliases to types in standard collections that were introduced solely to support generics are deprecated as of Python 3.9. This switch controls whether these are treated as deprecated. This applies only when pythonVersion is 3.9 or newer. The default value for this setting is `false` but may be switched to `true` in the future."""
    enableReachabilityAnalysis = """If enabled, code that is determined to be unreachable by type analysis is reported using a tagged hint. This setting does not affect code that is determined to be unreachable regardless of type analysis; such code is always reported as unreachable. This setting also has no effect when when using the command-line version of pyright because it never emits tagged hints for unreachable code."""
    enableExperimentalFeatures = """Enables a set of experimental (mostly undocumented) features that correspond to proposed or exploratory changes to the Python typing standard. These features will likely change or be removed, so they should not be used except for experimentation purposes. The default value for this setting is `false`."""
    disableBytesTypePromotions = """Disables legacy behavior where `bytearray` and `memoryview` are considered subtypes of `bytes`. [PEP 688](https://peps.python.org/pep-0688/#no-special-meaning-for-bytes) deprecates this behavior, but this switch is provided to restore the older behavior. The default value for this setting is `true`."""
    reportGeneralTypeIssues = """Generate or suppress diagnostics for general type inconsistencies, unsupported operations, argument/parameter mismatches, etc. This covers all of the basic type-checking rules not covered by other rules. It does not include syntax errors. The default value for this setting is `"error"`."""
    reportPropertyTypeMismatch = """Generate or suppress diagnostics for properties where the type of the value passed to the setter is not assignable to the value returned by the getter. Such mismatches violate the intended use of properties, which are meant to act like variables. The default value for this setting is `"none"`."""
    reportFunctionMemberAccess = """Generate or suppress diagnostics for non-standard member accesses for functions. The default value for this setting is `"error"`."""
    reportMissingImports = """Generate or suppress diagnostics for imports that have no corresponding imported python file or type stub file. The default value for this setting is `"error"`."""
    reportMissingModuleSource = """Generate or suppress diagnostics for imports that have no corresponding source file. This happens when a type stub is found, but the module source file was not found, indicating that the code may fail at runtime when using this execution environment. Type checking will be done using the type stub. The default value for this setting is `"warning"`."""
    reportInvalidTypeForm = """Generate or suppress diagnostics for type annotations that use invalid type expression forms or are semantically invalid. The default value for this setting is `"error"`."""
    reportMissingTypeStubs = """Generate or suppress diagnostics for imports that have no corresponding type stub file (either a typeshed file or a custom type stub). The type checker requires type stubs to do its best job at analysis. The default value for this setting is `"none"`. Note that there is a corresponding quick fix for this diagnostics that let you generate custom type stub to improve editing experiences."""
    reportImportCycles = """Generate or suppress diagnostics for cyclical import chains. These are not errors in Python, but they do slow down type analysis and often hint at architectural layering issues. Generally, they should be avoided. The default value for this setting is `"none"`. Note that there are import cycles in the typeshed stdlib typestub files that are ignored by this setting."""
    reportUnusedImport = """Generate or suppress diagnostics for an imported symbol that is not referenced within that file. The default value for this setting is `"none"`."""
    reportUnusedClass = """Generate or suppress diagnostics for a class with a private name (starting with an underscore) that is not accessed. The default value for this setting is `"none"`."""
    reportUnusedFunction = """Generate or suppress diagnostics for a function or method with a private name (starting with an underscore) that is not accessed. The default value for this setting is `"none"`."""
    reportUnusedVariable = """Generate or suppress diagnostics for a variable that is not accessed. The default value for this setting is `"none"`. Variables whose names begin with an underscore are exempt from this check."""
    reportDuplicateImport = """Generate or suppress diagnostics for an imported symbol or module that is imported more than once. The default value for this setting is `"none"`."""
    reportWildcardImportFromLibrary = """Generate or suppress diagnostics for a wildcard import from an external library. The use of this language feature is highly discouraged and can result in bugs when the library is updated. The default value for this setting is `"warning"`."""
    reportAbstractUsage = """Generate or suppress diagnostics for the attempted instantiate an abstract or protocol class or use of an abstract method. The default value for this setting is `"error"`."""
    reportArgumentType = """Generate or suppress diagnostics for argument type incompatibilities when evaluating a call expression. The default value for this setting is `"error"`."""
    reportAssertTypeFailure = """Generate or suppress diagnostics for a type mismatch detected by the `typing.assert_type` call. The default value for this setting is `"error"`."""
    reportAssignmentType = """Generate or suppress diagnostics for assignment type incompatibility. The default value for this setting is `"error"`."""
    reportAttributeAccessIssue = """Generate or suppress diagnostics related to attribute accesses. The default value for this setting is `"error"`."""
    reportCallIssue = """Generate or suppress diagnostics related to call expressions and arguments passed to a call target. The default value for this setting is `"error"`."""
    reportInconsistentOverload = """Generate or suppress diagnostics for an overloaded function that has overload signatures that are inconsistent with each other or with the implementation. The default value for this setting is `"error"`."""
    reportIndexIssue = """Generate or suppress diagnostics related to index operations and expressions. The default value for this setting is `"error"`."""
    reportInvalidTypeArguments = """Generate or suppress diagnostics for invalid type argument usage. The default value for this setting is `"error"`."""
    reportNoOverloadImplementation = """Generate or suppress diagnostics for an overloaded function or method if the implementation is not provided. The default value for this setting is `"error"`."""
    reportOperatorIssue = """Generate or suppress diagnostics related to the use of unary or binary operators (like `*` or `not`). The default value for this setting is `"error"`."""
    reportOptionalSubscript = """Generate or suppress diagnostics for an attempt to subscript (index) a variable with an Optional type. The default value for this setting is `"error"`."""
    reportOptionalMemberAccess = """Generate or suppress diagnostics for an attempt to access a member of a variable with an Optional type. The default value for this setting is `"error"`."""
    reportOptionalCall = """Generate or suppress diagnostics for an attempt to call a variable with an Optional type. The default value for this setting is `"error"`."""
    reportOptionalIterable = """Generate or suppress diagnostics for an attempt to use an Optional type as an iterable value (e.g. within a `for` statement). The default value for this setting is `"error"`."""
    reportOptionalContextManager = """Generate or suppress diagnostics for an attempt to use an Optional type as a context manager (as a parameter to a `with` statement). The default value for this setting is `"error"`."""
    reportOptionalOperand = """Generate or suppress diagnostics for an attempt to use an Optional type as an operand to a unary operator (like `~` or `not`) or the left-hand operator of a binary operator (like `*`, `==`, `or`). The default value for this setting is `"error"`."""
    reportRedeclaration = """Generate or suppress diagnostics for a symbol that has more than one type declaration. The default value for this setting is `"error"`."""
    reportReturnType = """Generate or suppress diagnostics related to function return type compatibility. The default value for this setting is `"error"`."""
    reportTypedDictNotRequiredAccess = """Generate or suppress diagnostics for an attempt to access a non-required field within a TypedDict without first checking whether it is present. The default value for this setting is `"error"`."""
    reportUntypedFunctionDecorator = """Generate or suppress diagnostics for function decorators that have no type annotations. These obscure the function type, defeating many type analysis features. The default value for this setting is `"none"`."""
    reportUntypedClassDecorator = """Generate or suppress diagnostics for class decorators that have no type annotations. These obscure the class type, defeating many type analysis features. The default value for this setting is `"none"`."""
    reportUntypedBaseClass = """Generate or suppress diagnostics for base classes whose type cannot be determined statically. These obscure the class type, defeating many type analysis features. The default value for this setting is `"none"`."""
    reportUntypedNamedTuple = """Generate or suppress diagnostics when “namedtuple” is used rather than “NamedTuple”. The former contains no type information, whereas the latter does. The default value for this setting is `"none"`."""
    reportPrivateUsage = """Generate or suppress diagnostics for incorrect usage of private or protected variables or functions. Protected class members begin with a single underscore (“_”) and can be accessed only by subclasses. Private class members begin with a double underscore but do not end in a double underscore and can be accessed only within the declaring class. Variables and functions declared outside of a class are considered private if their names start with either a single or double underscore, and they cannot be accessed outside of the declaring module. The default value for this setting is `"none"`."""
    reportTypeCommentUsage = """Prior to Python 3.5, the grammar did not support type annotations, so types needed to be specified using “type comments”. Python 3.5 eliminated the need for function type comments, and Python 3.6 eliminated the need for variable type comments. Future versions of Python will likely deprecate all support for type comments. If enabled, this check will flag any type comment usage unless it is required for compatibility with the specified language version. The default value for this setting is `"none"`."""
    reportPrivateImportUsage = """Generate or suppress diagnostics for use of a symbol from a "py.typed" module that is not meant to be exported from that module. The default value for this setting is `"error"`."""
    reportConstantRedefinition = """Generate or suppress diagnostics for attempts to redefine variables whose names are all-caps with underscores and numerals. The default value for this setting is `"none"`."""
    reportDeprecated = """Generate or suppress diagnostics for use of a class or function that has been marked as deprecated. The default value for this setting is `"none"`."""
    reportIncompatibleMethodOverride = """Generate or suppress diagnostics for methods that override a method of the same name in a base class in an incompatible manner (wrong number of parameters, incompatible parameter types, or incompatible return type). The default value for this setting is `"error"`."""
    reportIncompatibleVariableOverride = """Generate or suppress diagnostics for class variable declarations that override a symbol of the same name in a base class with a type that is incompatible with the base class symbol type. The default value for this setting is `"error"`."""
    reportInconsistentConstructor = """Generate or suppress diagnostics when an `__init__` method signature is inconsistent with a `__new__` signature. The default value for this setting is `"none"`."""
    reportOverlappingOverload = """Generate or suppress diagnostics for function overloads that overlap in signature and obscure each other or have incompatible return types. The default value for this setting is `"error"`."""
    reportPossiblyUnboundVariable = """Generate or suppress diagnostics for variables that are possibly unbound on some code paths. The default value for this setting is `"error"`."""
    reportMissingSuperCall = """Generate or suppress diagnostics for `__init__`, `__init_subclass__`, `__enter__` and `__exit__` methods in a subclass that fail to call through to the same-named method on a base class. The default value for this setting is `"none"`."""
    reportUninitializedInstanceVariable = """Generate or suppress diagnostics for instance variables within a class that are not initialized or declared within the class body or the `__init__` method. The default value for this setting is `"none"`."""
    reportInvalidStringEscapeSequence = """Generate or suppress diagnostics for invalid escape sequences used within string literals. The Python specification indicates that such sequences will generate a syntax error in future versions. The default value for this setting is `"warning"`."""
    reportUnknownParameterType = """Generate or suppress diagnostics for input or return parameters for functions or methods that have an unknown type. The default value for this setting is `"none"`."""
    reportUnknownArgumentType = """Generate or suppress diagnostics for call arguments for functions or methods that have an unknown type. The default value for this setting is `"none"`."""
    reportUnknownLambdaType = """Generate or suppress diagnostics for input or return parameters for lambdas that have an unknown type. The default value for this setting is `"none"`."""
    reportUnknownVariableType = """Generate or suppress diagnostics for variables that have an unknown type. The default value for this setting is `"none"`."""
    reportUnknownMemberType = """Generate or suppress diagnostics for class or instance variables that have an unknown type. The default value for this setting is `"none"`."""
    reportMissingParameterType = """Generate or suppress diagnostics for input parameters for functions or methods that are missing a type annotation. The `self` and `cls` parameters used within methods are exempt from this check. The default value for this setting is `"none"`."""
    reportMissingTypeArgument = """Generate or suppress diagnostics when a generic class is used without providing explicit or implicit type arguments. The default value for this setting is `"none"`."""
    reportInvalidTypeVarUse = """Generate or suppress diagnostics when a TypeVar is used inappropriately (e.g. if a TypeVar appears only once) within a generic function signature. The default value for this setting is `"warning"`."""
    reportCallInDefaultInitializer = """Generate or suppress diagnostics for function calls, list expressions, set expressions, or dictionary expressions within a default value initialization expression. Such calls can mask expensive operations that are performed at module initialization time. The default value for this setting is `"none"`."""
    reportUnnecessaryIsInstance = """Generate or suppress diagnostics for `isinstance` or `issubclass` calls where the result is statically determined to be always true or always false. Such calls are often indicative of a programming error. The default value for this setting is `"none"`."""
    reportUnnecessaryCast = """Generate or suppress diagnostics for `cast` calls that are statically determined to be unnecessary. Such calls are sometimes indicative of a programming error. The default value for this setting is `"none"`."""
    reportUnnecessaryComparison = """Generate or suppress diagnostics for `==` or `!=` comparisons or other conditional expressions that are statically determined to always evaluate to False or True. Such comparisons are sometimes indicative of a programming error. The default value for this setting is `"none"`. Also reports `case` clauses in a `match` statement that can be statically determined to never match (with exception of the `_` wildcard pattern, which is exempted)."""
    reportUnnecessaryContains = """Generate or suppress diagnostics for `in` operations that are statically determined to always evaluate to False or True. Such operations are sometimes indicative of a programming error. The default value for this setting is `"none"`."""
    reportAssertAlwaysTrue = """Generate or suppress diagnostics for `assert` statement that will provably always assert because its first argument is a parenthesized tuple (for example, `assert (v > 0, "Bad value")` when the intent was probably `assert v > 0, "Bad value"`). This is a common programming error. The default value for this setting is `"warning"`."""
    reportSelfClsParameterName = """Generate or suppress diagnostics for a missing or misnamed “self” parameter in instance methods and “cls” parameter in class methods. Instance methods in metaclasses (classes that derive from “type”) are allowed to use “cls” for instance methods. The default value for this setting is `"warning"`."""
    reportImplicitStringConcatenation = """Generate or suppress diagnostics for two or more string literals that follow each other, indicating an implicit concatenation. This is considered a bad practice and often masks bugs such as missing commas. The default value for this setting is `"none"`."""
    reportUndefinedVariable = """Generate or suppress diagnostics for undefined variables. The default value for this setting is `"error"`."""
    reportUnboundVariable = """Generate or suppress diagnostics for unbound variables. The default value for this setting is `"error"`."""
    reportUnhashable = """Generate or suppress diagnostics for the use of an unhashable object in a container that requires hashability. The default value for this setting is `"error"`."""
    reportInvalidStubStatement = """Generate or suppress diagnostics for statements that are syntactically correct but have no purpose within a type stub file. The default value for this setting is `"none"`."""
    reportIncompleteStub = """Generate or suppress diagnostics for a module-level `__getattr__` call in a type stub file, indicating that it is incomplete. The default value for this setting is `"none"`."""
    reportUnsupportedDunderAll = """Generate or suppress diagnostics for statements that define or manipulate `__all__` in a way that is not allowed by a static type checker, thus rendering the contents of `__all__` to be unknown or incorrect. Also reports names within the `__all__` list that are not present in the module namespace. The default value for this setting is `"warning"`."""
    reportUnusedCallResult = """Generate or suppress diagnostics for call statements whose return value is not used in any way and is not None. The default value for this setting is `"none"`."""
    reportUnusedCoroutine = """Generate or suppress diagnostics for call statements whose return value is not used in any way and is a Coroutine. This identifies a common error where an `await` keyword is mistakenly omitted. The default value for this setting is `"error"`."""
    reportUnusedExcept = """Generate or suppress diagnostics for an `except` clause that will never be reached. The default value for this setting is `"error"`."""
    reportUnusedExpression = """Generate or suppress diagnostics for simple expressions whose results are not used in any way. The default value for this setting is `"none"`."""
    reportUnnecessaryTypeIgnoreComment = """Generate or suppress diagnostics for a `# type: ignore` or `# pyright: ignore` comment that would have no effect if removed. The default value for this setting is `"none"`."""
    reportMatchNotExhaustive = """Generate or suppress diagnostics for a `match` statement that does not provide cases that exhaustively match against all potential types of the target expression. The default value for this setting is `"none"`."""
    reportImplicitOverride = """Generate or suppress diagnostics for overridden methods in a class that are missing an explicit `@override` decorator. The default value for this setting is `"none"`."""
    reportShadowedImports = """Generate or suppress diagnostics for files that are overriding a module in the stdlib. The default value for this setting is `"none"`."""

    @property
    def clean(self) -> str:
        trims = {
            re.compile(r"Generate or suppress diagnostics for"),
            re.compile(r"Generate or suppress diagnostics related to"),
            re.compile(r"The default value for this setting is.*"),
        }

        return reduce(lambda s, p: re.sub(p, "", s), trims, self.value).strip()

    @classmethod
    def keys(cls) -> set[str]:
        return {rule.name for rule in cls}


class Location(BaseModel):
    line: int
    character: int


class Range(BaseModel):
    start: Location
    end: Location


class PyrightDiagnostic(BaseModel):
    file: Path
    severity: str
    message: str
    range: Range
    rule: str

    def get_context(self, context_lines: int = 2) -> list[str]:
        """Get the lines around the error with context"""
        if not self.file.exists():
            return []

        lines = self.file.read_text().splitlines()
        start_line = max(0, self.range.start.line - context_lines)
        end_line = min(len(lines), self.range.end.line + context_lines + 1)

        return lines[start_line:end_line]

    def pretty_fmt(self, context_lines: int = 2) -> str:
        """Format and print the error in a readable way"""
        output = []

        # Print file location
        file_location = f"[blue]{self.file}:{self.range.start.line + 1}:{self.range.start.character + 1}[/blue]"
        output.append(file_location)

        # Get context lines
        context = self.get_context(context_lines)
        if not context:
            return f"[red]Could not read file: {self.file}[/red]"

        # Calculate line numbers for display
        start_line = max(0, self.range.start.line - 2)

        line_prefix_std = "  [dim]   [/dim] │ "
        line_prefix_number = "  [dim]{:>3}[/dim] │ "
        line_prefix_number_error = "> [red]{:>3}[/red] │ "
        line_prefix_help = " [dim]help[/dim] ~ "
        line_prefix_help_block = "  [dim]   [/dim] ~ "

        # Print each line with context
        for i, line in enumerate(context, start=start_line):
            # Print line number and content
            line_prefix = (
                line_prefix_number_error
                if i == self.range.start.line
                else line_prefix_number
            )
            code_line = f"{line_prefix.format(i + 1)}{line}"
            output.append(code_line)

            # Print error indicator if this is the error line
            if i == self.range.start.line:
                start, end = self.range.start.character, self.range.end.character
                padding = " " * start
                indicator = "^" * (end - start)

                # Print error indicator ^^^^
                rule_flavor = (
                    f" » {PyrightDiagnosticRule[self.rule].clean}"
                    if self.rule in PyrightDiagnosticRule.keys()
                    else ""
                )
                indicator_message = f"{line_prefix_std}{padding}[red]{indicator} [dim]{self.rule}[/red]{rule_flavor}[/dim]"
                output.append(indicator_message)

        # Print error message
        output.append(f"{line_prefix_std}")
        msg_prefix = line_prefix_help
        for line in self.message.splitlines():
            wrapped_message = f"{msg_prefix}  [red]{line}[/red]"
            output.append(wrapped_message)
            msg_prefix = line_prefix_help_block

        return "\n".join(output)


class PyrightSummary(BaseModel):
    filesAnalyzed: int = 0
    errorCount: int = 0
    warningCount: int = 0
    informationCount: int = 0
    timeInSec: float = 0

    def __bool__(self) -> bool:
        return any(
            (
                self.filesAnalyzed,
                self.errorCount,
                self.warningCount,
                self.informationCount,
                self.timeInSec,
            )
        )

    def pretty_fmt(self) -> str:
        err = "red" if self.errorCount else "green"
        warn = "yellow" if self.warningCount else "green"
        info = "blue" if self.informationCount else "green"
        time = "bold magenta" if self.timeInSec else "green"
        return cleandoc(
            f"""
            [blue]summary:[/blue]
              files analyzed   [dim]»[/dim] {self.filesAnalyzed}
              errors           [dim]»[/dim] [{err}]{self.errorCount}[/{err}]
              warnings         [dim]»[/dim] [{warn}]{self.warningCount}[/{warn}]
              information      [dim]»[/dim] [{info}]{self.informationCount}[/{info}]
              time             [dim]»[/dim] [bold {time}]{self.timeInSec}s[/bold {time}]
            """
        )


class PyrightOutput(BaseModel):
    version: str = ""
    time: str = ""
    generalDiagnostics: list[PyrightDiagnostic] = Field(default_factory=list)
    summary: PyrightSummary = Field(default_factory=PyrightSummary)

    returncode: int = 0

    @classmethod
    def model_validate_path(cls, path: Path | str) -> Self:
        path = Path(path)
        logger.debug(f"path: {path}, exists: {path.exists()}")

        if not path.exists():
            raise FileNotFoundError(f"file does not exist: {path}")

        with path.open("r") as f:
            return cls.model_validate_textio(f)

    @classmethod
    def model_validate_textio(cls, textio: TextIO) -> Self:
        text = textio.read()
        logger.debug(f"text: {text}")
        return cls.model_validate_json(text)

    def __bool__(self) -> bool:
        return any(
            (
                self.version,
                self.time,
                self.summary,
            )
        )

    def pretty_fmt(self, context_lines: int = 2, show_summary: bool = False) -> str:
        output = []
        output.append(
            "\n".join(
                diagnostic.pretty_fmt(context_lines)
                for diagnostic in self.generalDiagnostics
            )
        )
        if show_summary:
            output.append("")
            output.append(self.summary.pretty_fmt())
        return "\n".join(output)

    def update(self, returncode: int | None = None) -> Self:
        if returncode is not None:
            self.returncode = returncode
        return self


class Pyright(BaseModel):
    os_path: str = Field(default_factory=lambda: os.environ["PATH"])
    install_cmds: ClassVar[dict[str, list[str]]] = {
        "bun": ["bun", "add"],
        "yarn": ["yarn", "add"],
        "npm": ["npm", "install"],
    }
    errors: list[PyrightDiagnostic] = Field(default_factory=list)

    def error(self, message: str, console: Console = Console()) -> None:
        console.print(f"[red]{message}[/red]")
        sys.exit(1)

    def which(self, cmd: str) -> str | None:
        return shutil.which(cmd, path=self.os_path)

    def requires(self, cmd: str) -> str:
        installed_at = self.is_installed(cmd)
        if installed_at is None:
            self.error(
                f"'{cmd}' is not installed"
                if cmd == "pyright"
                else f"'{cmd}' is required to install pyright"
            )

        assert installed_at is not None
        return installed_at

    def is_installed(self, cmd: str, _cache: dict[str, str | None] = {}) -> str | None:
        if cmd in _cache:
            return _cache[cmd]

        logger.debug(f"checking if '{cmd}' is installed")
        result = self.which(cmd)

        if result:
            _cache[cmd] = result
        return result

    def node_is_installed(self):
        return self.is_installed("node")

    def pyright_is_installed(self):
        return self.is_installed("pyright")

    def bun_is_installed(self):
        return self.is_installed("bun")

    def yarn_is_installed(self):
        return self.is_installed("yarn")

    def npm_is_installed(self):
        return self.is_installed("npm")

    def install_via_cmd(self, *cmd: str):
        cmd = tuple(_ for _ in cmd if _)

        if len(cmd) == 0:
            raise Exception("No command provided to install pyright")

        self.requires(cmd[0])
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if proc.returncode == 0:
            self.update_path()
            return

        self.error(
            f"failed to install pyright: {proc.returncode}\n\n"
            f"reason:\n\n"
            f"    {proc.stderr.replace('\n', '\n    ')}"
        )

    def update_path(self):
        self.requires("node")
        node_modules = subprocess.check_output(["npm", "root"], encoding="utf-8")
        node_bin = Path(node_modules.strip()) / ".bin"

        if not node_bin.exists():
            self.error(f"node_modules path does not exist: {node_bin}")

        self.os_path = ":".join((node_bin.as_posix(), self.os_path))

    def best_installer(self) -> Literal["bun", "yarn", "npm"]:
        """Get the best pyright installer"""
        self.requires("node")
        if self.bun_is_installed():
            return "bun"
        elif self.yarn_is_installed():
            return "yarn"
        elif self.npm_is_installed():
            return "npm"

        raise Exception("No pyright installer found")

    def install_pyright(
        self,
        installer: InstallersT | None = None,
        global_install: bool = False,
        force: bool = False,
    ) -> None:
        if not force and shutil.which("pyright"):
            logger.debug("pyright already installed")
            return

        installer = installer or self.best_installer()
        logger.debug(f"using '{installer}' to install pyright")

        self.install_via_cmd(
            *self.install_cmds[installer],
            "--global" if global_install else "",
            "pyright",
        )

    def run(self, *args: str) -> subprocess.Popen[str]:
        self.requires("node")
        pyright_bin = self.requires("pyright")
        logger.debug(f"running pyright with args: pyright --outputjson {args}")
        proc = subprocess.Popen(
            [pyright_bin, "--outputjson", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        logger.debug(f"pyright bin: {pyright_bin}")
        logger.debug(f"pyright args: {args}")
        logger.debug(f"pyright stdout: {proc.stdout}")
        logger.debug(f"pyright stderr: {proc.stderr}")
        return proc

    def run_getoutput(self, *args: str) -> tuple[str, str]:
        return self.run(*args).communicate()

    def run_getparsed(self, *args: str) -> PyrightOutput:
        proc = self.run(*args)

        if proc.returncode == 0:
            return PyrightOutput(returncode=proc.returncode)

        stdout, stderr = proc.communicate()
        try:
            logger.info("attempting to load output")
            return PyrightOutput.model_validate_json(stdout).update(
                returncode=proc.returncode
            )
        except Exception as e:
            logger.error(f"pyright returned {proc.returncode}")
            logger.error(f"stdout: {stdout}")
            logger.error(f"stderr: {stderr}")

            map(logger.error, stderr.splitlines())
            raise RuntimeError(f"pyright returned {proc.returncode}") from e

    @singledispatchmethod
    def parse_output(self, data: Any) -> Iterable[PyrightDiagnostic]: ...

    @parse_output.register
    def _(self, input: str) -> Iterable[PyrightDiagnostic]:
        output = PyrightOutput.model_validate_json(input)
        yield from output.generalDiagnostics

    @parse_output.register
    def _(self, input: Iterable) -> Iterable[PyrightDiagnostic]:
        for error_dict in input:
            assert isinstance(error_dict, dict)
            yield PyrightDiagnostic.model_validate(error_dict)


class PyrightRunner(BaseModel):
    pyright: Pyright = Field(default_factory=Pyright)

    def parse_args(self) -> tuple[argparse.Namespace, list[str]]:
        parser = argparse.ArgumentParser(add_help=False)
        group = parser.add_argument_group("pyright-pretty options")
        group.add_argument("--debug", action="store_true")
        group.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help="Increase verbosity level (can be used multiple times)",
        )
        group.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="Suppress all output except errors",
        )
        group.add_argument(
            "-c",
            "--context",
            type=int,
            default=2,
            help="Number of lines of context to include in the output",
        )
        group.add_argument(
            "--show-summary",
            action="store_true",
            help="Show the summary of the output",
        )
        group.add_argument("-g", "--global", dest="global_install", action="store_true")
        group.add_argument("--force-install", action="store_true")
        group.add_argument("--install-if-missing", action="store_true")
        group.add_argument("--installer", choices=["bun", "yarn", "npm"], default="npm")
        group.add_argument("--help", action="store_true")

        args, remaining = parser.parse_known_args()

        if args.help:
            parser.print_help()

            self.pyright.update_path()
            if self.pyright.pyright_is_installed():
                stdout, _ = self.pyright.run_getoutput("--help")
                stdout = (
                    stdout.replace("Usage:", "usage:")
                    .replace("  Options:", "pyright options:")
                    .strip()
                )
                print(
                    f"\n\noptions from pyright, these will be passed along to pyright\n\n{stdout}"
                )
            else:
                print(
                    "pyright is not installed, please install it manually or by using `--install-if-missing'"
                )

            sys.exit(0)

        return args, remaining

    def configure_logging(self, args: argparse.Namespace):
        if args.debug:
            log_level = logging.DEBUG
        elif args.quiet:
            log_level = logging.ERROR
        elif args.verbose:
            # Default is WARNING, -v=INFO, -vv=DEBUG
            log_level = max(logging.WARNING - (args.verbose * 10), logging.DEBUG)
        else:
            log_level = logging.WARNING

        logging.basicConfig(
            level=log_level,
            format="%(message)s",
            handlers=[RichHandler()],
        )

    def run(self) -> int:
        parsed, remaining = self.parse_args()
        self.configure_logging(args=parsed)
        self.pyright.requires("node")
        self.pyright.update_path()

        # Read from stdin if no file provided
        if False and not os.isatty(0):
            logger.debug("reading from stdin")
            output = PyrightOutput.model_validate_textio(sys.stdin)
        elif len(sys.argv) >= 2 and (f := Path(sys.argv[1])).exists():
            logger.debug(f"reading from file: {f}")
            output = PyrightOutput.model_validate_path(f)
        else:
            if parsed.install_if_missing and not self.pyright.pyright_is_installed():
                self.pyright.install_pyright()

            output = self.pyright.run_getparsed(*remaining)

        if output.returncode == 0:
            return output.returncode

        console = Console()
        console.print(
            output.pretty_fmt(
                context_lines=parsed.context,
                show_summary=parsed.show_summary,
            )
        )

        return output.returncode


a: int

x: int
a = "hi"


def main() -> int:
    return PyrightRunner().run()


if __name__ == "__main__":
    sys.exit(main() or 1)
