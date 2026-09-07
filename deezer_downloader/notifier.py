#!/usr/bin/env python3

# File: deezer_downloader/web/notifier.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-06-17
# Description: 
# License: MIT


try:
    from gntplib import Publisher  # type: ignore
    growl = Publisher( 
            "Deezer-Downloader",  # type: ignore
            ["info", "error", "warning", "debug", "finish", "mpd_update"],
            icon="deezer-downloader.png"
        )

    try:
        growl.register()  # type: ignore
    except:
        pass

    HAS_GNTPLIB = True
except Exception as e:
    print(f"[GNTPLIB:ERROR] {e}")
    HAS_GNTPLIB = False

    class Publisher:
        def publish(self, *args, **kwargs):
            return 

    growl = Publisher()