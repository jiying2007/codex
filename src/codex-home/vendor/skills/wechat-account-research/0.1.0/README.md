# wechat-account-research

Local Codex packaging metadata for the bounded WeChat account research skill.

- Source: the public-search and page-verification mechanism was adapted from the local Hermes `wechat-article-reader`; unsafe proxy rotation, CAPTCHA retry, full-body archive and automatic deletion behavior were deliberately excluded.
- Runtime: `~/codex/tools/codex_assets/wechat_archive.py` through `~/codex/scripts/wechat-archive.sh`.
- Persistence: metadata, access states, counts and SHA-256 only; article bodies and temporary signed URLs are never retained.
- Verification: `rtk python3 -m unittest tests.test_wechat_archive` and `rtk bash scripts/doctor.sh --scope governance`.
