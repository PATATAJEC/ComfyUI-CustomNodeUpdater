import os
import json
import subprocess
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path
import configparser
import shutil
import stat

BASE_DIR = Path(__file__).resolve().parent
CUSTOM_NODES_DIR = BASE_DIR / 'ComfyUI' / 'custom_nodes'
DB_FILE = BASE_DIR / 'database.json'
PYTHON_EXEC = BASE_DIR / 'python_embeded' / 'python.exe'


def get_git_remote_url(git_config_path):
    config = configparser.ConfigParser()
    config.read(git_config_path, encoding='utf-8')
    try:
        return config['remote "origin"']['url']
    except Exception:
        return None


def get_git_index_mtime(folder):
    index_path = folder / '.git' / 'index'
    if not index_path.exists():
        return None
    try:
        ts = index_path.stat().st_mtime
        return datetime.fromtimestamp(ts)
    except Exception:
        return None


def get_git_current_branch(repo_path: Path):
    """
    Zwraca nazwę aktywnego brancha (string).
    Obsługa 'detached HEAD' i błędów Git.
    """
    try:
        # Najpierw spróbuj standardowo
        res = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path, check=True, capture_output=True, text=True
        )
        name = res.stdout.strip()
        if name and name != 'HEAD':
            return name

        # 'HEAD' -> spróbuj show-current (git 2.22+)
        res2 = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=repo_path, check=False, capture_output=True, text=True
        )
        name2 = (res2.stdout or '').strip()
        if name2:
            return name2

        # nadal nic — odczytaj skrót commita, żeby było coś widać
        res3 = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo_path, check=False, capture_output=True, text=True
        )
        short = (res3.stdout or '').strip()
        return f"detached@{short}" if short else "detached"

    except Exception:
        return "unknown"


def time_since(timestamp_str):
    if not timestamp_str:
        return "unknown"
    try:
        dt = datetime.fromisoformat(timestamp_str)
    except Exception:
        return "invalid timestamp"
    now = datetime.now()
    diff = now - dt
    days = diff.days
    seconds = diff.seconds
    if days > 0:
        return f"{days} day(s) ago"
    elif seconds >= 3600:
        hours = seconds // 3600
        return f"{hours} hour(s) ago"
    elif seconds >= 60:
        minutes = seconds // 60
        return f"{minutes} minute(s) ago"
    else:
        return "just now"


def scan_nodes():
    database = []
    node_id = 1

    if not CUSTOM_NODES_DIR.exists():
        CUSTOM_NODES_DIR.mkdir(parents=True, exist_ok=True)

    for folder in CUSTOM_NODES_DIR.iterdir():
        if not folder.is_dir():
            continue
        git_config_path = folder / '.git' / 'config'
        if not git_config_path.exists():
            continue
        github_url = get_git_remote_url(git_config_path)
        if not github_url:
            continue
        index_time = get_git_index_mtime(folder)
        current_branch = get_git_current_branch(folder)
        entry = {
            "id": node_id,
            "name": folder.name,
            "github_url": github_url,
            "path": str(folder.relative_to(BASE_DIR)),
            "last_update_timestamp": index_time.isoformat() if index_time else "",
            "current_branch": current_branch,
            "selected": False
        }
        database.append(entry)
        node_id += 1

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=4)
    return database


