#!/usr/bin/env python3

# File: deezer_downloader/disk_organizer.py
# Editor: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-15
# Description: Detects multi-disk albums from the DISK_NUMBER tag and
#              reorganizes already-downloaded files into CD01/CD02/...
#              subfolders in the background, without blocking the
#              download of the next song.
# License: MIT

import os
import re
import shutil
import threading

# Recognizes CD1, CD01, CD 1, CD_01, Disc2, Disc 02, DISK-3, cd10, ...
# group(1) = the word as the user wrote it (kept verbatim for reuse)
# group(2) = the digits as written (leading zeros preserved, so we can
#            infer whether the user zero-pads and to what width)
_CD_DIR_RE = re.compile(r"^(cd|disc|disk)[\s_\-]*(\d+)$", re.IGNORECASE)

try:
    from .printer import _print, _log  # type: ignore
except Exception:
    from printer import _print, _log

try:
    from .notifier import growl  # type: ignore
except Exception:
    from notifier import growl


def _parse_disk_number(raw, default=1):
    """DISK_NUMBER from the Deezer website can be missing, empty, or a
    string. Normalize it to an int, falling back to `default` on any
    garbage input instead of raising."""
    try:
        if raw is None:
            return default
        raw = str(raw).strip()
        if raw == "":
            return default
        return int(float(raw))
    except (ValueError, TypeError):
        return default


