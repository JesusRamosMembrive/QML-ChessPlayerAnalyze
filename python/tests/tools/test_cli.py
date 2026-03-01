"""Tests for CLI argument parsing."""

from tools.debug_cli import build_parser


class TestCLIParser:
    def test_analyze_pgn_command(self):
        parser = build_parser()
        args = parser.parse_args(["analyze-pgn", "game.pgn", "--player", "white", "--depth", "16"])
        assert args.command == "analyze-pgn"
        assert args.pgn_file == "game.pgn"
        assert args.player == "white"
        assert args.depth == 16

    def test_analyze_pgn_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["analyze-pgn", "game.pgn", "--player", "white"])
        assert args.depth == 12
        assert args.multipv == 5
        assert args.opening_moves == 15
        assert args.endgame_pieces == 12

    def test_score_command(self):
        parser = build_parser()
        args = parser.parse_args(["score", "results.json"])
        assert args.command == "score"
        assert args.result_file == "results.json"

    def test_inspect_game_command(self):
        parser = build_parser()
        args = parser.parse_args(["inspect-game", "results.json", "--game", "3"])
        assert args.command == "inspect-game"
        assert args.game == 3

    def test_analyze_batch_command(self):
        parser = build_parser()
        args = parser.parse_args([
            "analyze-batch", "./pgns/cheaters/",
            "--label", "cheater", "--player", "white",
        ])
        assert args.command == "analyze-batch"
        assert args.label == "cheater"
        assert args.player == "white"

    def test_compare_command(self):
        parser = build_parser()
        args = parser.parse_args(["compare", "./results/a/", "./results/b/"])
        assert args.command == "compare"
        assert args.dir_a == "./results/a/"
        assert args.dir_b == "./results/b/"
