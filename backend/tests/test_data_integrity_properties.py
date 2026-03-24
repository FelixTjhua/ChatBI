"""Property-based tests for terminology parent-child relationship integrity."""
import sys
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------

_word = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

_description = st.text(min_size=0, max_size=100)

_oid = st.integers(min_value=1, max_value=100)

# Generate a list of parent terms (pid=None) with unique IDs
_parent_id = st.integers(min_value=1, max_value=10000)

# Number of children per parent
_num_children = st.integers(min_value=0, max_value=5)


# ---------------------------------------------------------------------------

def build_terminology_hierarchy(parents, children_map):
    """Build an in-memory terminology hierarchy."""
    terms = []
    for pid, word in parents:
        terms.append({"id": pid, "pid": None, "word": word})

    for parent_id, children in children_map.items():
        for child_id, word in children:
            terms.append({"id": child_id, "pid": parent_id, "word": word})

    return terms


def validate_hierarchy(terms):
    """Validate terminology hierarchy integrity."""
    id_to_term = {t["id"]: t for t in terms}
    orphans = []
    deep_nesting = []

    for term in terms:
        if term["pid"] is not None:
            parent = id_to_term.get(term["pid"])
            if parent is None:
                orphans.append(term)
            elif parent["pid"] is not None:
                deep_nesting.append(term)

    return len(orphans) == 0 and len(deep_nesting) == 0, orphans, deep_nesting


# ---------------------------------------------------------------------------

@st.composite
def valid_hierarchy(draw):
    """Generate a valid two-level terminology hierarchy."""
    num_parents = draw(st.integers(min_value=1, max_value=10))
    next_id = 1
    parents = []
    children_map = {}

    for _ in range(num_parents):
        word = draw(_word)
        parents.append((next_id, word))
        parent_id = next_id
        next_id += 1

        num_children = draw(st.integers(min_value=0, max_value=5))
        children = []
        for _ in range(num_children):
            child_word = draw(_word)
            children.append((next_id, child_word))
            next_id += 1
        children_map[parent_id] = children

    return parents, children_map


@st.composite
def hierarchy_with_orphan(draw):
    """Generate a hierarchy that has an orphan child (pid points to non-existent parent)."""
    parents, children_map = draw(valid_hierarchy())
    terms = build_terminology_hierarchy(parents, children_map)

    # Add an orphan child pointing to a non-existent parent
    max_id = max(t["id"] for t in terms) if terms else 0
    orphan_pid = max_id + 100  # guaranteed non-existent
    orphan_word = draw(_word)
    terms.append({"id": max_id + 1, "pid": orphan_pid, "word": orphan_word})

    return terms


@st.composite
def hierarchy_with_deep_nesting(draw):
    """Generate a hierarchy with 3-level nesting (child of child)."""
    parents, children_map = draw(valid_hierarchy())
    assume(any(len(v) > 0 for v in children_map.values()))

    terms = build_terminology_hierarchy(parents, children_map)

    # Find a child term and make a grandchild
    children = [t for t in terms if t["pid"] is not None]
    assume(len(children) > 0)

    child = children[0]
    max_id = max(t["id"] for t in terms)
    grandchild_word = draw(_word)
    terms.append({"id": max_id + 1, "pid": child["id"], "word": grandchild_word})

    return terms


# ---------------------------------------------------------------------------

class TestTerminologyHierarchyIntegrityProperty25:
    """
    **Validates: Requirements 5.2**

    Property 25: 术语库父子关系完整性
    对于任何术语库中 pid 非空的术语条目，其 pid 应指向一个存在的父术语条目，
    且父术语的 pid 应为空（仅支持两级结构）。
    """

    @given(data=valid_hierarchy())
    @settings(max_examples=100)
    def test_valid_hierarchy_passes_validation(self, data):
        """A correctly constructed two-level hierarchy should pass validation."""
        parents, children_map = data
        terms = build_terminology_hierarchy(parents, children_map)

        valid, orphans, deep_nesting = validate_hierarchy(terms)

        assert valid, (
            f"Valid hierarchy failed validation: orphans={orphans}, deep_nesting={deep_nesting}"
        )
        assert len(orphans) == 0
        assert len(deep_nesting) == 0

    @given(data=valid_hierarchy())
    @settings(max_examples=100)
    def test_all_children_point_to_existing_parents(self, data):
        """Every child's pid must reference an existing term."""
        parents, children_map = data
        terms = build_terminology_hierarchy(parents, children_map)

        all_ids = {t["id"] for t in terms}
        for term in terms:
            if term["pid"] is not None:
                assert term["pid"] in all_ids, (
                    f"Child {term['id']} (word='{term['word']}') has pid={term['pid']} "
                    f"which does not exist in the hierarchy"
                )

    @given(data=valid_hierarchy())
    @settings(max_examples=100)
    def test_parents_have_null_pid(self, data):
        """All parent terms (those referenced by children) must have pid=None."""
        parents, children_map = data
        terms = build_terminology_hierarchy(parents, children_map)

        id_to_term = {t["id"]: t for t in terms}
        for term in terms:
            if term["pid"] is not None:
                parent = id_to_term.get(term["pid"])
                assert parent is not None, f"Parent {term['pid']} not found"
                assert parent["pid"] is None, (
                    f"Parent {parent['id']} (word='{parent['word']}') has non-null pid={parent['pid']}, "
                    f"violating two-level structure constraint"
                )

    @given(data=valid_hierarchy())
    @settings(max_examples=100)
    def test_only_two_levels(self, data):
        """Hierarchy must have at most 2 levels: parents (pid=None) and children (pid=parent_id)."""
        parents, children_map = data
        terms = build_terminology_hierarchy(parents, children_map)

        id_to_term = {t["id"]: t for t in terms}
        for term in terms:
            if term["pid"] is not None:
                parent = id_to_term.get(term["pid"])
                if parent is not None:
                    # Parent must be a root (pid=None)
                    assert parent["pid"] is None, (
                        f"Three-level nesting detected: term {term['id']} -> "
                        f"parent {parent['id']} -> grandparent {parent['pid']}"
                    )

    @given(terms=hierarchy_with_orphan())
    @settings(max_examples=100)
    def test_orphan_detected(self, terms):
        """Hierarchy with orphan children should fail validation."""
        valid, orphans, deep_nesting = validate_hierarchy(terms)

        assert not valid, "Hierarchy with orphan should not be valid"
        assert len(orphans) > 0, "Should detect at least one orphan"

    @given(terms=hierarchy_with_deep_nesting())
    @settings(max_examples=100)
    def test_deep_nesting_detected(self, terms):
        """Hierarchy with 3+ levels should fail validation."""
        valid, orphans, deep_nesting = validate_hierarchy(terms)

        assert not valid, "Hierarchy with deep nesting should not be valid"
        assert len(deep_nesting) > 0, "Should detect at least one deep nesting violation"

    @given(data=valid_hierarchy())
    @settings(max_examples=100)
    def test_validation_idempotent(self, data):
        """Running validation twice on the same data should give the same result."""
        parents, children_map = data
        terms = build_terminology_hierarchy(parents, children_map)

        result1 = validate_hierarchy(terms)
        result2 = validate_hierarchy(terms)

        assert result1[0] == result2[0], "Validation should be idempotent"
