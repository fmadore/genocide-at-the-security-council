# Fonts

Three faces, all under the SIL Open Font License 1.1, vendored as `woff2` and
declared in [`../app.css`](../app.css). They live under `src/` rather than
`static/` so Vite fingerprints them and emits a URL that already carries the
project's base path; project Pages are served from a subpath, where a
root-relative `/fonts/…` would 404.

| File                                | Face                  | Axes                        | Role                                                      |
| ----------------------------------- | --------------------- | --------------------------- | --------------------------------------------------------- |
| `SourceSerif4Variable-Roman.woff2`  | Source Serif 4        | `wght` 200–900, `opsz` 8–60 | Body copy, headlines, every number a reader holds in mind |
| `SourceSerif4Variable-Italic.woff2` | Source Serif 4 Italic | `wght` 200–900, `opsz` 8–60 | Emphasis in prose                                         |
| `Archivo-Variable.woff2`            | Archivo               | `wght` 100–900              | The apparatus: sidenotes, labels, controls, table headers |
| `IBMPlexMono-Regular.woff2`         | IBM Plex Mono         | static, 400                 | Citations: meeting symbols, script names, file paths      |

Latin subsets, taken from the Fontsource 5.3.0 builds
(`@fontsource-variable/source-serif-4`, `@fontsource-variable/archivo`,
`@fontsource/ibm-plex-mono`), which repackage the upstream releases without
modifying the outlines. 302 KB in total.

Copyright and licence terms are in `LICENSE-SourceSerif4.md` (Adobe),
`LICENSE-Archivo.txt` (The Archivo Project Authors) and
`LICENSE-IBMPlexMono.txt` (IBM). The OFL requires these to travel with the
files; they are not covered by the repository's own MIT licence.
