# Custom Node Updater for ComfyUI

A simple desktop tool (Tkinter) to manage ComfyUI custom nodes: clone, update (git pull), switch to a specific branch, install requirements, and delete selected nodes—all with logs and a scrollable list.

<img width="1099" height="903" alt="image" src="https://github.com/user-attachments/assets/7fc62921-ce19-4447-97fa-e5f7e5b9e28b" />

## Features

* **Clone node** from a GitHub URL into `ComfyUI/custom_nodes/`.
* **Update selected** repositories via `git pull`.
* **Install requirements** from each node’s `requirements.txt` using the embedded Python (`python_embeded/python.exe`).
* **Delete selected nodes** safely (restricted to `ComfyUI/custom_nodes/`, with confirmation).
* **Switch to branch**: enter a branch name and update the selected node to that branch (`git fetch --all --prune` + `git switch` or create a tracking branch if needed).
* **Show current branch** next to each node's name (displayed in its own column after the name).
* **Scrollable node list** and **persistent console panel** (split view) so logs remain visible when resizing the window.

Additionally, a convenience launcher script **`run_CustomNodeUpdater.bat`** is included to start the app quickly on Windows.

## Installation (Quick setup)
- Copy **`CustomNodeUpdater.py`** and **`run_CustomNodeUpdater.bat`** into the **root of your ComfyUI folder** — the same directory that contains the `python_embeded/` folder.
- Ensure `python_embeded/python.exe` exists (or update the path in the script if your layout differs).
- Make sure Git is installed (or set a full path/alias if needed).

## Requirements

* **Git** available in your system PATH.
* **Python**: the script uses an embedded interpreter at `python_embeded/python.exe` for installing requirements. Adjust paths if your setup differs.
* A standard ComfyUI folder structure with `ComfyUI/custom_nodes/`.

## Installation

1. Place this repository next to (or inside) your ComfyUI setup so that `ComfyUI/custom_nodes/` is reachable by the script.
2. Ensure `python_embeded/python.exe` exists (or update the path in the script).
3. Make sure Git is installed.
4. (Windows) Double‑click `run_CustomNodeUpdater.bat` to launch; or run the script via Python.

## Usage

1. **Update database** – scans `ComfyUI/custom_nodes/` for Git repos and lists them.
2. **Clone node** – paste a GitHub URL and click *CLONE NODE*.
3. **Select repositories** (checkboxes) and choose:

   * *GIT PULL SELECTED*
   * *INSTALL REQUIREMENTS TO SELECTED*
   * *DELETE SELECTED NODES* (permanent; only inside `custom_nodes/`)
4. **Switch to branch** – in a row’s input field, enter a branch name (e.g., `main`, `dev`, `feature-x`) and click *UPDATE TO BRANCH*.

**Note:** The current branch for each node is displayed next to its name, so you can quickly see what branch is active.

### Branch switching details

* The app runs `git fetch --all --prune`, then tries `git switch <branch>`.
* If the local branch does not exist, it creates it tracking `origin/<branch>`.
* This preserves local changes; it does **not** hard‑reset to `origin/<branch>`.

> If you prefer a force update (local branch exactly equals `origin/<branch>`), you can modify the function to use `git checkout -B <branch> origin/<branch>`.

## Safety notes

* Deletions are confirmed and limited to `ComfyUI/custom_nodes/` to avoid accidental removal outside this folder.
* Logs are shown in a console panel for transparency.

## Troubleshooting

* **Git not found**: ensure Git is installed and accessible in PATH.
* **requirements.txt not found**: some nodes don’t need dependencies; the installer will skip them.
* **Branch not found**: verify the branch name exists on the remote.

## License

MIT License — see `LICENSE` file for details. This allows use, modification, and distribution with minimal restrictions.
