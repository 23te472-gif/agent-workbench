import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory_store import MemoryStore

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=MemoryStore(Path(self.tmp.name)/'memory.json')
    def test_capacity_warning_hard_limit_and_edit_or_delete(self):
        for i in range(800):self.store.save(dict(scope='A',kind='preference',text=f'偏好 {i}'))
        self.assertTrue(self.store.snapshot()['warning'])
        for i in range(800,1000):self.store.save(dict(scope='B',kind='note',text=f'记录 {i}'))
        with self.assertRaisesRegex(ValueError,'1000'):self.store.save(dict(scope='shared',kind='profile',text='extra'))
        first=self.store.snapshot()['items'][0];self.store.save(dict(first,text='修改已有记录'))
        self.store.delete(first['id']);self.assertEqual(self.store.snapshot()['count'],999)
        self.store.clear();self.assertEqual(self.store.snapshot()['count'],0)
    def test_scope_and_retrieval_have_bounded_content(self):
        self.store.save(dict(scope='A',kind='preference',text='A_ONLY 我倾诉时先听我说'))
        self.store.save(dict(scope='B',kind='preference',text='B_ONLY 不要每次追问'))
        self.store.save(dict(scope='shared',kind='profile',text='SHARED 我喜欢宝可梦'))
        for i in range(25):self.store.save(dict(scope='A',kind='preference',text=str(i)+'字'*490))
        found=self.store.relevant('A','hello');self.assertLessEqual(len(found),20);self.assertLessEqual(sum(len(row['text'])+3 for row in found),6000)
        self.assertNotIn('B_ONLY',json.dumps(found,ensure_ascii=False))
        b=self.store.relevant('B','hello');self.assertTrue(any('SHARED' in r['text'] for r in b));self.assertFalse(any('A_ONLY' in r['text'] for r in b))
    def test_invalid_and_duplicate_memories(self):
        for invalid in [dict(scope='C',kind='profile',text='x'),dict(scope='A',kind='profile',text=''),dict(scope='A',kind='profile',text='x'*501)]:
            with self.assertRaises(ValueError):self.store.save(invalid)
        first=self.store.save(dict(scope='shared',kind='profile',text='昵称小沈'))
        self.assertEqual(self.store.save(dict(scope='shared',kind='profile',text='昵称小沈'))['id'],first['id'])
        self.assertEqual(self.store.snapshot()['count'],1)

    def test_retrieval_count_and_recency_without_modifying_file(self):
        for i in range(25):self.store.save(dict(scope='shared',kind='preference',text=f'偏好 {i}'))
        before=self.store.path.read_bytes();rows=self.store.relevant('A','hello')
        self.assertEqual(len(rows),20);self.assertEqual(rows[0]['text'],'偏好 24')
        self.assertEqual(self.store.path.read_bytes(),before)
        self.assertEqual(MemoryStore(self.store.path).snapshot()['count'],25)

    def test_corrupt_and_oversized_files_preserved(self):
        for raw in ('{"invalid":true}', ' '* (self.store.MAX_BYTES+1)):
            self.store.path.write_text(raw,encoding='utf-8')
            with self.assertRaises(ValueError):self.store.snapshot()
            self.assertEqual(self.store.path.read_text(encoding='utf-8'),raw)

if __name__=='__main__':unittest.main()
