"""Run with Python 3.13.9: python main_cli.py --text known."""

from qr_app.presentation.cli import configure_stdio, main


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
