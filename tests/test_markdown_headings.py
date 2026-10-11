import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from utils.markdown_utils import normalize_headings
from utils import file_utils
from quality_check import check_article


class HeadingTests(unittest.TestCase):
    def test_duplicate_title_keeps_body(self):
        result, warnings = normalize_headings('テーマ', '# テーマ\n導入\n## テーマ\n説明\n## 結論\n終わり')
        self.assertEqual(result, '# テーマ\n\n導入\n説明\n## 結論\n終わり')
        self.assertFalse(warnings)

    def test_different_generated_title_is_kept_as_section_and_warned(self):
        result, warnings = normalize_headings('テーマ', '# 独自タイトル\n## 導入\n本文')
        self.assertEqual(result, '# テーマ\n\n## 独自タイトル\n### 導入\n本文')
        self.assertTrue(warnings)

    def test_skipped_levels_preserve_relative_hierarchy(self):
        result, _ = normalize_headings('テーマ', '### 大見出し\n##### 小見出し\n### 次の大見出し')
        self.assertEqual(result, '# テーマ\n\n## 大見出し\n### 小見出し\n## 次の大見出し')

    def test_valid_body_is_unchanged_and_normalization_is_idempotent(self):
        body = '## 導入\n本文 # 通常文字\n### 詳細\n## 結論'
        first, _ = normalize_headings('テーマ', body)
        second, _ = normalize_headings('テーマ', first)
        self.assertEqual(first, '# テーマ\n\n' + body)
        self.assertEqual(second, first)

    def test_deep_meaningful_hierarchy_is_preserved_and_warned(self):
        body = '## 章\n### 節\n#### 項\n##### 細目'
        result, warnings = normalize_headings('テーマ', body)
        self.assertEqual(result, '# テーマ\n\n' + body)
        self.assertEqual(len(warnings), 2)

    def test_fenced_code_and_quotes_are_unchanged(self):
        body = '````md\n# テーマ\n```\n### code\n````\n~~~\n# title\n~~~\n> # テーマ\n> ## 引用\n    # code\n\t## code'
        result, warnings = normalize_headings('テーマ', body)
        self.assertEqual(result, '# テーマ\n\n' + body)
        self.assertFalse(warnings)

    def test_unclosed_fence_is_preserved_and_warned(self):
        body = '```md\n# テーマ\n## code'
        result, warnings = normalize_headings('テーマ', body)
        self.assertEqual(result, '# テーマ\n\n' + body)
        self.assertIn('閉じられていない', warnings[0])

    def test_normal_hash_and_escaped_heading_unchanged(self):
        body = '本文の # 記号\n\\# 見出しではない\n`# テーマ`\nhttps://example.test/#anchor'
        self.assertEqual(normalize_headings('テーマ', body)[0], '# テーマ\n\n' + body)

    def test_uncertain_syntax_not_repaired(self):
        body = '#空白なし\n# \n####### 不正\n下線見出し\n===='
        result, warnings = normalize_headings('テーマ', body)
        self.assertEqual(result, '# テーマ\n\n' + body)
        self.assertTrue(warnings)

    def test_closing_hash_and_line_endings(self):
        result, _ = normalize_headings('テーマ', '# テーマ ###\r\n### 見出し ##\r\n本文\r\n')
        self.assertEqual(result, '# テーマ\n\n## 見出し ##\r\n本文\r\n')

    def test_quality_checks_not_forced_to_pass(self):
        text, _ = normalize_headings('テーマ', '# テーマ\n### 章\nTODOを修正する')
        report = check_article(text, 'blog', 'テーマ')
        checks = {c.name:c for c in report.checks}
        self.assertFalse(report.passed)
        self.assertFalse(checks['文字数'].passed)
        self.assertFalse(checks['未完成表現'].passed)

    def test_quality_heading_check_passes_after_safe_repair(self):
        text, _ = normalize_headings('テーマ', '# テーマ\n### 導入\n本文\n### 本文\n説明\n### まとめ\n結論')
        report = check_article(text, 'blog', 'テーマ')
        self.assertTrue(next(c for c in report.checks if c.name == '見出し構成').passed)

    def test_all_article_types_save_normalized_and_preserve_old_bytes(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), patch.object(file_utils, '__file__', str(Path(directory)/'src/utils/file_utils.py')):
            for folder in ('research','blog','note'):
                original = Path(directory)/'data'/folder/'テーマ.md'
                original.parent.mkdir(parents=True)
                old = '# 昔\r\n既存記事'.encode('utf-8')
                original.write_bytes(old)
                file_utils.save_markdown(folder, 'テーマ', '# テーマ\n### 章\n本文')
                self.assertEqual(file_utils.load_markdown(folder,'テーマ'), '# テーマ\n\n## 章\n本文')
                history = list((original.parent/'history/テーマ').glob('*.md'))
                self.assertEqual(history[0].read_bytes(), old)

    def test_warning_is_visible_after_save(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(output), patch.object(file_utils, '__file__', str(Path(directory)/'src/utils/file_utils.py')):
            file_utils.save_markdown('blog', 'テーマ', '# 別タイトル\n本文')
        self.assertIn('見出し要確認', output.getvalue())
