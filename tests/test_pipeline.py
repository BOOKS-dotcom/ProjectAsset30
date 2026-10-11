import contextlib
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
# Offline API boundary: no credentials or network required.
sys.modules['openai'] = types.SimpleNamespace(OpenAI=Mock())
from agents import research_ai, blog_ai, note_ai
from utils import file_utils
import pipeline
import manager


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        fake_file = Path(self.temp.name) / 'src/utils/file_utils.py'
        self.patch = patch.object(file_utils, '__file__', str(fake_file))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)
        self.calls = []
        for module, content in ((research_ai, 'research result'),
                                (blog_ai, 'blog result'), (note_ai, 'note result')):
            client = Mock()
            def generate(content=content, **kwargs):
                self.calls.append(kwargs['input'])
                return types.SimpleNamespace(output_text=content)
            client.responses.create.side_effect = generate
            p = patch.object(module, 'OpenAI', return_value=client)
            p.start()
            self.addCleanup(p.stop)

    def test_pipeline_saves_and_hands_off_current_results(self):
        file_utils.save_markdown('research', '日本語テーマ', 'stale research')
        file_utils.save_markdown('blog', '日本語テーマ', 'stale blog')
        with patch('builtins.input', side_effect=AssertionError('unexpected prompt')):
            pipeline.run(' 日本語テーマ ')
        self.assertEqual(len(self.calls), 3)
        self.assertIn('日本語テーマ', self.calls[0])
        self.assertIn('research result', self.calls[1])
        self.assertNotIn('stale research', self.calls[1])
        self.assertIn('blog result', self.calls[2])
        self.assertNotIn('stale blog', self.calls[2])
        for folder, content in (('research', 'research result'),
                                ('blog', 'blog result'), ('note', 'note result')):
            self.assertEqual(file_utils.load_markdown(folder, '日本語テーマ'),
                             '# 日本語テーマ\n\n' + content)

    def test_manual_agents(self):
        for module, answer in ((research_ai, '手動テーマ'), (blog_ai, '1'), (note_ai, '1')):
            with patch('builtins.input', return_value=answer) as prompt:
                module.run()
            prompt.assert_called_once()
        self.assertEqual(len(self.calls), 3)

    def test_manual_cancel_invalid_and_missing_sources(self):
        for module, folder in ((blog_ai, 'research'), (note_ai, 'blog')):
            with patch('builtins.input') as prompt:
                module.run()
                prompt.assert_not_called()
            file_utils.save_markdown(folder, 'theme', 'source')
            for answer in ('0', '-1', '2', 'abc'):
                with patch('builtins.input', return_value=answer):
                    module.run()
        self.assertEqual(self.calls, [])

    def test_invalid_themes_do_not_call_api(self):
        for theme in ('', '  ', '../escape', 'a/b', 'a\\b', 'CON', 'NUL.txt',
                      'a:', 'a.', 'a\nb', 'x' * 241):
            with self.subTest(theme=theme), self.assertRaises(ValueError):
                pipeline.run(theme)
        self.assertEqual(self.calls, [])

    def test_each_stage_failure_stops_following_stages(self):
        for failed in range(3):
            runners = [Mock(), Mock(), Mock()]
            runners[failed].side_effect = RuntimeError('failure')
            with patch.multiple(pipeline, research_run=runners[0],
                                blog_run=runners[1], note_run=runners[2]):
                with self.assertRaises(RuntimeError):
                    pipeline.run('theme')
            for index, runner in enumerate(runners):
                self.assertEqual(runner.call_count, int(index <= failed))

    def test_save_failure_stops_pipeline(self):
        with patch.object(blog_ai, 'save_markdown', side_effect=OSError):
            with self.assertRaises(OSError):
                pipeline.run('theme')
        self.assertEqual(len(self.calls), 2)
        self.assertIn('research result', file_utils.load_markdown('research', 'theme'))
        self.assertFalse((Path(self.temp.name) / 'data/note/theme.md').exists())

    def test_menu_asks_theme_once_and_recovers_without_exception_details(self):
        with patch('builtins.input', side_effect=['6', 'theme', '0']) as prompt:
            manager.main()
        self.assertEqual(prompt.call_count, 3)
        self.assertEqual(len(self.calls), 3)
        with patch('builtins.input', side_effect=['6', 'theme', '0']), \
             patch.object(manager, 'pipeline_run', side_effect=RuntimeError('SECRET_SENTINEL')):
            manager.main()
        self.assertNotIn('SECRET_SENTINEL', self.output.getvalue())
        self.assertIn('自動実行を停止', self.output.getvalue())

    def test_manual_menu_routing(self):
        with patch('builtins.input', side_effect=['1', '2', '3', '4', '5', 'bad', '0']), \
             patch.object(manager, 'research_run') as research, \
             patch.object(manager, 'blog_run') as blog, \
             patch.object(manager, 'note_run') as note:
            manager.main()
        for runner in (research, blog, note):
            runner.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
