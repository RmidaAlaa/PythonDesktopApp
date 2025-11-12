import os
import glob
import subprocess
import platform
import ctypes
import webbrowser
import string
from pathlib import Path
from typing import Optional, Tuple

# Windows registry access (only used on Windows)
try:
    import winreg  # type: ignore
except Exception:
    winreg = None  # Non-Windows or restricted env


def find_stm32cubeide_exe() -> Path | None:
    """Locate STM32CubeIDE executable on Windows as robustly as possible.

    Detection order:
    1) Environment variables: `STM32CUBEIDE_BIN` (exe path) or `STM32CUBEIDE_HOME` (install dir)
    2) Windows Registry (Uninstall keys, DisplayIcon, InstallLocation)
    3) Common install paths on disk
    4) PATH lookup
    """
    # 1) Env var override
    env_path = os.environ.get("STM32CUBEIDE_BIN") or os.environ.get("STM32CubeIDE_BIN")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    env_home = os.environ.get("STM32CUBEIDE_HOME") or os.environ.get("STM32CubeIDE_HOME")
    if env_home:
        home = Path(env_home)
        for candidate in (
            home / "STM32CubeIDE.exe",
            home / "stm32cubeide.exe",
            home / "STM32CubeIDE" / "STM32CubeIDE.exe",
            home / "STM32CubeIDE" / "stm32cubeide.exe",
        ):
            if candidate.is_file():
                return candidate

    candidates: list[Path] = []

    # 2) Windows Registry lookup
    exe_from_registry = _find_cubeide_from_registry()
    if exe_from_registry:
        return exe_from_registry

    # 3) Common ST install directories (current system drive)
    patterns = [
        r"C:\\ST\\STM32CubeIDE*\\STM32CubeIDE\\stm32cubeide.exe",
        r"C:\\Program Files\\ST\\STM32CubeIDE*\\STM32CubeIDE\\stm32cubeide.exe",
        r"C:\\Program Files (x86)\\ST\\STM32CubeIDE*\\STM32CubeIDE\\stm32cubeide.exe",
        r"C:\\Program Files\\STMicroelectronics\\STM32CubeIDE\\STM32CubeIDE.exe",
        r"C:\\Program Files (x86)\\STMicroelectronics\\STM32CubeIDE\\STM32CubeIDE.exe",
        r"C:\\Users\\*\\AppData\\Local\\Programs\\ST*\\STM32CubeIDE\\STM32CubeIDE.exe",
    ]
    for pattern in patterns:
        for match in glob.glob(pattern):
            candidates.append(Path(match))

    # Return the first existing candidate
    for c in candidates:
        if c.is_file():
            return c

    # 4) Fallback: try on PATH
    for name in ("stm32cubeide.exe", "stm32cubeide"):
        exe_path = shutil_which(name)
        if exe_path:
            return Path(exe_path)

    return None


def list_logical_drives() -> list[str]:
    """Enumerate Windows logical drives as drive roots like 'C:\\'."""
    if platform.system() != "Windows":
        return ['/']
    drives: list[str] = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                drives.append(f"{string.ascii_uppercase[i]}:\\")
    except Exception:
        # fallback: probe common letters
        for ch in string.ascii_uppercase:
            root = f"{ch}:\\"
            try:
                if Path(root).exists():
                    drives.append(root)
            except Exception:
                pass
    return drives


