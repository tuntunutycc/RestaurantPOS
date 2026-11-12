# Kitchen Print Fonts

Place kitchen print fonts in this folder so image-rendered kitchen tickets can use them without `.env` font configuration.

Recommended / bundled files:

```text
Pyidaungsu.ttf                      # preferred Myanmar (bundled; MCF Pyidaungsu 2.5.3 Regular)
Pyidaungsu-2.5.3_Regular.ttf        # same font, versioned filename
NotoSansMyanmar-Regular.ttf         # Myanmar fallback
NotoSans-Regular.ttf                # Latin/digit fallback
NOTICE-Pyidaungsu.txt               # Pyidaungsu attribution
OFL-NotoSansMyanmar.txt / OFL-NotoSans.txt
```

`Pyidaungsu.ttf` is preferred for Myanmar Unicode on kitchen tickets and cashier receipts (image mode).
`NotoSansMyanmar-Regular.ttf` remains as a fallback if Pyidaungsu is not present.
`NotoSans-Regular.ttf` is used as the Latin/digit/punctuation fallback so English labels and symbols do not render as square boxes.

The renderer auto-detects preferred bundled fonts in this order:

1. `KITCHEN_PRINT_FONT_PATH` override, when configured
2. preferred bundled Myanmar fonts in `assets/fonts/` / `static/fonts/` (**Pyidaungsu first**, then Noto Myanmar)
3. bundled Latin fallback fonts in `assets/fonts/` / `static/fonts/`
4. common system font paths
5. Pillow default font as a last fallback

For reliable Myanmar ticket/receipt output, use `render_mode=image` in Kitchen Printer Settings and restart the server after adding font files.

The log line `Loaded kitchen print Myanmar font: ...` appears only when a receipt/ticket is printed in **image** mode. It does not appear at server startup, and never appears in text mode.
