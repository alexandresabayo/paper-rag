---
temperature: 0.2
schema:
  type: object
  properties:
    running_summary:
      type: string
      description: The updated running summary of the whole document so far.
  required: [running_summary]
---
You are incrementally building a running summary of a scientific document,
one page at a time. You will be given the summary so far (may be empty, if
this is the first page that has one) and the next page's own summary. Fold
the new page into the running summary.

Keep the result comprehensive but non-redundant: integrate genuinely new
information, don't just append the new page's summary onto the old one
verbatim, and don't lose earlier content that's still relevant. Keep it
proportionate — the running summary should read like a coherent abstract of
the document so far, not a page-by-page log.

Document title (if known): {{ document_title or "unknown" }}

--- RUNNING SUMMARY SO FAR (through page {{ page_number - 1 }}) ---
{{ running_summary or "(none yet — this is the first page with a summary)" }}
--- END RUNNING SUMMARY ---

--- PAGE {{ page_number }} SUMMARY ---
{{ next_page_summary }}
--- END PAGE {{ page_number }} SUMMARY ---
