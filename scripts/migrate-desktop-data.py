import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_migration import migrate_legacy_data


def migrate(source_root):
    result = migrate_legacy_data(source_root)
    print(f"Desktop data directory: {result['data_dir']}")
    print(f"Desktop config directory: {result['config_dir']}")
    print(f"Copied database/state files: {result['state_files']}")
    print(f"Copied credential files: {result['credential_files']}")
    print(f"Copied import files: {result['import_files']}")
    print("Existing desktop files were left untouched.")


def main():
    parser = argparse.ArgumentParser(description="Migrate an AiOS development profile into desktop storage.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path.cwd(),
        help="AiOS repository or legacy data directory.",
    )
    args = parser.parse_args()
    migrate(args.source)


if __name__ == "__main__":
    main()