def load_database():
    if DB_FILE.exists():
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_database(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def git_pull(path, log_callback):
    cmd = ['git', 'pull']
    log_callback(f"[CMD] {' '.join(cmd)}  (cwd={path})")
    try:
        result = subprocess.run(cmd, cwd=path, check=True, capture_output=True, text=True)
        log_callback(f"[GIT PULL] {path.name}:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        log_callback(f"[GIT PULL ERROR] {path.name}:\n{e.stderr}")
        return False


def install_requirements(path, log_callback):
    req_path = BASE_DIR / path / 'requirements.txt'
    if req_path.exists():
        python_exec_rel = os.path.relpath(PYTHON_EXEC, BASE_DIR)
        req_path_rel = os.path.relpath(req_path, BASE_DIR)
        cmd = [python_exec_rel, '-m', 'pip', 'install', '-r', req_path_rel]
        log_callback(f"[CMD] {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=BASE_DIR)
            log_callback(f"[INSTALL] {path.name}:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            log_callback(f"[INSTALL ERROR] {path.name}:\n{e.stderr}")
            return False
    else:
        log_callback(f"[SKIP] No requirements.txt in {path.name}")
        return False


def git_clone_repo(url, log_callback):
    try:
        repo_name = url.rstrip('/').split('/')[-1].replace('.git', '')
        target_dir = CUSTOM_NODES_DIR / repo_name
        if target_dir.exists():
            log_callback(f"[SKIP] Folder {repo_name} already exists.")
            return False
        cmd = ['git', 'clone', url, str(target_dir)]
        log_callback(f"[CMD] {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        log_callback(f"[CLONE] {repo_name}:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        log_callback(f"[CLONE ERROR] {url}:\n{e.stderr}")
        return False


def git_update_to_branch(path: Path, branch: str, log_callback):
    if not branch or branch.strip() == "":
        log_callback("[BRANCH] Branch name is empty.")
        return False
    branch = branch.strip()

    try:
        cmd_fetch = ['git', 'fetch', '--all', '--prune']
        log_callback(f"[CMD] {' '.join(cmd_fetch)}  (cwd={path})")
        subprocess.run(cmd_fetch, cwd=path, check=True, capture_output=True, text=True)

        # Try normal switch; if local doesn't exist, create tracking from origin/<branch>
        cmd_switch = ['git', 'switch', branch]
        log_callback(f"[CMD] {' '.join(cmd_switch)}  (cwd={path})")
        res = subprocess.run(cmd_switch, cwd=path, capture_output=True, text=True)
        if res.returncode == 0:
            log_callback(f"[BRANCH] Switched {path.name} to existing local branch '{branch}'.\n{res.stdout}")
            return True

        cmd_switch_track = ['git', 'switch', '-c', branch, '--track', f'origin/{branch}']
        log_callback(f"[CMD] {' '.join(cmd_switch_track)}  (cwd={path})")
        res2 = subprocess.run(cmd_switch_track, cwd=path, check=True, capture_output=True, text=True)
        log_callback(f"[BRANCH] Created and switched {path.name} to '{branch}' tracking origin/{branch}.\n{res2.stdout}")
        return True

    except subprocess.CalledProcessError as e:
        log_callback(f"[BRANCH ERROR] {path.name} -> '{branch}':\n{e.stderr or e.stdout}")
        return False


def on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def delete_node_folder(node_dir: Path, log_callback):
    try:
        node_dir = node_dir.resolve()
        if CUSTOM_NODES_DIR not in node_dir.parents:
            log_callback(f"[DELETE-SAFE] Refusing to remove outside custom_nodes: {node_dir}")
            return False
        if not node_dir.exists():
            log_callback(f"[DELETE] Folder does not exist: {node_dir.name}")
            return False
        shutil.rmtree(node_dir, onerror=on_rm_error)
        log_callback(f"[DELETE] Removed {node_dir.name}")
        return True
    except Exception as e:
        log_callback(f"[DELETE ERROR] {node_dir.name}: {e}")
        return False


class NodeManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Node Updater")
        self.database = load_database()
        self.check_vars = {}
        self.branch_vars = {}

        # === Paned layout (top: controls+list, bottom: console) ===
        self.paned = tk.PanedWindow(self.root, orient='vertical')
        self.paned.pack(fill='both', expand=True)

        # Top pane
        self.top_pane = tk.Frame(self.paned)
        self.paned.add(self.top_pane)

        # Bottom pane (console) – always visible thanks to minsize
        self.bottom_pane = tk.Frame(self.paned)
        self.paned.add(self.bottom_pane, minsize=150)

        self.build_top_ui()
        self.build_console()

        self.draw_nodes()

        # Minimal window size
        self.root.minsize(800, 500)

    # ---------- UI: top (controls + scrollable list) ----------
    def build_top_ui(self):
        # Clone row
        self.clone_frame = tk.Frame(self.top_pane, pady=4)
        self.clone_frame.pack(fill='x')

        self.clone_entry = tk.Entry(self.clone_frame)
        self.clone_entry.pack(side='left', fill='x', expand=True, padx=5)

        self.clone_button = tk.Button(self.clone_frame, text="CLONE NODE", bg="lightgreen", command=self.clone_node)
        self.clone_button.pack(side='right', padx=5)

        # Action buttons
        tk.Button(self.top_pane, text="UPDATE CUSTOM NODE DATABASE", bg="violet",
                  command=self.update_database).pack(fill='x')
        tk.Button(self.top_pane, text="GIT PULL SELECTED", bg="skyblue",
                  command=self.pull_selected).pack(fill='x')
        tk.Button(self.top_pane, text="INSTALL REQUIREMENTS TO SELECTED", bg="orange",
                  command=self.install_selected).pack(fill='x')
        tk.Button(self.top_pane, text="DELETE SELECTED NODES", bg="red", fg="white",
                  command=self.delete_selected).pack(fill='x')

        # Scrollable list container
        self.list_container = tk.Frame(self.top_pane)
        self.list_container.pack(fill='both', expand=True, pady=(4, 0))

        # Canvas + Scrollbar
        self.list_canvas = tk.Canvas(self.list_container, highlightthickness=0)
        self.list_scrollbar = tk.Scrollbar(self.list_container, orient="vertical",
                                           command=self.list_canvas.yview)
        self.list_scrollbar.pack(side='right', fill='y')
        self.list_canvas.pack(side='left', fill='both', expand=True)

        # Inner frame inside the canvas
        self.list_inner = tk.Frame(self.list_canvas)
        self.list_window = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")

        # Keep scrollregion and width in sync
        self.list_inner.bind("<Configure>", lambda e: self._update_scrollregion())
        self.list_canvas.bind("<Configure>", lambda e: self.list_canvas.itemconfig(self.list_window, width=e.width))

        # Robust mouse wheel: bind_all only while cursor is over the list area
        self.list_inner.bind("<Enter>", lambda e: self._bind_wheel())
        self.list_inner.bind("<Leave>", lambda e: self._unbind_wheel())
        self.list_canvas.bind("<Enter>", lambda e: self._bind_wheel())
        self.list_canvas.bind("<Leave>", lambda e: self._unbind_wheel())

        self.list_canvas.configure(yscrollcommand=self.list_scrollbar.set)

    def _bind_wheel(self):
        # Windows/macOS
        self.root.bind_all("<MouseWheel>", self._on_mousewheel_any)
        # Horizontal with Shift (opcjonalne – przydatne, gdy wiersze szerokie)
        self.root.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel_any)
        # Linux
        self.root.bind_all("<Button-4>", self._on_linux_up)
        self.root.bind_all("<Button-5>", self._on_linux_down)

    def _unbind_wheel(self):
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Shift-MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _on_mousewheel_any(self, event):
        # Windows: delta = ±120*n; macOS: małe wartości; kierunek zgodny ze znakiem
        if event.delta == 0:
            return
        steps = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        self.list_canvas.yview_scroll(steps, "units")

    def _on_shift_mousewheel_any(self, event):
        # Shift + Scroll = przewijanie poziome (gdyby było potrzebne)
        if event.delta == 0:
            return
        steps = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        self.list_canvas.xview_scroll(steps, "units")

    def _on_linux_up(self, event):
        self.list_canvas.yview_scroll(-1, "units")

    def _on_linux_down(self, event):
        self.list_canvas.yview_scroll(1, "units")

    def _update_scrollregion(self):
        self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))

    # ---------- UI: bottom (console) ----------
    def build_console(self):
        self.text_frame = tk.Frame(self.bottom_pane)
        self.text_frame.pack(fill='both', expand=True)

        self.log_text = tk.Text(self.text_frame, height=10, bg="black", fg="white", wrap='none')
        self.log_text.pack(side='left', fill='both', expand=True)

        scrollbar = tk.Scrollbar(self.text_frame, command=self.log_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_text['yscrollcommand'] = scrollbar.set

    # ---------- Nodes drawing ----------
    def draw_nodes(self):
        # wipe current rows
        for w in self.list_inner.winfo_children():
            w.destroy()

        self.check_vars.clear()
        self.branch_vars.clear()

        for entry in self.database:
            var = tk.BooleanVar(value=entry.get("selected", False))
            self.check_vars[entry['id']] = var

            row = tk.Frame(self.list_inner, bg="#eeeeee", pady=3)
            row.pack(fill='x')

            tk.Checkbutton(row, variable=var).pack(side='left', padx=5)
            tk.Label(row, text=entry['id'], width=3).pack(side='left')

            # Nazwa (klikalna -> kopiuje URL GitHub) | Branch
            name_label = tk.Label(row, text=entry['name'], width=30, anchor='w', fg="#1a73e8", cursor="hand2")
            name_label.pack(side='left', padx=(5, 0))
            name_label.bind("<Button-1>", lambda e, u=entry.get('github_url', ''): self.copy_url_to_clipboard(u))

            tk.Label(row, text='|', width=1, anchor='center', fg="#888").pack(side='left', padx=(5, 5))
            tk.Label(row, text=entry.get('current_branch', 'unknown'), width=18, anchor='w').pack(side='left')

            tk.Button(row, text="GIT PULL", bg="skyblue",
                      command=lambda p=entry['path']: self.git_pull_one(p)).pack(side='left', padx=(5, 0))
            tk.Button(row, text="INSTALL REQUIREMENTS", bg="orange",
                      command=lambda p=entry['path']: self.install_req_one(p)).pack(side='left', padx=(5, 0))

            # Branch entry + button
            bvar = tk.StringVar(value="")
            self.branch_vars[entry['id']] = bvar
            branch_entry = tk.Entry(row, textvariable=bvar, width=20)
            branch_entry.pack(side='left', padx=5)
            tk.Button(row, text="UPDATE TO BRANCH",
                      command=lambda e=entry, bv=bvar: self.update_branch_one(e, bv.get())).pack(side='left')

            updated = time_since(entry.get("last_update_timestamp", ""))
            tk.Label(row, text=f"updated: {updated}", width=20, anchor='w').pack(side='left', padx=5)

        # update canvas region after (re)draw
        self._update_scrollregion()

    # ---------- Actions ----------
    def update_database(self):
        self.log("Updating database...")
        self.database = scan_nodes()
        self.draw_nodes()
        self.log("Database updated.")

    def pull_selected(self):
        for entry in self.database:
            if self.check_vars.get(entry['id']) and self.check_vars[entry['id']].get():
                git_pull(BASE_DIR / entry['path'], self.log)

    def install_selected(self):
        for entry in self.database:
            if self.check_vars.get(entry['id']) and self.check_vars[entry['id']].get():
                install_requirements(Path(entry['path']), self.log)

    def delete_selected(self):
        selected = [e for e in self.database if self.check_vars.get(e['id']) and self.check_vars[e['id']].get()]
        if not selected:
            messagebox.showinfo("No selection", "Select at least one node to delete.")
            return

        names = ", ".join(e['name'] for e in selected)
        if not messagebox.askyesno("Confirm delete",
                                   f"Are you sure you want to permanently delete selected nodes?\n\n{names}"):
            return

        changed = False
        for entry in selected:
            node_dir = BASE_DIR / entry['path']
            if delete_node_folder(node_dir, self.log):
                changed = True

        if changed:
            self.log("Refreshing node list after deletions...")
            self.database = scan_nodes()
            self.draw_nodes()

    def git_pull_one(self, path):
        git_pull(BASE_DIR / path, self.log)

    def install_req_one(self, path):
        install_requirements(Path(path), self.log)

    def update_branch_one(self, entry, branch_name):
        path = BASE_DIR / entry['path']
        ok = git_update_to_branch(path, branch_name, self.log)
        if ok:
            # po przełączeniu przeskannuj repo, żeby pokazać nowy branch
            self.database = scan_nodes()
            self.draw_nodes()

    def clone_node(self):
        url = self.clone_entry.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please enter a GitHub URL.")
            return
        self.log(f"Cloning node from: {url}")
        success = git_clone_repo(url, self.log)
        if success:
            self.log("Refreshing node list...")
            self.database = scan_nodes()
            self.draw_nodes()

    def copy_url_to_clipboard(self, url: str):
        """Kopiuje adres GitHub do schowka i loguje zdarzenie."""
        if not url:
            self.log("[COPY] No GitHub URL available for this node.")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            # Opcjonalny update, by schowek był natychmiast dostępny
            self.root.update_idletasks()
            self.log(f"[COPIED] GitHub URL copied to clipboard: {url}")
        except Exception as e:
            self.log(f"[COPY ERROR] Failed to copy URL: {e}")

    def log(self, message):
        self.log_text.insert('end', f"{message}\n")
        self.log_text.see('end')


if __name__ == '__main__':
    root = tk.Tk()
    app = NodeManagerApp(root)
    root.mainloop()
