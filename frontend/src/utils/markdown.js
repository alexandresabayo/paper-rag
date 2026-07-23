import { marked } from "marked";
import DOMPurify from "dompurify";

// GFM-style single-newline handling (matches how most chat models format
// their own output - a blank line between paragraphs isn't guaranteed,
// but a plain newline between short lines is common).
marked.setOptions({ breaks: true });

/**
 * Renders `rawText` (assumed to be Markdown - model output, not user
 * input) to sanitized HTML for `v-html`.
 *
 * `streaming`: when true, appends a small inline cursor marker to the
 * *raw markdown source* before parsing - not as a separate DOM sibling
 * afterward - so it ends up exactly at the end of whatever the last
 * rendered element is (a paragraph, a list item, ...) regardless of
 * what that element happens to be. Verified this survives
 * DOMPurify's sanitization pass with its class intact before wiring
 * this in.
 *
 * The whole string is re-parsed from scratch on every call rather than
 * incrementally patched - simple, and cheap enough at chat-answer
 * lengths; some Markdown (an unclosed ``` fence, a trailing `**`) will
 * render a little oddly for the instant it's incomplete mid-stream, the
 * same trade-off most streaming-markdown chat UIs make.
 */
const CURSOR_MARKER = '<span class="md-cursor">\u258c</span>';

export function renderMarkdown(rawText, streaming = false) {
  const source = streaming ? `${rawText ?? ""}${CURSOR_MARKER}` : rawText ?? "";
  const html = marked.parse(source);
  return DOMPurify.sanitize(html);
}
