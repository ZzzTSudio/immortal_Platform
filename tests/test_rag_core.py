from app.rag.chunker import chunk_document
from app.rag.cleaner import clean_text, remove_toc_cover_pages
from app.rag.models import ChunkMetadata, SearchHit
from app.rag.prompt_builder import build_knowledge_prompt
from app.rag.retriever import rrf_fuse


def test_clean_text_removes_html_and_duplicate_paragraphs():
    raw = "<html><body><p>正文内容</p><p>正文内容</p><footer>页脚</footer></body></html>"

    cleaned = clean_text(raw)

    assert "正文内容" in cleaned
    assert cleaned.count("正文内容") == 1
    assert "<p>" not in cleaned


def test_remove_toc_cover_pages_drops_front_toc():
    pages = ["目录\nChapter\n5\n7", "正文第一页", "正文第二页"]

    kept = remove_toc_cover_pages(pages)

    assert kept == ["正文第一页", "正文第二页"]


def test_chunk_document_prefers_markdown_titles():
    chunks = chunk_document(
        skill_id="skill_a",
        filename="guide.md",
        source_type="md",
        text="# 安装\n安装步骤说明\n\n## API\n接口说明",
        chunk_size_tokens=20,
        overlap_tokens=2,
    )

    assert chunks
    assert {chunk.metadata.title for chunk in chunks} >= {"安装", "API"}
    assert all(chunk.skill_id == "skill_a" for chunk in chunks)


def test_rrf_fuse_combines_dense_and_sparse_scores():
    metadata = ChunkMetadata(source="txt", title="t")
    dense = [SearchHit(chunk_id="a", content="A", metadata=metadata, score=0.9)]
    sparse = [
        SearchHit(chunk_id="b", content="B", metadata=metadata, score=3.0),
        SearchHit(chunk_id="a", content="A", metadata=metadata, score=1.0),
    ]

    fused = rrf_fuse(dense, sparse, k=60, weight_dense=0.7, weight_sparse=0.3, limit=20)

    assert [hit.chunk_id for hit in fused][:2] == ["a", "b"]
    assert fused[0].dense_score == 0.9
    assert fused[0].sparse_score == 1.0


def test_prompt_builder_formats_knowledge_block():
    metadata = ChunkMetadata(source="pdf", title="手册")
    hits = [SearchHit(chunk_id="c1", content="这是知识内容", metadata=metadata, rerank_score=0.8)]

    prompt = build_knowledge_prompt(hits, max_tokens=100)

    assert prompt.startswith("【知识库】")
    assert "[1] 这是知识内容" in prompt
    assert "来源：pdf" in prompt

