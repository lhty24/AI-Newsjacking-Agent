from unittest.mock import patch

from src.cli import main
from src.models.pipeline import PipelineRun


MODULE = "src.cli"


class TestCLIMain:
    @patch(f"{MODULE}.run_pipeline")
    @patch(f"{MODULE}.LLM_API_KEY", "test-key")
    def test_main_calls_pipeline(self, mock_run):
        run = PipelineRun(trigger="cli", status="completed", news_count=2, variants_generated=3)
        mock_run.return_value = (run, [])

        exit_code = main()

        assert exit_code == 0
        mock_run.assert_called_once_with(trigger="cli")

    @patch(f"{MODULE}.run_pipeline")
    @patch(f"{MODULE}.LLM_API_KEY", "test-key")
    def test_main_returns_1_on_failure(self, mock_run):
        run = PipelineRun(trigger="cli", status="failed", error="boom")
        mock_run.return_value = (run, [])

        exit_code = main()

        assert exit_code == 1

    @patch(f"{MODULE}.run_pipeline")
    @patch(f"{MODULE}.LLM_API_KEY", "")
    def test_main_exits_without_api_key(self, mock_run):
        exit_code = main()

        assert exit_code == 1
        mock_run.assert_not_called()
