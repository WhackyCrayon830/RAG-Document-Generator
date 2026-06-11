from pathlib import Path

from docx import Document


def compile_docx(title: str, sections: list[dict], output_path: Path, template_path: Path | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document(str(template_path)) if template_path and template_path.exists() else Document()
    if not template_path:
        doc.add_heading(title, level=0)
    for section in sections:
        doc.add_heading(section["title"], level=1)
        for block in section["content"].split("\n\n"):
            text = block.strip()
            if text:
                doc.add_paragraph(text)
    doc.save(str(output_path))
    return output_path
