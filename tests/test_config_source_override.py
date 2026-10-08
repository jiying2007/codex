import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.codex_assets.core import render_config


class ConfigSourceOverrideTests(unittest.TestCase):
    def test_explicit_source_is_used_for_config_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            canonical, override, output = root / 'canonical', root / 'override', root / 'build'
            for source, value in ((canonical, 'canonical'), (override, 'local-model')):
                (source / 'config').mkdir(parents=True)
                (source / 'config/base.toml').write_text('model = "' + value + '"\n')
            repo = SimpleNamespace(source=canonical, assets={'config': {'base': 'config/base.toml'}})
            with patch('tools.codex_assets.core.render_mcp_config', return_value=''):
                render_config(repo, output, 'team-collab', override)
                self.assertEqual((output / 'config.toml').read_text(), 'model = "local-model"\n')
                render_config(repo, output, 'team-collab')
                self.assertEqual((output / 'config.toml').read_text(), 'model = "canonical"\n')
