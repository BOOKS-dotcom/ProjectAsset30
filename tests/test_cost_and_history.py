import contextlib
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
# No SDK or API credentials required by the offline test suite.
if 'openai' not in sys.modules:
    sys.modules['openai'] = types.SimpleNamespace(OpenAI=Mock())
import config
import pipeline
import main as standalone
from agents import research_ai
from utils import ai_utils, file_utils


class CostTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        redirect = contextlib.redirect_stdout(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        self.factory = Mock(return_value=self.client)
        self.response = types.SimpleNamespace(status='completed', output_text='article',
            usage=types.SimpleNamespace(input_tokens=100, output_tokens=200))
        self.client.responses.create.return_value = self.response

    def test_price_math_and_pipeline_quote(self):
        self.assertAlmostEqual(ai_utils.estimate_usd(12000 * 3, 3), 0.45)
        with patch('builtins.input', return_value='n'):
            self.assertFalse(ai_utils.confirm_cost(36000, 3))
        self.assertIn('67.5円', self.output.getvalue())
        self.assertIn('上限保証ではありません', self.output.getvalue())

    def test_declining_manual_quote_does_not_construct_client(self):
        for answer in ('n', '', 'yes', 'invalid'):
            with patch('builtins.input', return_value=answer):
                self.assertIsNone(ai_utils.generate_text(self.factory, 'prompt'))
        self.factory.assert_not_called()

    def test_limit_retry_and_usage_settings(self):
        with patch('builtins.input', return_value='Y'):
            self.assertEqual(ai_utils.generate_text(self.factory, '日本語'), 'article')
        self.factory.assert_called_once_with(max_retries=0, timeout=120.0)
        kwargs = self.client.responses.create.call_args.kwargs
        self.assertEqual(kwargs['max_output_tokens'], 3000)
        self.assertEqual(kwargs['reasoning'], {'effort':'low'})
        self.assertEqual(kwargs['service_tier'], 'default')
        self.assertIn('$0.0065', self.output.getvalue())

    def test_large_input_is_rejected_before_approval_and_client(self):
        with patch('builtins.input') as prompt, self.assertRaises(ai_utils.GenerationError):
            ai_utils.generate_text(self.factory, 'あ' * 4001)
        prompt.assert_not_called()
        self.factory.assert_not_called()

    def test_invalid_settings_are_rejected(self):
        for name, value in (('MODEL','unknown'), ('MAX_OUTPUT_TOKENS',0),
                            ('MAX_OUTPUT_TOKENS',128001), ('MAX_INPUT_BYTES',-1),
                            ('USD_TO_JPY',float('nan')), ('REASONING_EFFORT','bad')):
            with self.subTest(name=name, value=value), patch.object(config, name, value), \
                 self.assertRaises(ai_utils.GenerationError):
                ai_utils.generate_text(self.factory, 'prompt')
        self.factory.assert_not_called()

    def test_incomplete_and_empty_results_are_not_saved(self):
        for status, text in (('incomplete','partial'), ('completed','   ')):
            self.response.status, self.response.output_text = status, text
            with patch.object(research_ai, 'OpenAI', self.factory), \
                 patch.object(research_ai, 'save_markdown') as save, \
                 patch('builtins.input', return_value='y'), \
                 self.assertRaises(ai_utils.GenerationError):
                research_ai.run('theme')
            save.assert_not_called()
        self.assertIn('$0.0065', self.output.getvalue())

    def test_missing_usage_does_not_claim_known_cost(self):
        self.response.usage = None
        with patch('builtins.input', return_value='y'):
            ai_utils.generate_text(self.factory, 'prompt')
        self.assertIn('使用量が取得できない', self.output.getvalue())

    def test_failed_request_is_not_retried_or_leaked(self):
        self.client.responses.create.side_effect = RuntimeError('SECRET_SENTINEL')
        with patch('builtins.input', return_value='y'), self.assertRaises(RuntimeError):
            ai_utils.generate_text(self.factory, 'prompt')
        self.client.responses.create.assert_called_once()
        self.assertIn('使用量が取得できない', self.output.getvalue())
        self.assertNotIn('SECRET_SENTINEL', self.output.getvalue())

    def test_pipeline_decline_never_runs_agents(self):
        with patch('builtins.input', return_value='n'), \
             patch.object(pipeline, 'research_run') as research, \
             patch.object(pipeline, 'blog_run') as blog, \
             patch.object(pipeline, 'note_run') as note:
            pipeline.run('theme')
        for runner in (research, blog, note):
            runner.assert_not_called()

    def test_pipeline_approval_once_and_total_even_after_failure(self):
        def success(theme, *, session):
            session.attempts += 1
            session.record(self.response.usage)
        with patch('builtins.input', return_value='y') as prompt, \
             patch.object(pipeline, 'research_run', side_effect=success), \
             patch.object(pipeline, 'blog_run', side_effect=RuntimeError), \
             patch.object(pipeline, 'note_run') as note, self.assertRaises(RuntimeError):
            pipeline.run('theme')
        prompt.assert_called_once()
        note.assert_not_called()
        self.assertIn('$0.0065', self.output.getvalue())

    def test_standalone_entry_uses_shared_agent_and_hides_api_errors(self):
        with patch.object(standalone, 'run') as runner:
            standalone.main()
        runner.assert_called_once_with()
        with patch.object(standalone, 'run', side_effect=RuntimeError('SECRET_SENTINEL')):
            standalone.main()
        self.assertNotIn('SECRET_SENTINEL', self.output.getvalue())

    def test_pipeline_success_asks_approval_once(self):
        def success(theme, *, session):
            session.attempts += 1
            session.record(self.response.usage)
        with patch('builtins.input', return_value='y') as prompt, \
             patch.object(pipeline, 'research_run', side_effect=success), \
             patch.object(pipeline, 'blog_run', side_effect=success), \
             patch.object(pipeline, 'note_run', side_effect=success):
            pipeline.run('theme')
        prompt.assert_called_once()
        self.assertIn('$0.0195', self.output.getvalue())


class HistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        location = patch.object(file_utils, '__file__', str(self.root / 'src/utils/file_utils.py'))
        location.start()
        self.addCleanup(location.stop)
        redirect = contextlib.redirect_stdout(io.StringIO())
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_repeated_saves_preserve_all_versions_and_latest_selection(self):
        for folder in ('research','blog','note'):
            for content in ('初版', '第二版', '第三版'):
                file_utils.save_markdown(folder, '日本語テーマ', content)
            history = list((self.root / 'data' / folder / 'history/日本語テーマ').glob('*.md'))
            self.assertEqual(len(history), 2)
            self.assertEqual({p.read_text(encoding='utf-8') for p in history},
                {'# 日本語テーマ\n\n初版', '# 日本語テーマ\n\n第二版'})
            self.assertEqual(file_utils.load_markdown(folder,'日本語テーマ'),
                '# 日本語テーマ\n\n第三版')
            self.assertEqual(file_utils.list_markdown(folder), ['日本語テーマ'])

    def test_legacy_file_is_preserved_byte_for_byte(self):
        p = self.root / 'data/research/theme.md'
        p.parent.mkdir(parents=True)
        original = '旧記事\r\n本文'.encode('utf-8')
        p.write_bytes(original)
        file_utils.save_markdown('research','theme','new')
        history = list((p.parent / 'history/theme').glob('*.md'))
        self.assertEqual(history[0].read_bytes(), original)

    def test_same_timestamp_has_distinct_history_names(self):
        with patch.object(file_utils, 'datetime') as clock:
            clock.now.return_value.strftime.return_value = 'fixed'
            for text in ('first','second','third'):
                file_utils.save_markdown('research','theme',text)
        self.assertEqual(len(list((self.root / 'data/research/history/theme').glob('*.md'))),2)

    def test_archive_failure_keeps_latest_and_cleans_temp_file(self):
        file_utils.save_markdown('research','theme','original')
        with patch.object(file_utils.shutil, 'copyfileobj', side_effect=OSError), \
             self.assertRaises(OSError):
            file_utils.save_markdown('research','theme','replacement')
        self.assertIn('original', file_utils.load_markdown('research','theme'))
        self.assertEqual(list((self.root / 'data/research').glob('*.tmp')), [])
        self.assertEqual(list((self.root / 'data/research/history/theme').glob('*.md')), [])

    def test_existing_history_name_is_never_deleted_on_collision(self):
        file_utils.save_markdown('research','theme','original')
        history_dir = self.root / 'data/research/history/theme'
        history_dir.mkdir(parents=True)
        existing = history_dir / 'fixed_id.md'
        existing.write_text('saved history', encoding='utf-8')
        with patch.object(file_utils, 'datetime') as clock, \
             patch.object(file_utils, 'uuid4', return_value=types.SimpleNamespace(hex='id')):
            clock.now.return_value.strftime.return_value = 'fixed'
            with self.assertRaises(FileExistsError):
                file_utils.save_markdown('research','theme','replacement')
        self.assertEqual(existing.read_text(encoding='utf-8'), 'saved history')
        self.assertIn('original', file_utils.load_markdown('research','theme'))

    def test_replace_failure_keeps_latest_and_archive(self):
        file_utils.save_markdown('research','theme','original')
        with patch.object(file_utils.os, 'replace', side_effect=OSError), \
             self.assertRaises(OSError):
            file_utils.save_markdown('research','theme','replacement')
        self.assertIn('original', file_utils.load_markdown('research','theme'))
        history = list((self.root / 'data/research/history/theme').glob('*.md'))
        self.assertIn('original', history[0].read_text(encoding='utf-8'))
        self.assertEqual(list((self.root / 'data/research').glob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
