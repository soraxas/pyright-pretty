from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from functools import singledispatchmethod
from inspect import cleandoc
from pathlib import Path
from typing import Any, ClassVar, Literal, Self, TextIO

from pydantic import BaseModel, Field
from rich.console import Console
from rich.logging import RichHandler

logger = logging.getLogger(__name__)

console = Console()
InstallersT = Literal["bun", "yarn", "npm"]


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

    def pretty_fmt(self) -> str:
        """Format and print the error in a readable way"""
        output = []

        # Print file location
        file_location = f"[blue]{self.file}:{self.range.start.line + 1}:{self.range.start.character + 1}[/blue]"
        output.append(file_location)

        # Get context lines
        context = self.get_context()
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
                indicator_message = f"{line_prefix_std}{padding}[red]{indicator} [dim]{self.rule}[/dim][/red]"
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
        return cleandoc(
            f"""
            files analyzed   » {self.filesAnalyzed}
            errors           » {self.errorCount}
            warnings         » {self.warningCount}
            information      » {self.informationCount}
            time             » {self.timeInSec}s
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

        if not path.exists():
            raise FileNotFoundError(f"file does not exist: {path}")

        with path.open("r") as f:
            return cls.model_validate_textio(f)

    @classmethod
    def model_validate_textio(cls, textio: TextIO) -> Self:
        return cls.model_validate_json(textio.read())

    def __bool__(self) -> bool:
        return any(
            (
                self.version,
                self.time,
                self.summary,
            )
        )

    def pretty_fmt(self) -> str:
        output = []
        output.append(self.summary.pretty_fmt())
        output.append(
            "\n".join(diagnostic.pretty_fmt() for diagnostic in self.generalDiagnostics)
        )
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
        if not os.isatty(0):
            output = PyrightOutput.model_validate_textio(sys.stdin)
        elif len(sys.argv) >= 2 and (f := Path(sys.argv[1])).exists():
            output = PyrightOutput.model_validate_path(f)
        else:
            if parsed.install_if_missing and not self.pyright.pyright_is_installed():
                self.pyright.install_pyright()

            output = self.pyright.run_getparsed(*remaining)

        if output.returncode == 0:
            return output.returncode

        console = Console()
        console.print(output.pretty_fmt())

        return 0


def main() -> int:
    return PyrightRunner().run()


if __name__ == "__main__":
    sys.exit(main())