class AlbumDiskOrganizer:
    """
    Tracks disk numbers for the songs of ONE album download job.

    Behavior:
    - As long as every song seen so far reports the same disk number,
      files are kept flat in `album_dir` and no CDxx folder is created.
    - The moment a song with a *different* disk number shows up, the
      album is treated as multi-disk from then on:
        * every song already downloaded for the first disk is moved
          into its own CDxx folder (e.g. CD01) in a background thread,
          so the download of the next song is never blocked on I/O.
        * the destination for the song that triggered the switch (and
          every song after it) becomes its own CDxx folder immediately,
          created synchronously so there's never a race on "where does
          this file go".
    - If per-disk folders already exist under ANY common naming (CD1,
      CD01, Disc 2, DISK-03, ...) -- e.g. organized by hand before this
      feature existed -- they are detected at startup, reused as-is
      (never renamed/duplicated), and every song routes straight to
      its matching folder from song one. Any disk that doesn't already
      have a folder gets a brand-new one, in the same naming style as
      the existing ones if any were found, otherwise "CD01" style.

    One instance per album download job — do not share across
    concurrent album downloads / worker threads.
    """

    CD_DIR_FORMAT = "CD{:02d}"

    def __init__(self, album_dir: str):
        self.album_dir = album_dir
        self._lock = threading.Lock()
        # disk_number -> existing folder path, for folders that were
        # already there (any naming) before this run started
        self._existing_cd_dirs, self._naming_style = self._detect_existing_cd_dirs()
        # A previous (partial or complete) run, or a manual reorg, may
        # already have organized this album into per-disk subfolders.
        # If so, don't re-detect it song by song -- go straight to
        # per-disk routing for every disk from the very first song.
        self._is_multi_disk = bool(self._existing_cd_dirs)
        self._first_disk_number = None
        # (path, disk_number) for files currently sitting flat in
        # album_dir, while we still believe this is a single-disk album
        self._flat_files = []
        # old_path -> new_path, filled in by background movers and by
        # locate_existing_file()
        self._rename_map = {}
        self._pending_moves = []

    def _detect_existing_cd_dirs(self):
        """Scan album_dir for folders that already represent a disk,
        under any of the naming variants _CD_DIR_RE recognizes.
        Returns (dict[int, str] of disk_number -> existing folder path,
        naming style tuple (prefix_text, digit_width) taken from the
        first match found, or None if nothing was found)."""
        existing = {}
        style = None
        try:
            for name in sorted(os.listdir(self.album_dir)):
                full = os.path.join(self.album_dir, name)
                if not os.path.isdir(full):
                    continue
                m = _CD_DIR_RE.match(name)
                if not m:
                    continue
                prefix, digits = m.group(1), m.group(2)
                try:
                    disk_number = int(digits)
                except ValueError:
                    continue
                existing[disk_number] = full
                if style is None:
                    style = (prefix, len(digits))
        except OSError:
            pass
        return existing, style

    def _cd_dir(self, disk_number: int) -> str:
        # 1. an existing folder for this exact disk number wins, no
        #    matter what it's named -- never create a second one.
        existing = self._existing_cd_dirs.get(disk_number)
        if existing:
            return existing
        # 2. no folder for this disk yet: create one, matching the
        #    naming style already used in this album if there is one,
        #    so a newly-appearing disk (e.g. CD3) fits in alongside
        #    hand-made CD1/CD2 instead of introducing "CD03".
        if self._naming_style is not None:
            prefix, width = self._naming_style
            name = "{}{:0{width}d}".format(prefix, disk_number, width=width)
            return os.path.join(self.album_dir, name)
        return os.path.join(self.album_dir, self.CD_DIR_FORMAT.format(disk_number))

    def get_destination_dir(self, raw_disk_number) -> str:
        """Call this BEFORE building a song's output path, once per
        song, in download order. Returns the directory that song should
        be written to."""
        disk_number = _parse_disk_number(raw_disk_number, default=1)

        with self._lock:
            if self._first_disk_number is None:
                self._first_disk_number = disk_number

            if not self._is_multi_disk:
                if disk_number == self._first_disk_number:
                    # still looks single-disk: keep it flat in album_dir
                    return self.album_dir
                # different disk number just appeared -> this is a
                # multi-disk album. Kick off the background move of
                # everything already downloaded for the first disk.
                self._is_multi_disk = True
                self._start_background_move_locked(self._first_disk_number)

            cd_dir = self._cd_dir(disk_number)

        os.makedirs(cd_dir, exist_ok=True)
        return cd_dir

    def locate_existing_file(self, song_filename: str, target_dir: str):
        """Check whether this song was already downloaded in an earlier
        run, so the caller can skip re-downloading it. Looks in two
        places:
        1. `target_dir` (its current, correct home).
        2. The legacy flat `album_dir` location -- covers a run that
           was interrupted mid-reorganization, leaving some disk-1
           files not yet moved into CD01 while later songs already
           went straight to their CDxx folder.

        A file found in the legacy location is moved into `target_dir`
        right away (a single known file -- cheap, unlike the bulk
        background move used for a live reorg) so it stops being an
        orphan outside its CD folder. Returns the file's path, or None
        if it hasn't been downloaded before.
        """
        candidate = os.path.join(target_dir, song_filename)
        if os.path.exists(candidate):
            return candidate

        if target_dir == self.album_dir:
            return None

        legacy = os.path.join(self.album_dir, song_filename)
        if not os.path.exists(legacy):
            return None

        try:
            shutil.move(legacy, candidate)
            with self._lock:
                self._rename_map[legacy] = candidate
            _log("Found '{}' left over from a previous run, moved into '{}'".format(legacy, candidate), s='n')
            return candidate
        except OSError as e:
            _log("Could not move leftover file '{}' into '{}': {}".format(legacy, candidate, e), s='e')
            return legacy  # it still exists there, just not moved yet

    def record_flat_file(self, path: str, raw_disk_number) -> None:
        """Call once a song has actually been written to `album_dir`
        flat (i.e. get_destination_dir returned album_dir for it), so
        it can be picked up by a later reorganization if one happens."""
        disk_number = _parse_disk_number(raw_disk_number, default=1)
        with self._lock:
            if not self._is_multi_disk:
                self._flat_files.append((path, disk_number))

    def _start_background_move_locked(self, disk_number: int) -> None:
        # must be called with self._lock held
        cd_dir = self._cd_dir(disk_number)
        files_to_move = list(self._flat_files)
        self._flat_files.clear()

        def _mover():
            try:
                os.makedirs(cd_dir, exist_ok=True)
                for old_path, _dn in files_to_move:
                    if not os.path.exists(old_path):
                        continue
                    new_path = os.path.join(cd_dir, os.path.basename(old_path))
                    try:
                        shutil.move(old_path, new_path)
                        with self._lock:
                            self._rename_map[old_path] = new_path
                        _log("Multi-disk album detected: moved '{}' -> '{}'".format(old_path, new_path), s='n')
                    except OSError as e:
                        _log("Could not move '{}' into '{}': {}".format(old_path, cd_dir, e), s='e')
                growl.publish(
                    "info", "DeezDown - INFO",
                    "Multi-disk album: reorganized {} song(s) into '{}'".format(
                        len(files_to_move), os.path.basename(cd_dir)),
                    icon="deezer-downloader.png",
                )
            except Exception as e:
                _log("Error while reorganizing album into CD folders: {}".format(e), s='e')

        t = threading.Thread(
            target=_mover,
            daemon=True,
            name="disk-reorganize-{}".format(os.path.basename(cd_dir)),
        )
        self._pending_moves.append(t)
        t.start()

    def resolve_final_paths(self, paths):
        """Wait for any background reorganization triggered during this
        album's download to finish, then translate `paths` (as built
        during the download loop) to their final on-disk location.

        Call this exactly once, after the whole album has finished
        downloading, and BEFORE zipping / mpd-updating / returning the
        paths to the caller.
        """
        with self._lock:
            pending = list(self._pending_moves)
        for t in pending:
            t.join()
        with self._lock:
            rename_map = dict(self._rename_map)
        return [rename_map.get(p, p) for p in paths]
