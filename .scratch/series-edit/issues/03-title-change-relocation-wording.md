# Title-change dialog promises a relocation the rename job does not do

Status: needs-triage

The `Confirm title change` dialog says "ALL downloaded files will be relocated on the next rename cycle". From source, the scheduled rename job (`rename_all`) never moves files; only `rename_bangumi` calls `move_torrent`, and it runs from `retrigger-rename` or a rule save with a changed season or title. New downloads go to the new root at once. So after a title change, files can end up split across the old and new folders.

Not yet driven live: confirming a title change on a series with files. Reproduce on the dev stack before fixing, then either move files when the title changes or correct the dialog text.
