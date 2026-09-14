# Fonts

Self-hosted, subset to Latin, loaded from `app.css` with relative URLs so Vite
fingerprints them and the emitted path carries the project's base.

| File                                  | Family                              | Role                                                         | Licence                               |
| ------------------------------------- | ----------------------------------- | ------------------------------------------------------------ | ------------------------------------- |
| `HankenGrotesk-Variable.woff2`        | Hanken Grotesk, weight axis 100-900 | Every heading, the body, labels, numbers, chart axes         | `LICENSE-HankenGrotesk.txt` (OFL 1.1) |
| `HankenGrotesk-Italic-Variable.woff2` | Hanken Grotesk italic               | Emphasis in running text                                     | same                                  |
| `CourierPrime-Regular.woff2`          | Courier Prime                       | The citation only: meeting symbols, script names, file paths | `LICENSE-CourierPrime.txt` (OFL 1.1)  |

One family for the page and one typewriter face for the citation. Hanken
Grotesk is an Akzidenz-class grotesk, the face of the international-
organisation programmes of the 1960s and 70s that the site's design follows;
Courier Prime is the face the verbatim records themselves were typed in. The
Roman is preloaded from `+layout.svelte`.

The files are the Latin subsets served by Google Fonts (fetched 14 September
2026); the upstream projects are
<https://github.com/marcologous/hanken-grotesk> and
<https://github.com/quoteunquoteapps/CourierPrime>.
