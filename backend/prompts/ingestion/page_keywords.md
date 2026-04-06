---
model: mistral-small
temperature: 0.2
schema:
  type: object
  properties:
    core_topics:
      type: array
      items: { type: string }
      description: The main themes this page is actually about (not the whole document).
    related_concepts:
      type: array
      items: { type: string }
      description: Contextual ideas the page touches on but doesn't center.
    domain_terms:
      type: array
      items: { type: string }
      description: Technical vocabulary specific to the field.
    acronyms:
      type: array
      items:
        type: object
        properties:
          acronym: { type: string }
          expansion: { type: string }
        required: [acronym, expansion]
    operational_verbs:
      type: array
      items: { type: string }
      description: Action phrases describing what is being done (e.g. "fine-tune", "cross-validate").
    entities:
      type: array
      items: { type: string }
      description: People, places, organizations, named datasets, or named systems mentioned.
    general_keywords:
      type: array
      items: { type: string }
      description: Anything relevant that doesn't fit the categories above.
  required: [core_topics, related_concepts, domain_terms, acronyms, operational_verbs, entities, general_keywords]
---
Extract and categorize keywords from the following page of a scientific
document. Only use what this page itself supports — do not invent keywords
that belong to the document as a whole but aren't evidenced on this page.

Leave a category as an empty list if nothing on this page fits it — do not
force entries into a category just to fill it.

--- BEGIN PAGE {{ page_number }} TEXT ---
{{ page_text }}
--- END PAGE {{ page_number }} TEXT ---
