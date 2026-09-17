from pathlib import Path

from vanilla_ultra_rag_mcp.source_selection import input_files, stage_input_files


def test_verifier_selects_and_stages_only_pdf_and_epub(tmp_path: Path) -> None:
    source = tmp_path / "sources"
    source.mkdir()
    pdf = source / "article.pdf"
    epub = source / "nested" / "book.epub"
    markdown = source / "notes.md"
    epub.parent.mkdir()
    for path in (pdf, epub, markdown):
        path.write_text(path.name, encoding="utf-8")

    inputs = input_files(source)
    assert inputs == [pdf, epub]

    staging_root = tmp_path / "staging"
    staged = stage_input_files(source, inputs, staging_root)
    staged_files = sorted(
        path.relative_to(staged) for path in staged.rglob("*") if path.is_file()
    )
    assert staged_files == [Path("article.pdf"), Path("nested/book.epub")]
    assert not (staged / "notes.md").exists()
