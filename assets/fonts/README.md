# Kitchen Print Fonts

Place kitchen print fonts in this folder so image-rendered kitchen tickets can use them without `.env` font configuration.

Recommended files:

```text
NotoSansMyanmar-Regular.ttf
NotoSans-Regular.ttf
```

`NotoSansMyanmar-Regular.ttf` is used for Myanmar Unicode characters.
`NotoSans-Regular.ttf` is used as the Latin/digit/punctuation fallback so English labels and symbols do not render as square boxes.

The renderer auto-detects preferred bundled fonts in this order:

1. `KITCHEN_PRINT_FONT_PATH` override, when configured
2. preferred bundled Myanmar fonts in `assets/fonts/` / `static/fonts/`
3. bundled Latin fallback fonts in `assets/fonts/` / `static/fonts/`
4. common system font paths
5. Pillow default font as a last fallback

For reliable Myanmar ticket output, use `render_mode=image` in Kitchen Printer Settings and restart the server after adding font files.
