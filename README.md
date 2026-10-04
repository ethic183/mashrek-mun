# Mashrek MUN ’26 Website

Official website of Mashrek Model United Nations 2026, *The Narratives of Power*.

It's a fully static site: plain HTML, CSS and a small JavaScript file. It needs no database or server code, so it can be hosted anywhere for free.

## Live site

**https://ethic183.github.io/mashrek-mun/** (hosted free on GitHub Pages from the `main` branch of
https://github.com/ethic183/mashrek-mun).

### Publishing an update
1. Edit `config.json` (or add a guide), then rebuild:
   ```
   python3 build.py
   ```
2. Upload the change:
   ```
   git add -A && git commit -m "Describe the change" && git push
   ```
3. GitHub republishes the site automatically in about a minute.

Using a custom domain later? Set it in the repository's **Settings → Pages → Custom domain**, then change
`"site_url"` in `config.json` to the new address and rebuild.

## Folder contents

| Path | What it is |
|---|---|
| `index.html`, `*.html` | The generated pages. **These are what you upload.** |
| `config.json` | **Everything you edit**: contact info, application links, guide links, schedule, committees |
| `content/<committee>.html` | Full study guides shown on committee pages (the GA guide is here now) |
| `build.py` | Regenerates all pages from `config.json` + `content/` |
| `tools/docx2guide.py` | Turns a Word topic brief into a committee study-guide page |
| `css/style.css`, `js/site.js` | Design and interactions |
| `assets/` | Logo, favicons and the social-share image |

## Updating the site

1. Edit `config.json` (or add a guide to `content/`).
2. Run:
   ```
   python3 build.py
   ```
3. Upload or push the folder again.

Don't edit the generated `.html` pages directly. The next build overwrites them.

### Contact info
```json
"contact": {
  "email": "mun@example.com",
  "instagram": "mashrekmun",
  "phone": "+962 6 000 0000",
  "location": "Mashrek International School"
}
```
Empty fields are hidden automatically.

### Application links
```json
"applications": [
  { "title": "Delegate Application", "url": "https://forms.gle/…", "deadline": "15 October" }
]
```
The home page status updates automatically (e.g. "2 open now").

### Study guides from Word (.docx)
Convert a topic brief written in the "MUN Topic Description Structure" format straight into its committee page:
```
python3 tools/docx2guide.py "~/Downloads/WHO Topic Brief.docx" world-health-organization
python3 tools/docx2guide.py "~/Downloads/GPC Topic Brief.docx" global-press-council
python3 build.py
```
Bold paragraphs become headings, bullet lists stay lists, and bold words stay bold. Arabic briefs are laid out
right-to-left automatically. The committee's card, the Guides page and the home-page count all update themselves.

Plain-text briefs work too (e.g. pasted into a `.txt` file). The WHO and Global Press Council sources are kept in
`content/source/` — edit them and re-run the converter to update those pages.

### Study guides (other options)
Pick either option, or use both:
- **PDF / Google Doc:** set that committee's `"guide_url"` in `config.json`. A download button appears on the committee page and on the Guides page.
- **Full page on the site:** create `content/<slug>.html`, using `content/general-assembly.html` as the template. The committee page will show the full guide with a contents sidebar.

### Schedule
```json
"schedule": [
  { "day": "Day One — Thursday 12 November", "events": [
    { "time": "08:00", "title": "Registration", "place": "Main hall" },
    { "time": "09:00", "title": "Opening Ceremony" }
  ]}
]
```

### Theme film
The home page's "Theme Reveal" section plays `assets/theme-film.mp4`. To replace it, overwrite that file, or change
`"theme_video"` / `"theme_video_poster"` in `config.json`. Set `"theme_video": ""` to remove the section.

The film contains third-party news footage (CBS News, Framepool, and others). It plays muted while on screen (with Mute and Pause buttons) and has a content note.
If the organisers prefer not to host that footage, remove the section and link to the Instagram post instead.

### Your domain
Once you know the web address, set it and rebuild:
```json
"site_url": "https://mashrekmun.com"
```
This turns on the canonical links, full social-share previews (WhatsApp, Instagram, iMessage), `sitemap.xml` and structured data for Google.

## Hosting (pick one)

- **Netlify:** drag the folder onto <https://app.netlify.com/drop>. It's live in seconds, and you can add a custom domain in the settings.
- **GitHub Pages:** push the folder to a repository, then go to Settings → Pages → Deploy from branch → `main` / root. Use a custom domain, or set `site_url` to `https://<user>.github.io/<repo>` so the 404 page resolves correctly.
- **Vercel / Cloudflare Pages:** import the folder. There's no build command, and the output directory is the root.
- **School server / cPanel:** upload everything except `build.py`, `config.json`, `content/` and `README.md`. Uploading those too is harmless.

`404.html` is picked up automatically by Netlify, GitHub Pages, Vercel and Cloudflare.
