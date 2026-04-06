---
model: mistral-small
temperature: 0.2
schema:
  type: object
  properties:
    summary:
      type: string
      description: A summary of this page only, {{ max_sentences }} sentences maximum.
  required: [summary]
---
Summarize the following page of a scientific document in at most
{{ max_sentences }} sentences. Cover only what this page itself says — do
not speculate about the rest of the document.

Write in the same language as the page text below. Preserve technical
terminology rather than simplifying it. Be concrete: prefer the page's own
claims, findings, or definitions over generic descriptions like "this page
discusses...".

--- BEGIN PAGE {{ page_number }} TEXT ---
{{ page_text }}
--- END PAGE {{ page_number }} TEXT ---
