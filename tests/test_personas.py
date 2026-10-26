import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from persona_catalog import catalog,resolve_style
from seat_styles import styles_for
from chat_service import chat_tone
class PublicPersonas(unittest.TestCase):
    def test_sample_presets_resolve_and_keep_memory_boundary(self):
        for row in catalog()['presets']:
            style=styles_for({'seat_styles':{'A':{'preset':row['id']}}})['A']
            self.assertIn(row['name'],chat_tone(style))
            self.assertIn('不会删除存储',chat_tone(style))
    def test_saved_snapshot_remains_authoritative(self):
        self.assertEqual(chat_tone({'preset':'lele','resolved_text':'saved','text':''}),'saved')
        with self.assertRaises(ValueError):resolve_style('unknown')
