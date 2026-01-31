# Tauri Icons

This directory should contain the following icon files for the Slovo application:

## Required Files

- `32x32.png` - Small icon (32x32 pixels)
- `128x128.png` - Medium icon (128x128 pixels)
- `128x128@2x.png` - Retina medium icon (256x256 pixels)
- `icon.icns` - macOS icon bundle
- `icon.ico` - Windows icon bundle
- `icon.png` - Base PNG icon (512x512 or larger)

## Generating Icons

You can use the Tauri icon generator:

```bash
pnpm tauri icon path/to/your/icon.png
```

Or manually create the icons using an image editor.

## Design Guidelines

- Use a simple, recognizable design
- Ensure good contrast at small sizes
- Include padding for macOS rounded corners
- Test visibility against both light and dark backgrounds
