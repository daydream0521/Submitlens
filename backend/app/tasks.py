import io
import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader


def paragraphs(text):
    return [{'ref': f'段落 {i}', 'text': part} for i, part in enumerate(re.split(r'\n\s*\n', text), 1) if part.strip()]


def parse_document(name, data):
    suffix = Path(name).suffix.lower()
    if suffix == '.pdf':
        reader = PdfReader(io.BytesIO(data))
        parts = [{'ref': f'第 {i} 页', 'text': page.extract_text() or ''} for i, page in enumerate(reader.pages, 1)]
    elif suffix == '.docx':
        doc = Document(io.BytesIO(data))
        parts = []
        for i, block in enumerate(doc.iter_inner_content(), 1):
            text = block.text if hasattr(block, 'text') else '\n'.join('\t'.join(c.text for c in row.cells) for row in block.rows)
            parts.append({'ref': f'段落/表格 {i}', 'text': text})
    elif suffix in ('.txt', '.md'):
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = data.decode('gb18030')
        if suffix == '.txt':
            parts = paragraphs(text)
        else:
            heading = ''
            parts = []
            for i, line in enumerate(text.splitlines(), 1):
                if line.startswith('#'):
                    heading = line.lstrip('#').strip()
                parts.append({'ref': f'行 {i}' + (f' / {heading}' if heading else ''), 'text': line})
        return text, parts
    else:
        raise ValueError('请选择 PDF、DOCX、MD 或 TXT 文件')
    return '\n\n'.join(p['text'] for p in parts), parts
