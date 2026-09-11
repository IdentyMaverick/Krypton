# Krypton

<img width="2400" height="1792" alt="logo-transparent" src="https://github.com/user-attachments/assets/942962e0-84ca-448b-99a3-a9db835e1687" />

[![Version](https://img.shields.io/github/v/release/IdentyMaverick/Krypton?label=version)](https://github.com/IdentyMaverick/Krypton/releases)

Windows 11 all-in-one setup designer. Current version is **1.0.1**. Pick apps from the catalog, add anything that is missing, then export a double-click setup program that installs exactly that set on a new PC.

Krypton does **not** replace Windows Setup and does **not** ship other vendors’ installers in this repo. It writes a small bundle that uses [winget](https://learn.microsoft.com/windows/package-manager/winget/) (and optional https / local installers you add) on the target machine.

## What you get

1. **Designer** — a local web UI to search, tick, and add apps, plus a few Windows 11 Explorer/taskbar options.
2. **Presets** — Essential, Office & home, Developer, Creator, Gamer, Privacy & security. Those are starting points; you can still tick or untick anything.
3. **Custom apps** — winget package id, an https installer URL, or a file you place next to `Install.cmd`.
4. **Exported setup program** — a zip/folder with `Install.cmd`, `Install-Bundle.ps1`, and `bundle.json`. Copy it to the Windows 11 PC and run `Install.cmd` as administrator.

## Design a setup (any OS)

Python 3.12+ is enough to open the designer:

```bash
python3 -m krypton serve
```

Check the installed/program version:

```bash
python3 -m krypton --version
```

Or:

```bash
python3 tools/serve.py
```

The designer opens at [http://127.0.0.1:8787/](http://127.0.0.1:8787/). Select apps, optionally load a preset, add custom installers, then **Export setup program**.

Export a bundle from a saved profile without the UI:

```bash
python3 -m krypton validate
python3 -m krypton export samples/developer.json -o dist --zip
```

## Run the setup (Windows 11)

1. Extract the exported folder onto the PC (USB is fine).
2. If you added a **local** installer, copy that `.exe` / `.msi` into the folder using the relative path you entered.
3. Right-click `Install.cmd` → **Run as administrator**.
4. Leave the window open until it finishes. Logs go to `%LOCALAPPDATA%\Krypton\logs`.

Requirements on the target PC:

- Windows 11 (build 22000 or newer; older Windows 10 may still run winget installs)
- Administrator rights
- [App Installer / winget](https://apps.microsoft.com/detail/9nblggh4nns1) for catalog apps

On Windows you can also start the designer by double-clicking `engine\Start-Designer.cmd` (no Python). Leave that window open and use http://127.0.0.1:8787/. If a window flashes and closes, run the `.cmd` file — it keeps the error on screen.

## Profile format

```json
{
  "name": "Studio PC",
  "version": 1,
  "apps": [
    "google-chrome",
    "visual-studio-code",
    {
      "id": "custom-ripgrep",
      "name": "ripgrep",
      "source": "winget",
      "package": "BurntSushi.ripgrep.MSVC"
    }
  ],
  "tweaks": ["show-file-extensions", "dark-mode"]
}
```

Custom `url` sources must be `https://`. Custom `local` paths must stay inside the exported folder (`installers/app.exe`), never an absolute path.

## Layout

| Path | Role |
| --- | --- |
| `catalog/` | App list, presets, Windows options |
| `designer/` | Setup designer UI |
| `engine/` | Windows installer and launchers |
| `krypton/` | Catalog validation, bundle export, local server |
| `samples/` | Example profiles |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Screenshots

<img width="1842" height="905" alt="image" src="https://github.com/user-attachments/assets/d8e7d2bc-c8e2-46df-950f-651fa9b8683e" />

<img width="1835" height="908" alt="image" src="https://github.com/user-attachments/assets/d0963ab4-e04f-4d1a-8caa-57e891556561" />


## License

Apache License 2.0. Third-party apps stay under their own licenses; Krypton only records which packages you asked winget (or your installer) to install.
