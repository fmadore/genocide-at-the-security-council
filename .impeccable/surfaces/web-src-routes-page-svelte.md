---
version: 1
slug: "web-src-routes-page-svelte"
primary_target: "web/src/routes/+page.svelte"
related_targets: ["web/src/lib/Figure.svelte","web/src/lib/UnitField.svelte"]
---

# Surface brief: Overview (web/src/routes/+page.svelte)

Scope: the site's opening page. Visitor mode: Operate (a researcher tests a
claim against the record and leaves with a citable figure or number).

Audience and job: a social scientist or historian at a laptop, checking how
the word genocide is used at the Security Council; the page must give the
headline numbers at a glance and open onto the two figures that carry them.

Action and proof: the counted corpus (a field of unit squares, one per 1,000
speeches, the speeches that mention the word filled), the four numbers with
their bases, Plate 1 (occurrences and share) and Plate 2 (six terms as small
multiples), each with its reading note and caveat beneath it and its source
line, and a numbered index of the other sections.

Constraints: copy is fixed; the mark on the word is the site's gesture and
appears in the title and the standfirst; the register hues stay a data layer;
figures export as CSV, SVG and PNG; WCAG AA with axe in CI; print-ready.

Chosen direction: The Programme Grid (seed 426cd46f, code-led). Memorable
moment: the corpus counted in squares above four numbers set in one weight,
then the first full-width plate.

Unresolved: whether the exit index should shrink to the two or three
destinations this page's own figures point at (critique P2); the chart's
loading state is still the word "Drawing…" in a void.
