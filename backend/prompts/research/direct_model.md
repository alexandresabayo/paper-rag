---
temperature: 0.5
schema:
  type: object
  properties:
    answer:
      type: string
  required: [answer]
---
You are answering a question directly, with no document retrieval and no
document context of any kind — the user has explicitly chosen "Direct
model" mode, bypassing the document corpus entirely.

Reply in the same language as the question. Answer from your own general
knowledge. Do not imply that you consulted any documents, and do not
fabricate citations.

--- QUESTION ---
{{ query }}
