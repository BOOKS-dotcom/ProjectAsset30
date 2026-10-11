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
        self.assertEqual(result, '# テーマ\n\n導入\n## テーマ\n説明\n## 結論\n終わり')
        self.assertTrue(warnings)

    def test_different_generated_title_is_preserved_and_warned(self):
        result, warnings = normalize_headings('テーマ', '# 独自タイトル\n## 導入\n本文')
        self.assertEqual(result, '# テーマ\n\n# 独自タイトル\n## 導入\n本文')
        self.assertTrue(warnings)

    def test_ambiguous_skipped_levels_are_preserved(self):
        result, _ = normalize_headings('テーマ', '### 大見出し\n##### 小見出し\n### 次の大見出し')
        self.assertEqual(result, '# テーマ\n\n### 大見出し\n##### 小見出し\n### 次の大見出し')

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


class ConservativeHeadingTests(unittest.TestCase):
    def assert_body_preserved(self, body):
        result, warnings = normalize_headings('テーマ', body)
        self.assertEqual(result, '# テーマ\n\n' + body)
        return warnings

    def test_consecutive_siblings_remain_unchanged(self):
        self.assertFalse(self.assert_body_preserved('## A\n本文A\n## B\n本文B\n## C'))

    def test_return_to_upper_heading_remains_unchanged(self):
        self.assert_body_preserved('## A\n### A1\n#### A1a\n### A2\n## B')

    def test_internal_jump_is_preserved_and_warned(self):
        warnings = self.assert_body_preserved('## A\n#### B\n## C')
        self.assertTrue(any('飛び' in warning for warning in warnings))

    def test_body_heading_matching_title_keeps_its_children(self):
        warnings = self.assert_body_preserved('## A\n### テーマ\n本文\n#### 子見出し\n## B')
        self.assertTrue(any('同名' in warning for warning in warnings))

    def test_later_h1_matching_title_is_not_deleted(self):
        warnings = self.assert_body_preserved('導入文\n# テーマ\n## A\n本文')
        self.assertTrue(warnings)

    def test_multiple_different_h1_titles_and_children_are_preserved(self):
        warnings = self.assert_body_preserved('# 別タイトル\n## A\n# 次のタイトル\n## B')
        self.assertEqual(len(warnings), 2)

    def test_exact_valid_markup_preserves_spacing_and_crlf(self):
        self.assert_body_preserved('  ##  A ###\r\n本文\r\n ###\tB\r\n## C\r\n')

    def test_uniform_missing_parent_shift_keeps_siblings_and_returns(self):
        body = '### A\n#### A1\n### B\n#### B1\n### C'
        result, _ = normalize_headings('テーマ', body)
        self.assertEqual(result, '# テーマ\n\n## A\n### A1\n## B\n### B1\n## C')
        self.assertEqual(normalize_headings('テーマ', result)[0], result)

    def test_setext_prevents_reinterpretation_of_surrounding_atx(self):
        warnings = self.assert_body_preserved('上位タイトル\n====\n### A\n#### B')
        self.assertTrue(any('下線形式' in warning for warning in warnings))

    def test_setext_in_code_and_quote_does_not_change_them(self):
        body = '```\nタイトル\n====\n# テーマ\n```\n> タイトル\n> ====\n## A\n### B'
        self.assertFalse(self.assert_body_preserved(body))

    def test_leading_duplicate_title_keeps_normal_hierarchy_and_prose(self):
        body = '# テーマ\n\n## A\n### テーマ\n説明\n#### 子\n## B'
        result, warnings = normalize_headings('テーマ', body)
        self.assertEqual(result, body)
        self.assertTrue(warnings)

    def test_unclosed_fence_prevents_global_shift(self):
        warnings = self.assert_body_preserved('### A\n```\n## code')
        self.assertTrue(any('閉じられていない' in warning for warning in warnings))
