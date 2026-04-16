import sys
from unittest.mock import patch

from src.cli import main
from src.config import ConfigError
from src.models.pipeline import PipelineRun


MODULE = "src.cli"


class TestCLIMain:
    @patch(f"{MODULE}.run_pipeline")
    @patch(f"{MODULE}.validate_config")
    def test_main_calls_pipeline_default(self, mock_validate, mock_run):
        run = PipelineRun(trigger="cli", status="completed", news_count=2, variants_generated=3)
        mock_run.return_value = (run, [], [])

        with patch.object(sys, "argv", ["cli"]):
            exit_code = main()

        assert exit_code == 0
        mock_validate.assert_called_once()
        mock_run.assert_called_once_with(trigger="cli", max_articles=3, max_chars=280)

    @patch(f"{MODULE}.run_pipeline")
    @patch(f"{MODULE}.validate_config")
    def test_main_max_articles_flag(self, mock_validate, mock_run):
        run = PipelineRun(trigger="cli", status="completed", news_count=5, variants_generated=3)
        mock_run.return_value = (run, [], [])

        with patch.object(sys, "argv", ["cli", "--max-articles", "5"]):
            exit_code = main()

        assert exit_code == 0
        mock_run.assert_called_once_with(trigger="cli", max_articles=5, max_chars=280)

    @patch(f"{MODULE}.run_pipeline")
    @patch(f"{MODULE}.validate_config")
    def test_main_returns_1_on_failure(self, mock_validate, mock_run):
        run = PipelineRun(trigger="cli", status="failed", error="boom")
        mock_run.return_value = (run, [], [])

        with patch.object(sys, "argv", ["cli"]):
            exit_code = main()

        assert exit_code == 1

    @patch(f"{MODULE}.run_pipeline")
    @patch(f"{MODULE}.validate_config", side_effect=ConfigError("LLM_API_KEY required"))
    def test_main_exits_without_api_key(self, mock_validate, mock_run):
        with patch.object(sys, "argv", ["cli"]):
            exit_code = main()

        assert exit_code == 1
        mock_run.assert_not_called()
