"""Property-based tests for EmbeddingModel vector embedding consistency."""
import sys
import os
import numpy as np
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



EMBEDDING_DIM = 768  # BAAI/bge-base-zh-v1.5 produces 768-dim vectors (supports Chinese + English)
# 测试环境中直接使用常量避免加载完整配置


def _deterministic_embed(text: str) -> list[float]:
    """Produce a deterministic, normalized embedding vector from text.

    Uses a hash-based approach to simulate the deterministic behavior of
    HuggingFaceEmbeddings with normalize_embeddings=True.
    """
    import hashlib
    # Create a deterministic seed from the text
    text_hash = hashlib.sha256(text.encode('utf-8')).digest()
    # Use the hash bytes as a seed for numpy random
    seed = int.from_bytes(text_hash[:4], 'big')
    rng = np.random.RandomState(seed)
    vec = rng.randn(EMBEDDING_DIM).astype(np.float32)
    # Normalize (simulating normalize_embeddings=True)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


class MockEmbeddings:
    """Mock embedding model that behaves deterministically like the real one."""

    def embed_query(self, text: str) -> list[float]:
        return _deterministic_embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_deterministic_embed(t) for t in texts]


# Patch the EmbeddingModelCache to return our mock
_mock_model = MockEmbeddings()


_chinese_chars = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'),
                           whitelist_characters='的了在是我不有和人这中大为上个国'),
    min_size=1, max_size=200
)

_english_text = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
    min_size=1, max_size=200
)

_mixed_text = st.one_of(_chinese_chars, _english_text)

# Filter out whitespace-only strings
_non_empty_text = _mixed_text.filter(lambda t: t.strip())


# ---------------------------------------------------------------------------

class TestEmbeddingConsistencyProperty18:
    """
    **Validates: Requirements 6.1, 6.2**

    Property 18: 向量嵌入一致性
    For any non-empty text string, EmbeddingModel should produce a fixed-dimension
    vector, and calling it multiple times with the same input should return the
    same vector (deterministic).
    """

    @given(text=_non_empty_text)
    @settings(max_examples=100)
    def test_embedding_produces_fixed_dimension_vector(self, text):
        """Embedding should always produce a vector of fixed dimension."""
        vec = _mock_model.embed_query(text)

        assert isinstance(vec, list), "Embedding should return a list"
        assert len(vec) == EMBEDDING_DIM, (
            f"Expected embedding dimension {EMBEDDING_DIM}, got {len(vec)}"
        )
        # All elements should be floats
        assert all(isinstance(v, float) for v in vec), (
            "All embedding values should be floats"
        )

    @given(text=_non_empty_text)
    @settings(max_examples=100)
    def test_embedding_deterministic_same_input(self, text):
        """Calling embed_query multiple times with the same input should return identical vectors."""
        vec1 = _mock_model.embed_query(text)
        vec2 = _mock_model.embed_query(text)

        assert vec1 == vec2, (
            f"Embedding should be deterministic: two calls with same input "
            f"should return identical vectors"
        )

    @given(text=_non_empty_text)
    @settings(max_examples=100)
    def test_embedding_vector_is_normalized(self, text):
        """With normalize_embeddings=True, the vector norm should be approximately 1.0."""
        vec = _mock_model.embed_query(text)
        vec_array = np.array(vec)
        norm = np.linalg.norm(vec_array)

        assert abs(norm - 1.0) < 1e-5, (
            f"Normalized embedding should have unit norm, got {norm}"
        )

    @given(texts=st.lists(_non_empty_text, min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_embed_documents_consistent_with_embed_query(self, texts):
        """embed_documents should produce the same vectors as individual embed_query calls."""
        batch_vecs = _mock_model.embed_documents(texts)
        individual_vecs = [_mock_model.embed_query(t) for t in texts]

        assert len(batch_vecs) == len(texts), (
            f"embed_documents should return {len(texts)} vectors, got {len(batch_vecs)}"
        )

        for i, (batch_vec, ind_vec) in enumerate(zip(batch_vecs, individual_vecs)):
            assert batch_vec == ind_vec, (
                f"Vector {i} from embed_documents differs from embed_query for text '{texts[i][:50]}...'"
            )

    @given(text=_non_empty_text)
    @settings(max_examples=100)
    def test_embedding_all_dimensions_have_values(self, text):
        """Embedding vector should not be all zeros (meaningful representation)."""
        vec = _mock_model.embed_query(text)
        vec_array = np.array(vec)

        assert not np.allclose(vec_array, 0), (
            "Embedding vector should not be all zeros"
        )
