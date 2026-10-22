"""Small filesystem safeguards for the local, file-driven application."""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath


def relative_path(value: object) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError("Expected a non-empty relative filesystem path.")
    text = str(value).replace("\\", "/")
    windows = PureWindowsPath(text)
    path = Path(text)
    if path.is_absolute() or windows.drive or windows.root or ".." in path.parts:
        raise ValueError("Path must stay within its workspace.")
    if any(":" in part or "\x00" in part or part.endswith((" ", "."))
           or PureWindowsPath(part).is_reserved() for part in path.parts):
        raise ValueError("Invalid filesystem path component.")
    return path


def contained_path(root: Path, value: object) -> Path:
    path = root / relative_path(value)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes its workspace (possibly through a symbolic link).")
    return path


def workspace_entries(root: Path):
    """Walk an explicit local root without following escapes or directory cycles."""
    if not root.exists():
        return
    pending = [root]
    visited = set()
    while pending:
        folder = pending.pop()
        resolved = folder.resolve()
        if resolved in visited:
            continue
        visited.add(resolved)
        for path in sorted(folder.iterdir()):
            contained_path(root, path.relative_to(root))
            yield path
            if path.is_dir():
                pending.append(path)


@contextmanager
def atomic_output(path: Path):
    """Publish only a completed file, on the same filesystem as its target."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.stem[:48]}.", suffix=path.suffix, dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def atomic_open(path: Path, mode: str = "w", **kwargs):
    with atomic_output(path) as temporary:
        with temporary.open(mode, **kwargs) as handle:
            yield handle


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    with atomic_open(path, encoding=encoding) as handle:
        handle.write(text)


def atomic_copy(source: Path, target: Path) -> None:
    with atomic_output(target) as temporary:
        shutil.copy2(source, temporary)


@contextmanager
def staged_directory(target: Path):
    """Keep the previous generated directory until its replacement is complete."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    backup = temporary.with_name(temporary.name + ".previous")
    published = False
    try:
        yield temporary
        if target.exists():
            target.rename(backup)
        try:
            temporary.rename(target)
            published = True
        except BaseException:
            if backup.exists():
                backup.rename(target)
            raise
    finally:
        # These paths are created above, directly beneath the target's parent.
        for directory in (temporary, backup) if published else (temporary,):
            if directory.exists():
                if directory.resolve().parent != target.parent.resolve() or directory.is_symlink():
                    raise ValueError("Unexpected generated-directory cleanup path.")
                shutil.rmtree(directory)
