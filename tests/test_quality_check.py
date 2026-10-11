import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import quality_check as quality
from utils import file_utils


def article(folder='blog'):
    sentence = '読者に役立つ具体例を示し、内容を理解しやすく説明します。'
    return '# 記事タイトル\n\n' + '\n\n'.join(
        f'## セクション{i}\n\n' + ''.join(f'{i}-{j}：{sentence}' for j in range(12))
        for i in range(1, 4))


class RuleTests(unittest.TestCase):
    def check(self, text, folder='blog'):
        return quality.check_article(text, folder, 'テーマ')

    def item(self, report, name):
        return next(item for item in report.checks if item.name == name)

    def test_good_article_passes_for_each_type(self):
        for folder in quality.PROFILES:
            with self.subTest(folder=folder):
                self.assertTrue(self.check(article(folder), folder).passed)

    def test_empty_and_heading_only_documents_need_review(self):
        for content in ('', '  \n', '# タイトル\n## 本文\n### まとめ'):
            with self.subTest(content=content):
                report = self.check(content)
                self.assertFalse(report.passed)
                self.assertFalse(self.item(report, '本文').passed)
                self.assertEqual(report.character_count, 0)

    def test_character_count_excludes_headings_whitespace_and_markdown(self):
        report = self.check('# タイトル\n\n## 本文\n\n **あ い**\n[う](https://example.com)\n')
        self.assertEqual(report.character_count, 3)

    def test_length_thresholds(self):
        _, minimum, maximum, _ = quality.PROFILES['research']
        for count, expected in ((minimum-1,False),(minimum,True),(maximum,True),(maximum+1,False)):
            with self.subTest(count=count):
                report = self.check('# 題\n\n' + 'あ'*count, 'research')
                self.assertEqual(self.item(report,'文字数').passed, expected)

    def test_missing_multiple_or_skipped_headings(self):
        for content in ('本文だけ', '# 題\n# 別題\n本文', '# 題\n### 飛んだ階層\n本文'):
            with self.subTest(content=content):
                self.assertFalse(self.item(self.check(content),'見出し構成').passed)

    def test_setext_headings_are_recognized(self):
        content = 'タイトル\n===\n\n概要\n---\n説明\n\n結論\n---\n説明'
        report = self.check(content,'research')
        self.assertTrue(self.item(report,'見出し構成').passed)

    def test_long_sentence_duplicates_are_flagged_but_short_words_are_not(self):
        sentence = 'これは公開前に確認が必要な長い説明文を繰り返しています。'
        report = self.check('# 題\n' + sentence + '\n' + sentence)
        self.assertFalse(self.item(report,'重複文章').passed)
        self.assertTrue(self.item(self.check('# 題\nはい。はい。'),'重複文章').passed)

    def test_placeholders_in_body_and_heading_are_detected(self):
        for placeholder in ('TODO', 'todo', 'TBD', 'FIXME', 'ここに入力', 'ここに記入'):
            with self.subTest(placeholder=placeholder):
                report = self.check(f'# 題\n## {placeholder}\n本文')
                self.assertFalse(self.item(report,'未完成表現').passed)
        self.assertTrue(self.item(self.check('# 題\nTODOLISTは製品名です。'),'未完成表現').passed)

    def test_japanese_adjacent_todo_changes_overall_verdict(self):
        report = self.check(article() + '\n\nTODOを修正する')
        self.assertFalse(self.item(report,'未完成表現').passed)
        self.assertFalse(report.passed)

    def test_placeholders_next_to_japanese_and_punctuation(self):
        for token in ('TODO','todo','ToDo','TBD','tbd','FIXME','fixme','FixMe'):
            for text in (f'{token}を修正する',f'ここは{token}',f'ここは{token}です',
                         f'（{token}）',f'{token}。',token):
                with self.subTest(text=text):
                    self.assertFalse(self.item(self.check('# 題\n'+text),'未完成表現').passed)

    def test_placeholder_substrings_in_english_identifiers_are_not_flagged(self):
        for text in ('TODOLIST','ToDoList','myTODO','TODO123','123TODO','_TODO',
                     'TODO_item','TBDays','notTBD','FIXMEs','prefixFIXME',
                     'こちらのTODOLISTです'):
            with self.subTest(text=text):
                self.assertTrue(self.item(self.check('# 題\n'+text),'未完成表現').passed)

    def test_inline_todo_example_does_not_fail_overall_verdict(self):
        report = self.check(article() + '\n\n`TODO` はコード例です。')
        self.assertTrue(self.item(report,'未完成表現').passed)
        self.assertTrue(report.passed)

    def test_inline_code_excludes_all_placeholder_forms_and_multiple_spans(self):
        for text in ('`TODO`、`TBD`、`FIXME`のコード例',
                     '`ここに入力` は表示のコード例',
                     '``TODOを修正する `TBD` FIXME`` のコード例',
                     '```TODO``` はインラインのコード例'):
            with self.subTest(text=text):
                self.assertTrue(self.item(self.check('# 題\n説明：'+text),'未完成表現').passed)

    def test_inline_and_regular_placeholders_on_same_line_are_independent(self):
        for text in ('`TODO` の例。TODOを修正する',
                     '本文はtbdです。`FIXME`は例です',
                     '``TODO`` の例。ここに入力',
                     '`TBD` `FIXME` の例。ここはFixMeです'):
            with self.subTest(text=text):
                self.assertFalse(self.item(self.check('# 題\n'+text),'未完成表現').passed)

    def test_heading_inline_code_is_excluded_but_regular_placeholder_is_detected(self):
        good = self.check('# `TODO`のコード例\n本文')
        bad = self.check('# `TODO`の例とTBDを修正する\n本文')
        self.assertTrue(self.item(good,'未完成表現').passed)
        self.assertFalse(self.item(bad,'未完成表現').passed)

    def test_escaped_or_unclosed_backticks_do_not_hide_regular_todo(self):
        for text in ('`TODOを修正する',r'\`TODO\`を修正する',
                     '``TODO`を修正する'):
            with self.subTest(text=text):
                self.assertFalse(self.item(self.check('# 題\n'+text),'未完成表現').passed)

    def test_inline_code_can_span_soft_line_breaks_but_not_blank_paragraphs(self):
        good = self.check('# 題\nコード例 `\nTODO\n` を説明します。')
        bad = self.check('# 題\n未完了の `\n\nTODOを修正する\n\n`')
        self.assertTrue(self.item(good,'未完成表現').passed)
        self.assertFalse(self.item(bad,'未完成表現').passed)

    def test_other_quality_results_are_unchanged_for_inline_placeholders(self):
        report = self.check(article() + '\n\n`TODO` の例。')
        for item in report.checks:
            if item.name != '未完成表現':
                self.assertTrue(item.passed,item.name)

    def test_fenced_code_is_not_prose_or_a_placeholder(self):
        report = self.check('# 題\n```python\n# TODO\nここに入力\n```\n説明')
        self.assertTrue(self.item(report,'未完成表現').passed)
        self.assertTrue(self.item(report,'Markdown形式').passed)
        self.assertEqual(report.character_count, 2)

    def test_whole_fenced_document_has_no_prose(self):
        report = self.check('```markdown\n# 題\n本文です\n```')
        self.assertFalse(self.item(report,'本文').passed)
        self.assertFalse(self.item(report,'見出し構成').passed)

    def test_markdown_problems(self):
        for content in ('#見出し\n本文', '# \n本文', '# 題\n```\nコード',
                        '# 題\n**太字', '# 題\n[リンク]()', '####### 見出し'):
            with self.subTest(content=content):
                self.assertFalse(self.item(self.check(content),'Markdown形式').passed)

    def test_fences_match_character_and_minimum_length(self):
        good = '# 題\n~~~~python\n```\nTODO\n~~~~~\n本文'
        self.assertTrue(self.item(self.check(good),'Markdown形式').passed)
        bad = '# 題\n````\n```\n本文'
        self.assertFalse(self.item(self.check(bad),'Markdown形式').passed)

    def test_report_contains_verdict_each_item_advice_and_limitations(self):
        report = self.check('# 題\nTODO')
        rendered = quality.render_report(report)
        for text in ('要確認','問題点','改善案','API料金：0円','事実関係・正確性'):
            self.assertIn(text, rendered)
        for item in report.checks:
            self.assertIn(item.name, rendered)
        passed = quality.render_report(self.check(article()))
        self.assertIn('合格',passed)
        self.assertIn('内容の正確性は未検証',passed)

    def test_invalid_type_and_unsafe_theme(self):
        for folder, theme in (('../escape','theme'),('blog','../escape'),('blog','CON')):
            with self.assertRaises(ValueError):
                quality.check_article('article',folder,theme)

    def test_theme_markdown_does_not_inject_report_structure(self):
        report = quality.Report('blog','<script>`|題',0,())
        rendered = quality.render_report(report)
        self.assertNotIn('<script>',rendered)
        self.assertIn('\\|',rendered)

    def test_quality_module_imports_without_openai(self):
        source = str(Path(__file__).resolve().parents[1] / 'src')
        code = f'import sys; sys.path.insert(0,{source!r}); sys.modules["openai"]=None; import quality_check'
        result = subprocess.run([sys.executable,'-B','-c',code],capture_output=True)
        self.assertEqual(result.returncode,0)


class SavedArticleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        location = patch.object(file_utils,'__file__',str(self.root/'src/utils/file_utils.py'))
        location.start()
        self.addCleanup(location.stop)
        redirect = contextlib.redirect_stdout(io.StringIO())
        redirect.__enter__()
        self.addCleanup(redirect.__exit__,None,None,None)

    def source(self,folder='blog',content=None):
        source = self.root/'data'/folder/'テーマ.md'
        source.parent.mkdir(parents=True,exist_ok=True)
        source.write_bytes((content if content is not None else article()).replace('\n','\r\n').encode('utf-8'))
        return source

    def test_reports_do_not_modify_articles_or_history_and_are_unique(self):
        for folder in quality.PROFILES:
            source = self.source(folder)
            history = source.parent/'history/テーマ/old.md'
            history.parent.mkdir(parents=True)
            history.write_text('旧記事',encoding='utf-8')
            before = {p:p.read_bytes() for p in self.root.rglob('*.md')}
            report, first = quality.check_saved_article(folder,'テーマ')
            _, second = quality.check_saved_article(folder,'テーマ')
            self.assertNotEqual(first,second)
            self.assertEqual(report.source_sha256,hashlib.sha256(source.read_bytes()).hexdigest())
            for p,data in before.items():
                self.assertEqual(p.read_bytes(),data)
            self.assertIn('点検時の記事SHA-256',first.read_text(encoding='utf-8'))
            self.assertEqual(file_utils.list_markdown(folder),['テーマ'])

    def test_missing_source_or_invalid_encoding_creates_no_report(self):
        with self.assertRaises(FileNotFoundError):
            quality.check_saved_article('blog','テーマ')
        self.source(content='text').write_bytes(b'\xff\xff')
        with self.assertRaises(UnicodeDecodeError):
            quality.check_saved_article('blog','テーマ')
        self.assertFalse((self.root/'data/quality').exists())

    def test_report_write_failure_does_not_modify_source(self):
        source = self.source()
        original = source.read_bytes()
        original_open = Path.open
        def refuse_report(path, mode='r', *args, **kwargs):
            if mode == 'x':
                raise PermissionError
            return original_open(path,mode,*args,**kwargs)
        with patch.object(quality.Path,'open',refuse_report),self.assertRaises(PermissionError):
            quality.check_saved_article('blog','テーマ')
        self.assertEqual(source.read_bytes(),original)

    def test_partial_report_write_is_cleaned_without_touching_source(self):
        source = self.source()
        original = source.read_bytes()
        original_open = Path.open
        class BrokenWriter:
            def __init__(self, handle):
                self.handle = handle
            def __enter__(self):
                return self
            def write(self, text):
                self.handle.write('partial')
                raise OSError('write failed')
            def __exit__(self, *args):
                self.handle.close()
        def broken_open(path, mode='r', *args, **kwargs):
            handle = original_open(path,mode,*args,**kwargs)
            return BrokenWriter(handle) if mode == 'x' else handle
        with patch.object(quality.Path,'open',broken_open),self.assertRaises(OSError):
            quality.check_saved_article('blog','テーマ')
        self.assertEqual(source.read_bytes(),original)
        self.assertEqual(list((self.root/'data/quality').rglob('*.md')),[])

    def test_report_collision_never_overwrites_existing_report(self):
        source = self.source()
        original = source.read_bytes()
        with patch.object(quality,'datetime') as clock, \
             patch.object(quality,'uuid4',return_value=SimpleNamespace(hex='fixed')):
            clock.now.return_value.strftime.return_value = 'fixed'
            _,path = quality.check_saved_article('blog','テーマ')
            saved = path.read_bytes()
            with self.assertRaises(FileExistsError):
                quality.check_saved_article('blog','テーマ')
        self.assertEqual(path.read_bytes(),saved)
        self.assertEqual(source.read_bytes(),original)

    def test_list_read_failure_returns_to_menu_without_creating_report(self):
        with patch.object(file_utils,'list_markdown',side_effect=PermissionError), \
             patch('builtins.input',return_value='1'):
            quality.run()
        self.assertFalse((self.root/'data/quality').exists())

    def test_menu_selects_every_type_and_can_cancel(self):
        for number,folder in (('1','research'),('2','blog'),('3','note')):
            self.source(folder)
            with patch('builtins.input',side_effect=[number,'1']):
                quality.run()
            self.assertEqual(len(list((self.root/'data/quality'/folder/'テーマ').glob('*.md'))),1)
        for choices in (['0'],['bad'],['1','0'],['1','-1'],['1','99'],['1','bad']):
            with patch('builtins.input',side_effect=choices):
                quality.run()
        self.assertEqual(len(list((self.root/'data/quality').rglob('*.md'))),3)

    def test_empty_article_list_returns_without_generation(self):
        with patch('builtins.input',return_value='1') as prompt:
            quality.run()
        prompt.assert_called_once()
        self.assertFalse((self.root/'data/quality').exists())

    def test_manager_quality_menu_does_not_call_any_ai(self):
        import manager
        self.source('research')
        with patch('builtins.input',side_effect=['7','1','1','0']), \
             patch.object(manager,'research_run') as research, \
             patch.object(manager,'blog_run') as blog, \
             patch.object(manager,'note_run') as note, \
             patch.object(manager,'pipeline_run') as pipeline:
            manager.main()
        for runner in (research,blog,note,pipeline):
            runner.assert_not_called()
        self.assertEqual(len(list((self.root/'data/quality').rglob('*.md'))),1)


if __name__ == '__main__':
    unittest.main()
