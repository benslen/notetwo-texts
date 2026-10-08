# NoteTwo Texts

A catalog of religious and sacred texts that are free to read, grouped by religion, with where to
download each one. [NoteTwo](https://github.com/benslen/NoteTwo) reads it to offer these texts
for reading and reflection; anyone else is welcome to use it too.

**[catalog.json](catalog.json)**: 16 religions and about 1,150 editions, including:

- **Bibles:** every freely shareable translation on [eBible.org](https://ebible.org) with at least a
  whole testament. That's 30 public-domain English Bibles (KJV, ASV, WEB, Young's, Darby, Douay–Rheims,
  Geneva 1599, Webster, Tyndale and more), the Hebrew, Greek, Latin and Coptic texts, and translations in
  more than 850 languages.
- **Tanakh:** JPS 1917, Leeser, the Westminster Leningrad Codex, and Targum Onkelos.
- **Qur'an:** the Arabic text from the [Tanzil Project](https://tanzil.net), and Pickthall, Yusuf Ali,
  Shakir, Rodwell, Sale and Dutch translations.
- **The other religions' texts:**
  - Buddhist sutras, Hindu scripture, Taoist and Confucian classics.
  - Bahá'í writings, the Book of Mormon, and the Book of Enoch.
  - Sikh, Jain, Zoroastrian and Shinto scriptures, and older traditions' texts: Egyptian, Maya and Norse.

The texts themselves aren't stored here; each entry links to its publisher.

## The format

```jsonc
{
  "schema": 1,
  "updated": "2026-10-07",
  "books": { "GEN": "Genesis", … },    // eBible.org's verse-file book codes
  "surahs": ["Al-Fatihah", …],          // the 114 surahs, for Tanzil files
  "religions": [
    {
      "id": "buddhism",
      "name": "Buddhism",
      "editions": [
        {
          "id": "gutenberg:2017",        // stable; apps can keep it
          "work": "Dhammapada",          // the text, shared by its translations
          "title": "Dhammapada",
          "translator": "F. Max Müller",
          "year": "1881",
          "language": "en",              // BCP 47
          "languageName": "English",
          "direction": "ltr",
          "format": "gutenberg",
          "url": "https://www.gutenberg.org/cache/epub/2017/pg2017.txt",
          "source": "https://www.gutenberg.org/ebooks/2017",
          "publisher": "Project Gutenberg",
          "license": "Public domain in the United States",
          "size": 86438,
          "headings": { "pattern": "^Chapter [IVXLC]+\\. .*$" }
        }
      ]
    }
  ]
}
```

**Formats:**

| `format` | What the download is |
| --- | --- |
| `usfm-verses` | A zip; `file` inside it has one verse per line: `GEN 1:1 In the beginning…` |
| `tanzil` | One verse per line: `1|1|بِسْمِ ٱللَّهِ…`; lines starting `#` are notes |
| `gutenberg` | Project Gutenberg plain text; the text runs between its `*** START` and `*** END` lines |
| `plain` | Plain text. `scanned: true` means it was read from page images, so expect occasional misread words |

**`headings`:**
- `pattern` is a regular expression, matched across the whole text in multi-line mode, and each match starts a section.
- Sections are titled by `title`, with `$1` standing for the first group, or by the matched line.
- Texts without `headings` can be split however suits the reader.

## Updating it

```sh
python3 scripts/build_catalog.py --refresh   # rebuild from sources/ and eBible.org's list
python3 scripts/check_catalog.py --deep      # check links, and that each text reads and splits
```

Hand-picked editions live in [sources/curated.json](sources/curated.json); eBible.org translations
are added automatically. A weekly GitHub Action checks that every link still works.
