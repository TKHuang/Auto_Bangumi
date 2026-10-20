Status: ready-for-agent

# Spec (from user's bug report, no tracked issue)

1. User subscribed the same anime from two subtitle groups (Ani and LoliHouse) = two Bangumi of one Series sharing one Season folder.
2. LoliHouse had zero torrents that passed its filter. PikPak held only Ani's 3 episodes.
3. User deleted LoliHouse with "also delete files". Ani's 3 episodes on PikPak were deleted. BUG.
4. Requirement: delete with files must delete only the deleted bangumi's own files; never another bangumi's files.
5. User follow-up: "watch for regression; I forgot why save_path was used originally; make sure nothing wrong is deleted; there is an auto-rename mechanism, so a mechanism is needed that knows exactly which anime's files to delete."

## Comments

- Fix (uncommitted on top of bfdf6214): torrents for delete/disable/move are matched by DB ownership (`bangumi_id`), not by save_path. Hashes owned by another bangumi are skipped. PikPak whole-folder trash and the move whole-folder fallback run only when `TorrentRepository.path_shared_with_others` says no other torrent can have files there (subfolder, NULL path, NULL hash all count as "other"). `update_rule` no longer rewrites cloud paths of rows that `move_torrent` did not move.
- Why save_path was used: 2023 qBittorrent-RSS-rule era, no hash in DB (commits 956f6af6, b6015951). Obsolete since hash tracking (e5683861).
- Won't fix: torrents with no DB row or a NULL hash are not deleted. PikPak `torrents_info` already ignored untracked tasks, and the old DB fallback skipped NULL hashes, so this is not a regression on PikPak. On qBittorrent, matching untracked torrents needs the save_path match that caused this bug.