def _search_cubeide_on_drives() -> dict[str, list[Path]]:
    """Search all drives for STM32CubeIDE executable using known patterns."""
    results: dict[str, list[Path]] = {}
    for root in list_logical_drives():
        found: list[Path] = []
        patterns = [
            # Common vendor paths
            os.path.join(root, "ST", "STM32CubeIDE*", "STM32CubeIDE", "stm32cubeide.exe"),
            os.path.join(root, "Program Files", "ST", "STM32CubeIDE*", "STM32CubeIDE", "stm32cubeide.exe"),
            os.path.join(root, "Program Files", "STMicroelectronics", "STM32CubeIDE", "STM32CubeIDE.exe"),
            os.path.join(root, "Program Files (x86)", "ST", "STM32CubeIDE*", "STM32CubeIDE", "stm32cubeide.exe"),
            os.path.join(root, "Program Files (x86)", "STMicroelectronics", "STM32CubeIDE", "STM32CubeIDE.exe"),
            os.path.join(root, "Users", "*", "AppData", "Local", "Programs", "ST*", "STM32CubeIDE", "STM32CubeIDE.exe"),
            # Root-level installs (e.g., D:\STM32CubeIDE_1.15.0\STM32CubeIDE\STM32CubeIDE.exe)
            os.path.join(root, "STM32CubeIDE*", "STM32CubeIDE", "STM32CubeIDE.exe"),
            os.path.join(root, "*", "STM32CubeIDE*", "STM32CubeIDE", "STM32CubeIDE.exe"),
            os.path.join(root, "*", "ST*", "STM32CubeIDE*", "STM32CubeIDE", "STM32CubeIDE.exe"),
            os.path.join(root, "*", "STMicroelectronics", "STM32CubeIDE", "STM32CubeIDE.exe"),
        ]
        for pattern in patterns:
            try:
                for match in glob.glob(pattern):
                    p = Path(match)
                    if p.is_file():
                        found.append(p)
            except Exception:
                pass
        # As a last resort per drive, do a bounded recursive search up to depth 3
        if not found:
            try:
                max_hits = 3
                max_dirs = 2000
                dirs_seen = 0
                for dirpath, dirnames, filenames in os.walk(root):
                    # Bound recursion depth to avoid scanning entire drive
                    try:
                        rel = Path(dirpath).relative_to(root)
                        depth = len(rel.parts)
                    except Exception:
                        depth = 0
                    if depth > 3:
                        # prune deeper directories
                        dirnames[:] = []
                        continue
                    if "STM32CubeIDE.exe" in filenames:
                        p = Path(dirpath) / "STM32CubeIDE.exe"
                        if p.is_file():
                            found.append(p)
                            if len(found) >= max_hits:
                                break
                    dirs_seen += 1
                    if dirs_seen >= max_dirs:
                        break
            except Exception:
                pass
        if found:
            results[root] = found
    return results


def find_stm32cubeide_exe_for_project(project_dir: Path) -> Path | None:
    """Find IDE exe, preferring an install on the same drive as the project."""
    # First, use existing robust search (env/registry/filesystem/PATH)
    exe = find_stm32cubeide_exe()
    if exe:
        return exe

    # Then scan across drives
    drive_map = _search_cubeide_on_drives()
    if not drive_map:
        return None

    # Prefer same drive as project
    proj_drive = project_dir.drive + "\\" if project_dir.drive else None
    if proj_drive and proj_drive in drive_map:
        return drive_map[proj_drive][0]

    # Otherwise, return the first found
    for _, paths in drive_map.items():
        if paths:
            return paths[0]
    return None


def _find_cubeide_console(exe_gui: Path) -> Optional[Path]:
    """Try to locate the CubeIDE console executable (stm32cubeidec.exe).

    Improves detection by scanning common install locations and case variations,
    and by falling back to Eclipse console (eclipsec.exe) if present.
    """
    # 1) Same directory as GUI exe
    for name in ("stm32cubeidec.exe", "STM32CubeIDEc.exe", "stm32cubeidec"):
        cand = exe_gui.parent / name
        if cand.exists():
            return cand

    # 2) PATH lookup
    p = shutil_which("stm32cubeidec.exe") or shutil_which("stm32cubeidec")
    if p:
        return Path(p)

    # 3) Try Eclipse console near GUI
    for name in ("eclipsec.exe", "eclipsec"):
        cand = exe_gui.parent / name
        if cand.exists():
            return cand

    # 4) Search common locations across drives similar to GUI search
    try:
        patterns = [
            r"C:\\ST\\STM32CubeIDE*\\STM32CubeIDE\\stm32cubeidec.exe",
            r"C:\\Program Files\\ST\\STM32CubeIDE*\\STM32CubeIDE\\stm32cubeidec.exe",
            r"C:\\Program Files (x86)\\ST\\STM32CubeIDE*\\STM32CubeIDE\\stm32cubeidec.exe",
            r"C:\\Program Files\\STMicroelectronics\\STM32CubeIDE\\stm32cubeidec.exe",
            r"C:\\Program Files (x86)\\STMicroelectronics\\STM32CubeIDE\\stm32cubeidec.exe",
        ]
        for pattern in patterns:
            for match in glob.glob(pattern):
                pth = Path(match)
                if pth.exists():
                    return pth
    except Exception:
        pass
    return None


