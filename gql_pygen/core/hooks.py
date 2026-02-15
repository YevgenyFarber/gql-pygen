"""Generation hooks for customizing code generation.

Provides protocols for pre- and post-generation hooks that can modify
the IR before generation or transform the generated code after.

Example usage:
    from gql_pygen.core.hooks import PreGenerateHook, PostGenerateHook

    # Pre-generation hook to filter types
    class FilterInternalTypes(PreGenerateHook):
        def pre_generate(self, ir):
            ir.types = [t for t in ir.types if not t.name.startswith("_")]
            return ir

    # Post-generation hook to add headers
    class AddLicenseHeader(PostGenerateHook):
        def post_generate(self, filename, content):
            header = "# Copyright 2024 My Company\\n\\n"
            return header + content
"""

from typing import Protocol, runtime_checkable

from .ir import IRSchema


@runtime_checkable
class PreGenerateHook(Protocol):
    """Protocol for pre-generation hooks.

    Pre-generation hooks receive the IR schema before code generation
    and can modify it. The modified IR is then used for generation.

    Example:
        class RemoveDeprecated(PreGenerateHook):
            def pre_generate(self, ir: IRSchema) -> IRSchema:
                ir.types = [t for t in ir.types if not t.deprecated]
                return ir
    """

    def pre_generate(self, ir: IRSchema) -> IRSchema:
        """Called before code generation.

        Args:
            ir: The intermediate representation of the schema

        Returns:
            The (possibly modified) IR to use for generation
        """
        ...


@runtime_checkable
class PostGenerateHook(Protocol):
    """Protocol for post-generation hooks.

    Post-generation hooks receive the generated code for each file
    and can transform it before it's written to disk.

    Example:
        class FormatWithBlack(PostGenerateHook):
            def post_generate(self, filename: str, content: str) -> str:
                import black
                return black.format_str(content, mode=black.FileMode())
    """

    def post_generate(self, filename: str, content: str) -> str:
        """Called after code generation for each file.

        Args:
            filename: The name of the generated file (e.g., "models.py")
            content: The generated code content

        Returns:
            The (possibly transformed) code to write
        """
        ...


class AddHeaderHook:
    """Built-in hook to add a header to generated files.

    Example:
        hook = AddHeaderHook("# Auto-generated - do not edit")
    """

    def __init__(self, header: str):
        self.header = header

    def post_generate(self, _filename: str, content: str) -> str:
        """Add a header to the beginning of the file."""
        if not self.header.endswith("\n"):
            header = self.header + "\n\n"
        else:
            header = self.header + "\n"
        return header + content


class FilterTypesHook:
    """Built-in hook to filter types by name prefix/suffix.

    Example:
        # Remove all types starting with underscore
        hook = FilterTypesHook(exclude_prefix= "_")
    """

    def __init__(
        self,
        exclude_prefix: str | None = None,
        exclude_suffix: str | None = None,
        include_prefix: str | None = None,
        include_suffix: str | None = None,
    ):
        self.exclude_prefix = exclude_prefix
        self.exclude_suffix = exclude_suffix
        self.include_prefix = include_prefix
        self.include_suffix = include_suffix

    def _should_include(self, name: str) -> bool:
        """Check if a type should be included."""
        if self.exclude_prefix and name.startswith(self.exclude_prefix):
            return False
        if self.exclude_suffix and name.endswith(self.exclude_suffix):
            return False
        if self.include_prefix and not name.startswith(self.include_prefix):
            return False
        if self.include_suffix and not name.endswith(self.include_suffix):
            return False
        return True

    def pre_generate(self, ir: IRSchema) -> IRSchema:
        """Filter types from the IR."""
        ir.types = {k: v for k, v in ir.types.items() if self._should_include(v.name)}
        ir.inputs = {k: v for k, v in ir.inputs.items() if self._should_include(v.name)}
        ir.enums = {k: v for k, v in ir.enums.items() if self._should_include(v.name)}
        return ir


class HookRunner:
    """Runs a collection of hooks in order."""

    def __init__(self):
        self.pre_hooks: list[PreGenerateHook] = []
        self.post_hooks: list[PostGenerateHook] = []

    def add_pre_hook(self, hook: PreGenerateHook):
        """Add a pre-generation hook."""
        self.pre_hooks.append(hook)

    def add_post_hook(self, hook: PostGenerateHook):
        """Add a post-generation hook."""
        self.post_hooks.append(hook)

    def run_pre_hooks(self, ir: IRSchema) -> IRSchema:
        """Run all pre-generation hooks in order."""
        for hook in self.pre_hooks:
            ir = hook.pre_generate(ir)
        return ir

    def run_post_hooks(self, filename: str, content: str) -> str:
        """Run all post-generation hooks in order."""
        for hook in self.post_hooks:
            content = hook.post_generate(filename, content)
        return content
