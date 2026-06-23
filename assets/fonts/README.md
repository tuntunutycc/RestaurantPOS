# Kitchen Print Fonts

Place Myanmar-capable Unicode fonts in this folder so image-rendered kitchen tickets can use them without `.env` font configuration.

Recommended file:

```text
NotoSansMyanmar-Regular.ttf
```

The renderer auto-detects preferred bundled fonts in this order:

1. `assets/fonts/`
2. `static/fonts/`
3. common system font paths
4. Pillow default font as a last fallback

For reliable Myanmar ticket output, use `render_mode=image` in Kitchen Printer Settings and restart the server after adding font files.