def _default_workspace_for(project_dir: Path) -> Path:
    """Choose a workspace directory, preferring the project's drive."""
    try:
        drive = project_dir.drive
        if drive:
            # e.g., D:\AWG-Kumulus-Workspace
            ws = Path(drive + os.sep) / "AWG-Kumulus-Workspace"
            ws.mkdir(parents=True, exist_ok=True)
            return ws
    except Exception:
        pass
    # Fallback to home
    ws = Path.home() / "AWG-Kumulus-Workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _import_project_into_workspace(console_exe: Path, workspace: Path, project_dir: Path) -> tuple[bool, str]:
    """Attempt to import the project into the workspace using headless CLI.

    Returns (success, message). Not all CubeIDE versions support -import; we try gracefully.
    """
    # Heuristic: only try import if the directory looks like an Eclipse project
    looks_like_project = (project_dir / ".project").exists()
    effective_dir = project_dir
    if not looks_like_project:
        # Try to find a subfolder that contains a valid Eclipse project
        try:
            max_dirs = 2000
            seen = 0
            for dirpath, dirnames, filenames in os.walk(project_dir):
                # Limit search depth to 2 to avoid scanning large trees
                try:
                    rel = Path(dirpath).relative_to(project_dir)
                    depth = len(rel.parts)
                except Exception:
                    depth = 0
                if depth > 2:
                    dirnames[:] = []
                    continue
                if ".project" in filenames:
                    effective_dir = Path(dirpath)
                    looks_like_project = True
                    break
                seen += 1
                if seen >= max_dirs:
                    break
        except Exception:
            pass
    if not looks_like_project:
        return False, "Selected folder is not an Eclipse project (.project missing)."

    # Some installations provide eclipsec.exe instead of stm32cubeidec.exe; both accept the same flags.
    args = [
        str(console_exe),
        "--launcher.suppressErrors",
        "-nosplash",
        "-application",
        "org.eclipse.cdt.managedbuilder.core.headlessbuild",
        "-data",
        str(workspace),
        "-import",
        str(effective_dir),
    ]
    try:
        # Run import, allow non-zero exit to be treated as failure
        res = subprocess.run(args, cwd=str(workspace))
        if res.returncode == 0:
            return True, "Project imported into workspace."
        return False, f"Import command returned {res.returncode}."
    except Exception as e:
        return False, f"Import failed: {e}"


def _find_cubeide_from_registry() -> Optional[Path]:
    """Search Windows Registry for STM32CubeIDE install location or executable.

    Looks under Uninstall keys for entries containing 'STM32CubeIDE'.
    """
    if winreg is None:
        return None

    uninstall_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]

    hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]

    def _read_value(key, name) -> Optional[str]:
        try:
            val, _ = winreg.QueryValueEx(key, name)
            if isinstance(val, str):
                return val
        except Exception:
            pass
        return None

    def _sanitize_path_str(path_str: str) -> str:
        # Strip quotes and trailing icon index like ",0"
        s = path_str.strip().strip('"')
        if "," in s:
            s = s.split(",", 1)[0]
        return s

    def _is_cubeide_exe(p: Path) -> bool:
        name = p.name.lower()
        # Only accept the IDE executable, avoid uninstallers
        return name == "stm32cubeide.exe"

    for hive in hives:
        for sub_path in uninstall_paths:
            try:
                root = winreg.OpenKey(hive, sub_path)
            except Exception:
                continue

            # Enumerate subkeys
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(root, i)
                    i += 1
                except OSError:
                    break

                try:
                    app_key = winreg.OpenKey(root, subkey_name)
                except Exception:
                    continue

                display_name = _read_value(app_key, "DisplayName")
                uninstall_str = _read_value(app_key, "UninstallString")
                display_icon = _read_value(app_key, "DisplayIcon")
                install_location = _read_value(app_key, "InstallLocation")

                texts = " ".join(filter(None, [display_name, uninstall_str, display_icon]))
                if texts and "STM32CubeIDE" in texts:
                    # Prefer DisplayIcon only if it points to the IDE exe
                    if display_icon:
                        icon_clean = _sanitize_path_str(display_icon)
                        icon_path = Path(icon_clean)
                        if icon_path.is_file() and _is_cubeide_exe(icon_path):
                            return icon_path

                    # Try InstallLocation
                    if install_location:
                        inst = Path(install_location)
                        for candidate in (
                            inst / "STM32CubeIDE.exe",
                            inst / "stm32cubeide.exe",
                            inst / "STM32CubeIDE" / "STM32CubeIDE.exe",
                            inst / "STM32CubeIDE" / "stm32cubeide.exe",
                        ):
                            if candidate.is_file() and _is_cubeide_exe(candidate):
                                return candidate

    return None


def shutil_which(cmd: str) -> str | None:
    try:
        from shutil import which
        return which(cmd)
    except Exception:
        return None


