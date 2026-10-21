"""Optional explicit exact-duplicate scan, entirely read-only."""
import argparse
from .scanner import scan
from .optimization import find_duplicates
import time
from .models import format_size


def main():
    parser = argparse.ArgumentParser(description='LocalScope exact duplicate report (read-only)')
    parser.add_argument('folder', help='Folder to scan')
    parser.add_argument('--max-file-gib', type=float, default=2.0,
                        help='Maximum size of an individual file to hash (default: 2 GiB)')
    args = parser.parse_args()
    if args.max_file_gib <= 0:
        parser.error('--max-file-gib must be positive')
    print('Scanning metadata...')
    root = scan(args.folder)
    print('Hashing candidate files (progress every 2 seconds)...', flush=True)
    last = [0.0]
    def status(phase, done, total, path, bytes_read):
        now = time.monotonic()
        if now - last[0] >= 2 or phase == 'Complete':
            last[0] = now
            print(f'[{phase}] {done:,}/{total:,} | {format_size(bytes_read)} read | {path}', flush=True)
    def diagnostic(kind, path, value):
        print(f'[DIAGNOSTIC] {kind}: {path} ({value})', flush=True)
    groups, hashed, skipped = find_duplicates(root,
        max_file_bytes=int(args.max_file_gib * 1024**3),
        status=status, diagnostic=diagnostic)
    print(f'Exact duplicate groups: {len(groups)}')
    print(f'Extra identical bytes (NOT confirmed recoverable): {format_size(sum(g.extra_bytes for g in groups))}')
    print(f'Files hashed: {hashed}; skipped: {skipped}')
    for group in groups:
        print(f'\n{len(group.paths)} identical files: ' + ' | '.join(group.paths))
    print('\nNo files were changed or deleted.')


if __name__ == '__main__':
    main()
