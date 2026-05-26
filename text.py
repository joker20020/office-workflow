# -*- UTF-8 -*-
# @author   : 40599
# @time     : 2026/3/16 15:31
# @version  : V1

import fitz
import re
from typing import List


async def get_json(text: str):
    group = []
    result = ""
    bracket_count = 0
    for s in text:
        if s == "{":
            bracket_count += 1
        elif s == "}":
            bracket_count -= 1
        if bracket_count:
            group.append(s)
        elif bracket_count == 0 and s == "}":
            group.append(s)
            result += "".join(group)
            group = []

    return result


class TextProcessor(object):

    def __init__(self):
        pass

    def extract_text_from_pdf(self, pdf_path):
        doc = fitz.open(pdf_path)
        text = ""

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()

        return text

    def split_markdown_for_rag(
        self,
        markdown_text: str,
        min_words: int = 50,
        include_subsections: bool = True
    ) -> List[str]:
        """将 Markdown 文档按标题结构分割为适合 RAG 检索的文本块。"""
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        lines = [line.rstrip() for line in markdown_text.splitlines() if line.strip() or line == '\n']

        sections = []
        current_section = None

        for line in lines:
            match = heading_pattern.match(line)
            if match:
                if current_section is not None:
                    sections.append(current_section)
                level = len(match.group(1))
                heading = match.group(2).strip()
                current_section = {
                    'level': level,
                    'heading': heading,
                    'lines': [line]
                }
            else:
                if current_section is None:
                    current_section = {
                        'level': 0,
                        'heading': 'Introduction',
                        'lines': [line]
                    }
                else:
                    current_section['lines'].append(line)

        if current_section is not None:
            sections.append(current_section)

        chunks = []

        for i, sec in enumerate(sections):
            if sec['level'] == 0 and not sec['lines']:
                continue

            path = []
            for j in range(i, -1, -1):
                if sections[j]['level'] < sec['level']:
                    path.append(sections[j]['heading'])
                elif sections[j]['level'] == sec['level'] and j < i:
                    break
            path.reverse()
            path.append(sec['heading'])
            title_path = " > ".join(path) if path else "Untitled"

            content_lines = sec['lines'][1:]

            if include_subsections:
                child_lines = []
                for j in range(i + 1, len(sections)):
                    if sections[j]['level'] <= sec['level']:
                        break
                    child_lines.extend(sections[j]['lines'])
                content_lines.extend(child_lines)

            content = '\n'.join(content_lines).strip()
            chunk_text = f"Section: {title_path}\n\n{content}".strip()

            if len(chunk_text.split()) >= min_words or i == 0:
                chunks.append(chunk_text)
            else:
                if chunks:
                    chunks[-1] += "\n\n" + chunk_text
                else:
                    chunks.append(chunk_text)

        return chunks
