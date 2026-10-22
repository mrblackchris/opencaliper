"""Launch the GUI from the source folder using the current Python environment."""
import sys


def main():
    from opencaliper.gui import run

    return run(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
