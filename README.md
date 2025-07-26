# nwnee-data-utilities

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
![platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

---

A collection of utilities for Neverwinter Nights: Enhanced Edition (NWNEE) data handling, powered by [nwn.py](https://github.com/niv/nwn.py).

This project offers multiple usage options depending on your needs and technical preferences. All workflows expose the same capabilities — only the setup and integration differ.

---

Detailed information about the text formats used by some of these utilities is available in the [FORMATS.md](./FORMATS.md) file.

---

## Workflows
### 🧪 1. Compiled Utilities (Click-and-Run)

These standalone executables require **no setup or installation**. Just download and run.

- Each utility creates its own `{utility name}/` folder on first launch. Example:
  ```
  batch_convert_gff_to_ndugff/
    input/
    output/
  ```
- Drop your game resources into the `input/` folder.
- Run the tool and collect results from the `output/` folder.
- Default behaviors (like config generation, if necessary) are handled automatically on first run.

> Recommended for players, modders, or tool users who don’t want to install Python.

---

### 🐍 2. Python Package (Scriptable API)

Use this option if you want to **write your own Python scripts** using the utility library.

- Install dependencies using:
  ```
  pip install -r requirements.txt
  ```
- Then import and use the unified interface:
  ```python
  from ndu import App

  app = App() # create an instance to initialize it
  with app.log():
      app.gff.single.load_gff(...).write_json(...)
  ```

This exposes powerful batch and single-file methods, file format tools, and high-level ERF/KEY/BIF manipulation. See [`App`](#app-structure) for structure.

> Ideal for technical users and automation workflows.

---

### 🛠 3. Clone and Hack (Developer Mode)

For those who want to dig deeper, extend functionality, or contribute:

- Clone the repo:
  ```
  git clone https://github.com/YOURNAME/nwnee-data-utilities.git
  cd nwnee-data-utilities
  ```
- The project is compatible with [uv](https://github.com/astral-sh/uv), [pip-tools](https://github.com/jazzband/pip-tools), and traditional virtualenv workflows.
- A `pyproject.toml` is included with full dependency metadata and tool configuration.

> Suitable for contributors, maintainers, and advanced tinkerers.

---

## App Structure

The `App` class is the public interface for all workflows. It organizes functionality into logical namespaces:

### `App.keybif`
- `export_game_resources`
- `write_default_recipes`

### `App.erf`
- `erf.batch.extract_erf_to_folder`
- `erf.batch.create_erf_from_folder`
- `erf.single.extract_erf_to_folder`
- `erf.single.create_erf_from_folder`

### `App.gff`
- **Batch methods**:
  - `convert_gff_to_json`
  - `convert_json_to_gff`
  - `convert_gff_to_ndugff`
  - `convert_ndugff_to_gff`
  - `convert_json_to_ndugff`
  - `convert_ndugff_to_json`
- **Single file I/O**:
  - `load_gff`, `load_json`, `load_ndugff`
  - `write_gff`, `write_json`, `write_ndugff`
- **Tools**:
  - `is_gff_file`, `is_ndugff_file`, `is_json_file`
  - `is_erf_file`, `is_erf_folder`

---

## License

MIT License. See [LICENSE](./LICENSE).

---

## Contacts

[![Discord](https://img.shields.io/badge/Discord-Join%20Chat-7289DA?logo=discord&logoColor=white&style=flat-square)](https://discord.gg/h5c6VGPK45)
