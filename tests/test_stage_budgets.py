import contextlib
import copy
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
if 'openai' not in sys.modules:
    sys.modules['openai'] = SimpleNamespace(OpenAI=Mock())
import config
import pipeline
from agents import research_ai, blog_ai, note_ai
from utils import ai_utils, file_utils

STAGES = ('research', 'blog', 'note')
AGENTS = (research_ai, blog_ai, note_ai)


class StageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        redirect = contextlib.redirect_stdout(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        self.factory = Mock(return_value=self.client)
        self.response = SimpleNamespace(status='completed', output_text='article',
            usage=SimpleNamespace(input_tokens=176, output_tokens=3000),
            incomplete_details=SimpleNamespace(reason='max_output_tokens'))
        self.client.responses.create.return_value = self.response

    def test_pipeline_quote_sums_stage_limits(self):
        self.assertAlmostEqual(ai_utils.estimate_usd(36000, stages=STAGES), .465)
        with patch('builtins.input', return_value='n'):
            self.assertFalse(ai_utils.confirm_cost(36000, stages=STAGES))
        self.assertIn('69.8円', self.output.getvalue())
        self.assertIn('Blog AI：出力上限3500', self.output.getvalue())
        self.assertIn('上限保証ではありません', self.output.getvalue())

    def test_changed_limit_changes_quote_and_actual_request(self):
        settings = copy.deepcopy(config.STAGE_SETTINGS)
        settings['blog']['max_output_tokens'] = 5000
        with patch.object(config, 'STAGE_SETTINGS', settings), patch('builtins.input', return_value='y'):
            self.assertAlmostEqual(ai_utils.estimate_usd(36000, stages=STAGES), .51)
            ai_utils.generate_text(self.factory, 'prompt', stage='blog')
        self.assertEqual(self.client.responses.create.call_args.kwargs['max_output_tokens'], 5000)
        self.assertIn('Blog AI：出力上限5000', self.output.getvalue())

    def test_each_stage_uses_approved_limits_without_retry(self):
        for stage, limit in zip(STAGES, (3000,3500,3000)):
            self.client.reset_mock()
            with patch('builtins.input', return_value='y') as approval:
                ai_utils.generate_text(self.factory, 'prompt', stage=stage)
            approval.assert_called_once()
            self.client.responses.create.assert_called_once()
            kwargs = self.client.responses.create.call_args.kwargs
            self.assertEqual(kwargs['max_output_tokens'], limit)
            self.assertEqual(kwargs['reasoning'], {'effort':'none'})
        self.factory.assert_called_with(max_retries=0, timeout=120.0)

    def test_manual_decline_does_not_construct_client(self):
        with patch('builtins.input', return_value='n'):
            self.assertIsNone(ai_utils.generate_text(self.factory, 'prompt', stage='blog'))
        self.factory.assert_not_called()

    def test_invalid_stage_settings_fail_before_approval_or_client(self):
        for key,value in (('max_output_tokens',0),('max_output_tokens',128001),
                          ('reasoning_effort','bad'),('characters',(900,600)),
                          ('characters',(True,900))):
            settings = copy.deepcopy(config.STAGE_SETTINGS)
            settings['research'][key] = value
            with self.subTest(key=key,value=value), patch.object(config,'STAGE_SETTINGS',settings), patch('builtins.input') as approval:
                with self.assertRaises(ai_utils.GenerationError):
                    ai_utils.generate_text(self.factory,'prompt',stage='research')
                approval.assert_not_called()
        self.factory.assert_not_called()

    def test_invalid_later_stage_aborts_pipeline_before_approval(self):
        settings = copy.deepcopy(config.STAGE_SETTINGS)
        settings['note']['max_output_tokens'] = -1
        with patch.object(config,'STAGE_SETTINGS',settings), patch('builtins.input') as approval, patch.object(pipeline,'research_run') as research:
            with self.assertRaises(ai_utils.GenerationError):
                pipeline.run('theme')
        approval.assert_not_called()
        research.assert_not_called()

    def test_incomplete_reports_stage_reason_usage_and_cost(self):
        self.response.status = 'incomplete'
        with self.assertRaises(ai_utils.GenerationError):
            ai_utils.generate_text(self.factory,'prompt',stage='research',session=ai_utils.CostSession())
        output = self.output.getvalue()
        for text in ('Research AI','出力上限に到達','入力176','出力3000','$0.09088','13.63円','次のAIには渡しません','再試行は行いません'):
            self.assertIn(text,output)
        self.client.responses.create.assert_called_once()

    def test_missing_usage_does_not_claim_zero_cost(self):
        self.response.status = 'incomplete'
        self.response.usage = None
        session = ai_utils.CostSession()
        with self.assertRaises(ai_utils.GenerationError):
            ai_utils.generate_text(self.factory,'prompt',stage='note',session=session)
        self.assertTrue(session.unknown_usage)
        self.assertIn('費用を計算できません',self.output.getvalue())
        self.assertNotIn('$0.00000',self.output.getvalue())

    def test_unknown_reason_and_partial_text_are_not_disclosed(self):
        self.response.status = 'incomplete'
        self.response.output_text = 'SECRET_SENTINEL'
        for reason in ('SECRET_SENTINEL',{'secret':'SECRET_SENTINEL'},None):
            self.response.incomplete_details.reason = reason
            with self.assertRaises(ai_utils.GenerationError):
                ai_utils.generate_text(self.factory,'prompt',stage='blog',session=ai_utils.CostSession())
        self.assertNotIn('SECRET_SENTINEL',self.output.getvalue())
        self.assertIn('未対応',self.output.getvalue())

    def test_content_filter_is_distinguished_from_output_limit(self):
        self.response.status = 'incomplete'
        self.response.incomplete_details.reason = 'content_filter'
        with self.assertRaises(ai_utils.GenerationError):
            ai_utils.generate_text(self.factory,'prompt',stage='blog',session=ai_utils.CostSession())
        self.assertIn('コンテンツフィルター',self.output.getvalue())
        self.assertNotIn('出力上限に到達',self.output.getvalue())

    def test_prompts_follow_character_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(file_utils,'__file__',str(Path(directory)/'src/utils/file_utils.py')):
            for stage,module in zip(STAGES,AGENTS):
                with patch.object(module,'generate_text',return_value='text') as generate, patch.object(module,'load_markdown',return_value='source',create=True):
                    module.run('theme')
                low,high = config.STAGE_SETTINGS[stage]['characters']
                self.assertIn(f'{low}～{high}文字',generate.call_args.args[1])
                self.assertEqual(generate.call_args.kwargs['stage'],stage)
                self.assertIn('主要ポイントは3点以内',generate.call_args.args[1])

    def test_incomplete_at_each_stage_preserves_old_article_and_stops_next(self):
        for failed_index in range(3):
            with self.subTest(failed_index=failed_index), tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
                root = Path(directory)
                stack.enter_context(patch.object(file_utils,'__file__',str(root/'src/utils/file_utils.py')))
                for stage in STAGES:
                    p = root/'data'/stage/'theme.md'
                    p.parent.mkdir(parents=True)
                    p.write_bytes(b'old article')
                responses = [SimpleNamespace(status='completed',output_text='## Intro\ntext',usage=SimpleNamespace(input_tokens=100,output_tokens=200)) for _ in range(failed_index)]
                self.response.status = 'incomplete'
                responses.append(self.response)
                self.client.responses.create.side_effect = responses
                self.client.reset_mock()
                for module in AGENTS:
                    stack.enter_context(patch.object(module,'OpenAI',self.factory))
                approval = stack.enter_context(patch('builtins.input',return_value='y'))
                with self.assertRaises(ai_utils.GenerationError):
                    pipeline.run('theme')
                approval.assert_called_once()
                self.assertEqual(self.client.responses.create.call_count,failed_index+1)
                for stage in STAGES[failed_index:]:
                    self.assertEqual((root/'data'/stage/'theme.md').read_bytes(),b'old article')
                    self.assertFalse((root/'data'/stage/'history').exists())

    def test_successful_pipeline_quotes_stage_budgets_once(self):
        def success(theme, *, session):
            session.attempts += 1
            session.record(self.response.usage)
        with patch('builtins.input',return_value='y') as approval, patch.object(pipeline,'research_run',side_effect=success), patch.object(pipeline,'blog_run',side_effect=success), patch.object(pipeline,'note_run',side_effect=success):
            pipeline.run('theme')
        approval.assert_called_once()
        self.assertIn('$0.4650',self.output.getvalue())
        self.assertIn('$0.2726',self.output.getvalue())


    def test_reasoning_usage_breakdown_does_not_double_count_cost(self):
        self.response.status = 'incomplete'
        self.response.usage.output_tokens_details = SimpleNamespace(reasoning_tokens=1000)
        session = ai_utils.CostSession()
        with self.assertRaises(ai_utils.GenerationError):
            ai_utils.generate_text(self.factory,'prompt',stage='research',session=session)
        self.assertEqual(session.usages,[(176,3000)])
        self.assertIn('推論：1000トークン',self.output.getvalue())
        self.assertIn('$0.09088',self.output.getvalue())

    def test_malformed_reasoning_breakdown_is_unknown(self):
        self.response.status = 'incomplete'
        self.response.usage.output_tokens_details = SimpleNamespace(reasoning_tokens=4000)
        with self.assertRaises(ai_utils.GenerationError):
            ai_utils.generate_text(self.factory,'prompt',stage='research',session=ai_utils.CostSession())
        self.assertIn('内訳は取得できません',self.output.getvalue())
        self.assertNotIn('推論：4000',self.output.getvalue())
