---
temperature: 0.0
schema:
  type: object
  properties:
    text:
      type: string
      description: The complete transcribed text of the page.
  required: [text]
---
You are transcribing a single page of a scientific document (journal article,
conference paper, preprint, thesis, or technical report) from an image.

Transcribe the page completely and faithfully:

- Preserve reading order (including multi-column layouts — read column by
  column, not line-by-line across columns).
- Preserve section headings, footnotes, figure/table captions, and equations
  as plain text (use standard notation for equations; do not attempt LaTeX).
- Preserve the original language of the text exactly as written — do not
  translate.
- Do not summarize, paraphrase, correct, or omit anything, including text
  that looks like it belongs to a header, footer, watermark, or page number.
- If the page is a title page, front matter, or references list, transcribe
  it exactly as it appears — do not reformat citations.
- If a region is genuinely illegible, write `[illegible]` in its place rather
  than guessing.

Return only the transcription. Do not add commentary, notes, or explanation
of what you did.
