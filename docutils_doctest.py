import doctest
import re
import sys
from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type

import docutils
from docutils import nodes
from docutils.nodes import Node
from docutils.nodes import TextElement
from docutils.parsers.rst import Directive
from docutils.parsers.rst import directives

blankline_re = re.compile(r"^\s*<BLANKLINE>", re.MULTILINE)
doctestopt_re = re.compile(r"#\s*doctest:.+$", re.MULTILINE)

OptionSpec = Dict[str, Callable[[str], Any]]


class TestDirective(Directive):
    """
    Base class for doctest-related directives.
    """

    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    def get_source_info(self) -> Tuple[str, int]:
        """Get source and line number."""
        return self.state_machine.get_source_and_line(self.lineno)

    def set_source_info(self, node: Node) -> None:
        """Set source and line number to the node."""
        node.source, node.line = self.get_source_info()

    def run(self) -> List[Node]:
        # use ordinary docutils nodes for test code: they get special attributes
        # so that our builder recognizes them, and the other builders are happy.
        code = "\n".join(self.content)
        test = None

        print(f"directive run: self.name {self.name}")
        if self.name == "doctest":
            if "<BLANKLINE>" in code:
                # convert <BLANKLINE>s to ordinary blank lines for presentation
                test = code
                code = blankline_re.sub("", code)
            if (
                doctestopt_re.search(code)
                and "no-trim-doctest-flags" not in self.options
            ):
                if not test:
                    test = code
                code = doctestopt_re.sub("", code)
        nodetype: Type[TextElement] = nodes.literal_block
        if self.name in ("testsetup", "testcleanup") or "hide" in self.options:
            nodetype = nodes.comment
        if self.arguments:
            groups = [x.strip() for x in self.arguments[0].split(",")]
        else:
            groups = ["default"]
        node = nodetype(code, code, testnodetype=self.name, groups=groups)
        self.set_source_info(node)
        if test is not None:
            # only save if it differs from code
            node["test"] = test
        if self.name == "doctest":
            # if self.config.highlight_language in ("py", "python"):
            #     node["language"] = "pycon"
            # else:
            #     node["language"] = "pycon3"  # default
            node["language"] = "pycon3"
        elif self.name == "testcode":
            # if self.config.highlight_language in ("py", "python"):
            #     node["language"] = "python"
            # else:
            #     node["language"] = "python3"  # default

            node["language"] = "python3"
        elif self.name == "testoutput":
            # don't try to highlight output
            node["language"] = "none"
        node["options"] = {}
        if self.name in ("doctest", "testoutput") and "options" in self.options:
            # parse doctest-like output comparison flags
            option_strings = self.options["options"].replace(",", " ").split()
            for option in option_strings:
                prefix, option_name = option[0], option[1:]
                if prefix not in "+-":
                    self.state.document.reporter.warning(
                        __("missing '+' or '-' in '%s' option.") % option,
                        line=self.lineno,
                    )
                    continue
                if option_name not in doctest.OPTIONFLAGS_BY_NAME:
                    self.state.document.reporter.warning(
                        __("'%s' is not a valid option.") % option_name,
                        line=self.lineno,
                    )
                    continue
                flag = doctest.OPTIONFLAGS_BY_NAME[option[1:]]
                node["options"][flag] = option[0] == "+"
        if self.name == "doctest" and "pyversion" in self.options:
            try:
                spec = self.options["pyversion"]
                python_version = ".".join([str(v) for v in sys.version_info[:3]])
                if not is_allowed_version(spec, python_version):
                    flag = doctest.OPTIONFLAGS_BY_NAME["SKIP"]
                    node["options"][flag] = True  # Skip the test
            except InvalidSpecifier:
                self.state.document.reporter.warning(
                    __("'%s' is not a valid pyversion option") % spec, line=self.lineno
                )
        if "skipif" in self.options:
            node["skipif"] = self.options["skipif"]
        if "trim-doctest-flags" in self.options:
            node["trim_flags"] = True
        elif "no-trim-doctest-flags" in self.options:
            node["trim_flags"] = False
        return [node]


class TestsetupDirective(TestDirective):
    option_spec: OptionSpec = {"skipif": directives.unchanged_required}


class TestcleanupDirective(TestDirective):
    option_spec: OptionSpec = {"skipif": directives.unchanged_required}


class DoctestDirective(TestDirective):
    option_spec: OptionSpec = {
        "hide": directives.flag,
        "no-trim-doctest-flags": directives.flag,
        "options": directives.unchanged,
        "pyversion": directives.unchanged_required,
        "skipif": directives.unchanged_required,
        "trim-doctest-flags": directives.flag,
    }


class TestcodeDirective(TestDirective):
    option_spec: OptionSpec = {
        "hide": directives.flag,
        "no-trim-doctest-flags": directives.flag,
        "pyversion": directives.unchanged_required,
        "skipif": directives.unchanged_required,
        "trim-doctest-flags": directives.flag,
    }


class TestoutputDirective(TestDirective):
    option_spec: OptionSpec = {
        "hide": directives.flag,
        "no-trim-doctest-flags": directives.flag,
        "options": directives.unchanged,
        "pyversion": directives.unchanged_required,
        "skipif": directives.unchanged_required,
        "trim-doctest-flags": directives.flag,
    }


class TestCode:
    def __init__(
        self,
        code: str,
        type: str,
        filename: str,
        lineno: int,
        options: Optional[Dict] = None,
    ) -> None:
        self.code = code
        self.type = type
        self.filename = filename
        self.lineno = lineno
        self.options = options or {}

    def __repr__(self) -> str:
        return "TestCode(%r, %r, filename=%r, lineno=%r, options=%r)" % (
            self.code,
            self.type,
            self.filename,
            self.lineno,
            self.options,
        )


parser = doctest.DocTestParser()


def setup() -> Dict[str, Any]:
    directives.register_directive("testsetup", TestsetupDirective)
    directives.register_directive("testcleanup", TestcleanupDirective)
    directives.register_directive("doctest", DoctestDirective)
    directives.register_directive("testcode", TestcodeDirective)
    directives.register_directive("testoutput", TestoutputDirective)
    # app.add_builder(DocTestBuilder)
    # # this config value adds to sys.path
    # app.add_config_value("doctest_path", [], False)
    # app.add_config_value("doctest_test_doctest_blocks", "default", False)
    # app.add_config_value("doctest_global_setup", "", False)
    # app.add_config_value("doctest_global_cleanup", "", False)
    # app.add_config_value(
    #     "doctest_default_flags",
    #     doctest.DONT_ACCEPT_TRUE_FOR_1
    #     | doctest.ELLIPSIS
    #     | doctest.IGNORE_EXCEPTION_DETAIL,
    #     False,
    # )
    return {"version": docutils.__version__, "parallel_read_safe": True}
