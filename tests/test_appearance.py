import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import Bridge

class AppearanceTests(unittest.TestCase):
    def test_theme_persists_independently_of_models_and_chat(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp)/'data';bridge=Bridge(Path(temp)/'room',data_dir=data)
            self.assertEqual(bridge.call('api_appearance_get')['data']['theme'],'mint')
            self.assertTrue(bridge.call('api_appearance_save',{'theme':'lavender'})['ok'])
            other=Bridge(Path(temp)/'room',data_dir=data)
            self.assertEqual(other.call('api_appearance_get')['data']['theme'],'lavender')
            self.assertIsNone(other._auto)
            self.assertFalse(other.call('api_appearance_save',{'theme':'unknown'})['ok'])
            self.assertEqual(other.call('api_appearance_get')['data']['theme'],'lavender')
            self.assertFalse((data/'providers.json').exists())
    def test_invalid_appearance_falls_back_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp);path=data/'appearance.json';path.write_text('invalid',encoding='utf-8')
            bridge=Bridge(data/'room',data_dir=data)
            self.assertEqual(bridge.call('api_appearance_get')['data']['theme'],'mint')
            self.assertEqual(path.read_text(encoding='utf-8'),'invalid')