def launch_stm32cubeide(project_dir: Path, workspace_override: Optional[Path] = None) -> tuple[bool, str]:
    """Launch STM32CubeIDE and show the selected project.

    Strategy:
    - Locate CubeIDE GUI exe
    - Prepare a workspace (prefer same drive as project)
    - If console exe available, attempt to import the project headlessly
    - Launch GUI pointing to that workspace. If import unsupported, user can Import from File menu.
    Returns (success, message).
    """
    exe = find_stm32cubeide_exe_for_project(project_dir)
    if not exe:
        # Direct user to installation page
        try:
            webbrowser.open("https://www.st.com/en/development-tools/stm32cubeide.html")
        except Exception:
            pass
        return False, (
            "STM32CubeIDE not found across system partitions. The installation page has been opened. "
            "Alternatively, set STM32CUBEIDE_BIN to the full exe path (or STM32CUBEIDE_HOME to the install directory)."
        )

    # Prepare workspace and attempt import
    # Env override: CUBEIDE_WORKSPACE (takes precedence when no explicit override provided)
    if workspace_override is None:
        env_ws = os.environ.get("CUBEIDE_WORKSPACE") or os.environ.get("STM32CUBEIDE_WORKSPACE")
        if env_ws:
            try:
                ws_path = Path(env_ws)
                ws_path.mkdir(parents=True, exist_ok=True)
                workspace = ws_path
            except Exception:
                workspace = _default_workspace_for(project_dir)
        else:
            workspace = _default_workspace_for(project_dir)
    else:
        workspace = workspace_override
    console = _find_cubeide_console(exe)
    import_msg = ""
    if console:
        imp_ok, imp_msg = _import_project_into_workspace(console, workspace, project_dir)
        import_msg = imp_msg
    else:
        import_msg = "Console executable not found; skipping auto-import."

    params = f'-data "{str(workspace)}"'
    try:
        subprocess.Popen([str(exe), "-data", str(workspace)], cwd=str(workspace))
        base_msg = "STM32CubeIDE launched."
        if import_msg:
            base_msg += f" {import_msg}"
        return True, base_msg
    except Exception as e:
        # On Windows, handle UAC elevation requirement (WinError 740)
        if platform.system() == "Windows":
            winerr = getattr(e, 'winerror', None)
            msg = str(e)
            if winerr == 740 or ("requires elevation" in msg.lower()):
                ok, se_msg = _shell_execute_launch(exe, params, workspace, elevate=True)
                if ok:
                    return True, "STM32CubeIDE launched with elevation (UAC). " + import_msg
                return False, f"Failed to launch STM32CubeIDE with elevation: {se_msg}"
            # Try non-elevated ShellExecute as a secondary fallback
            ok, se_msg = _shell_execute_launch(exe, params, workspace, elevate=False)
            if ok:
                return True, "STM32CubeIDE launched. " + import_msg
            return False, f"Failed to launch STM32CubeIDE: {e} | ShellExecute: {se_msg}"
        return False, f"Failed to launch STM32CubeIDE: {e}"


def stm32cubeide_install_status() -> Tuple[bool, Optional[Path], str]:
    """Return installation status tuple: (installed, path, source).

    source is one of: env, registry, filesystem, path
    """
    # Try each method and report source
    env_path = os.environ.get("STM32CUBEIDE_BIN") or os.environ.get("STM32CubeIDE_BIN")
    if env_path and Path(env_path).is_file():
        return True, Path(env_path), "env"

    env_home = os.environ.get("STM32CUBEIDE_HOME") or os.environ.get("STM32CubeIDE_HOME")
    if env_home:
        home = Path(env_home)
        for candidate in (
            home / "STM32CubeIDE.exe",
            home / "stm32cubeide.exe",
            home / "STM32CubeIDE" / "STM32CubeIDE.exe",
            home / "STM32CubeIDE" / "stm32cubeide.exe",
        ):
            if candidate.is_file():
                return True, candidate, "env"

    reg = _find_cubeide_from_registry()
    if reg:
        return True, reg, "registry"

    exe = find_stm32cubeide_exe()
    if exe:
        # Determine likely source
        src = "filesystem"
        return True, exe, src

    # Cross-drive scan (e.g., installs on D:) for status reporting
    drive_map = _search_cubeide_on_drives()
    for _, paths in drive_map.items():
        if paths:
            return True, paths[0], "filesystem"

    # PATH lookup
    p = shutil_which("stm32cubeide.exe") or shutil_which("stm32cubeide")
    if p:
        return True, Path(p), "path"

    return False, None, "none"


def _shell_execute_launch(exe: Path, params: str, cwd: Path, elevate: bool = False) -> Tuple[bool, str]:
    """Launch an executable using Windows ShellExecuteW.

    Returns (success, message). Elevate via UAC when requested.
    """
    if platform.system() != "Windows":
        return False, "ShellExecuteW only available on Windows"

    try:
        ShellExecuteW = ctypes.windll.shell32.ShellExecuteW  # type: ignore[attr-defined]
    except Exception as e:
        return False, f"ShellExecuteW unavailable: {e}"

    SW_SHOWNORMAL = 1
    verb = "runas" if elevate else "open"

    try:
        rc = ShellExecuteW(None, verb, str(exe), params, str(cwd), SW_SHOWNORMAL)
        # Per WinAPI: returns > 32 on success, otherwise an error code
        if rc > 32:
            return True, "OK"
        return False, f"ShellExecuteW error code: {rc}"
    except Exception as e:
        return False, f"ShellExecuteW failed: {e}"