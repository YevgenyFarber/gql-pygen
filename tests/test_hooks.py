"""Tests for generation hooks."""

import pytest

from gql_pygen.core.hooks import (
    AddHeaderHook,
    FilterTypesHook,
    HookRunner,
    PostGenerateHook,
    PreGenerateHook,
)
from gql_pygen.core.ir import IREnum, IRSchema, IRType


@pytest.fixture
def sample_ir():
    """Create a sample IR schema for testing."""
    return IRSchema(
        scalars=[],
        enums=[
            IREnum(name="Status", values=[], description=None),
            IREnum(name="_Internal", values=[], description=None),
        ],
        types=[
            IRType(name="User", fields=[], description=None, interfaces=[]),
            IRType(name="_Meta", fields=[], description=None, interfaces=[]),
            IRType(name="Product", fields=[], description=None, interfaces=[]),
        ],
        inputs=[
            IRType(name="CreateUserInput", fields=[], description=None, interfaces=[]),
            IRType(name="_DebugInput", fields=[], description=None, interfaces=[]),
        ],
        interfaces=[],
        queries=[],
        mutations=[],
    )


class TestAddHeaderHook:
    """Tests for AddHeaderHook."""

    def test_adds_header(self):
        hook = AddHeaderHook("# Auto-generated")
        result = hook.post_generate("models.py", "class User:\n    pass")
        assert result.startswith("# Auto-generated\n\n")

    def test_preserves_content(self):
        hook = AddHeaderHook("# Header")
        content = "class User:\n    pass"
        result = hook.post_generate("models.py", content)
        assert content in result

    def test_handles_header_with_newline(self):
        hook = AddHeaderHook("# Header\n")
        result = hook.post_generate("test.py", "code")
        # Should not double-up newlines
        assert result == "# Header\n\ncode"


class TestFilterTypesHook:
    """Tests for FilterTypesHook."""

    def test_exclude_prefix(self, sample_ir):
        hook = FilterTypesHook(exclude_prefix="_")
        result = hook.pre_generate(sample_ir)
        
        type_names = [t.name for t in result.types]
        assert "User" in type_names
        assert "Product" in type_names
        assert "_Meta" not in type_names

    def test_exclude_suffix(self, sample_ir):
        hook = FilterTypesHook(exclude_suffix="Input")
        result = hook.pre_generate(sample_ir)
        
        input_names = [i.name for i in result.inputs]
        assert len(input_names) == 0  # All inputs end with "Input"

    def test_include_prefix(self, sample_ir):
        hook = FilterTypesHook(include_prefix="Create")
        result = hook.pre_generate(sample_ir)
        
        input_names = [i.name for i in result.inputs]
        assert "CreateUserInput" in input_names
        assert "_DebugInput" not in input_names

    def test_filters_enums(self, sample_ir):
        hook = FilterTypesHook(exclude_prefix="_")
        result = hook.pre_generate(sample_ir)
        
        enum_names = [e.name for e in result.enums]
        assert "Status" in enum_names
        assert "_Internal" not in enum_names


class TestHookRunner:
    """Tests for HookRunner."""

    def test_run_pre_hooks(self, sample_ir):
        runner = HookRunner()
        runner.add_pre_hook(FilterTypesHook(exclude_prefix="_"))
        
        result = runner.run_pre_hooks(sample_ir)
        type_names = [t.name for t in result.types]
        assert "_Meta" not in type_names

    def test_run_post_hooks(self):
        runner = HookRunner()
        runner.add_post_hook(AddHeaderHook("# Header"))
        
        result = runner.run_post_hooks("test.py", "code")
        assert result.startswith("# Header")

    def test_multiple_pre_hooks(self, sample_ir):
        runner = HookRunner()
        runner.add_pre_hook(FilterTypesHook(exclude_prefix="_"))
        
        class CountTypesHook:
            def pre_generate(self, ir):
                ir.type_count = len(ir.types)
                return ir
        
        runner.add_pre_hook(CountTypesHook())
        
        result = runner.run_pre_hooks(sample_ir)
        assert result.type_count == 2  # User and Product (after filtering)

    def test_multiple_post_hooks(self):
        runner = HookRunner()
        runner.add_post_hook(AddHeaderHook("# Line 1"))
        runner.add_post_hook(AddHeaderHook("# Line 0"))
        
        result = runner.run_post_hooks("test.py", "code")
        # Both headers should be present (second wraps first)
        assert "# Line 0" in result
        assert "# Line 1" in result


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_add_header_is_post_hook(self):
        assert isinstance(AddHeaderHook("header"), PostGenerateHook)

    def test_filter_types_is_pre_hook(self):
        assert isinstance(FilterTypesHook(), PreGenerateHook)

    def test_custom_pre_hook(self):
        class CustomPreHook:
            def pre_generate(self, ir):
                return ir
        
        assert isinstance(CustomPreHook(), PreGenerateHook)

    def test_custom_post_hook(self):
        class CustomPostHook:
            def post_generate(self, filename, content):
                return content
        
        assert isinstance(CustomPostHook(), PostGenerateHook)

