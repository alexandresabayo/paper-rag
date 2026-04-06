---
model: mistral-small
temperature: 0.0
schema:
  type: object
  properties:
    doc_type:
      type: string
      enum: ["Journal Article", "Conference Paper", "Preprint", "Thesis", "Technical Report", "Other"]
    authors:
      type: array
      items: { type: string }
    year:
      type: string
      description: Publication year as a 4-digit string, or "" if not determinable.
    title:
      type: string
    venue:
      type: string
      description: Journal or conference name, or "" if not applicable/determinable.
    doi:
      type: string
      description: DOI if present anywhere in the source text, or "".
    acronym:
      type: string
      description: The document/project/method's own acronym if it prominently uses one, or "".
  required: [doc_type, authors, year, title, venue, doi, acronym]
---
Below is the combined text of the first {{ page_count }} pages of a scientific
document (title page plus whatever immediately follows — the DOI or venue
sometimes sits on a copyright/cover page rather than the title page itself).

Read this text and identify the document's own metadata, exactly as the
document states it. Do not infer anything from a file name — none is given
to you, and none should be assumed. If a field genuinely cannot be
determined from the text below, return an empty string for it (or an empty
list for `authors`) rather than guessing.

--- BEGIN DOCUMENT TEXT ({{ page_count }} pages, combined) ---
{{ combined_text }}
--- END DOCUMENT TEXT ---
