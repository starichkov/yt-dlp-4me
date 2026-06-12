import re
import subprocess
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Optional, Union

# Regex to find a URL in a line.
# It looks for http/https followed by non-space characters,
# but stops at characters that usually end a URL in Markdown context like ) or ].
URL_PATTERN = r'https?://[^\s\)\]\>\"\'\,]+'

# Regex for section headers (case-insensitive, supports # and ##, optional space after #)
RE_DOWNLOADED = re.compile(r'^#{1,2}\s*Downloaded', re.IGNORECASE)
RE_FAILED = re.compile(r'^#{1,2}\s*Failed', re.IGNORECASE)
RE_PENDING = re.compile(r'^#{1,2}\s*Not downloaded yet', re.IGNORECASE)
RE_ANY_HEADER = re.compile(r'^#{1,2}(?![#])\s*')

DEFAULT_YT_DLP_PATH = str(Path.home() / 'bin' / 'yt-dlp_linux')

def parse_markdown(file_path: Union[str, Path]) -> List[Tuple[str, str]]:
    """Parses the Markdown file into a list of (section_name, line_text) tuples."""
    file_path = Path(file_path).expanduser()
    if not file_path.is_file():
        return []

    try:
        lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    section_map = []
    current_section = 'Other'
    
    for line in lines:
        stripped = line.strip()
        
        if RE_DOWNLOADED.match(stripped):
            current_section = 'Downloaded'
        elif RE_FAILED.match(stripped):
            current_section = 'Failed'
        elif RE_PENDING.match(stripped):
            current_section = 'Not downloaded yet'
        elif RE_ANY_HEADER.match(stripped):
            current_section = 'Other'
            
        section_map.append((current_section, line))

    return section_map

def extract_link(line: str) -> Optional[str]:
    """Extracts the first URL found in a line."""
    match = re.search(URL_PATTERN, line)
    return match.group(0) if match else None

def save_markdown(file_path: Union[str, Path], section_map: List[Tuple[str, str]]) -> None:
    """Saves the section map back to the Markdown file."""
    file_path = Path(file_path).expanduser()
    content = "".join(line for _, line in section_map)
    file_path.write_text(content, encoding='utf-8')

def download_video(link: str, output_dir: Union[str, Path], yt_dlp_path: str = DEFAULT_YT_DLP_PATH) -> Tuple[bool, bool]:
    """Runs yt-dlp for a given link and streams output to the console.
    Returns (success, already_existed).
    """
    output_dir = Path(output_dir).expanduser()
    yt_dlp_path = str(Path(yt_dlp_path).expanduser())
    print(f"\n>>> Starting download: {link}")
    # --color always helps keep the output pretty if the terminal supports it
    cmd = [yt_dlp_path, '--color', 'always', '-P', str(output_dir), link]
    
    already_existed = False
    try:
        # universal_newlines=True (alias 'text=True' in 3.7+) enable line-buffered output
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True, 
            bufsize=1
        )
        
        if process.stdout:
            for line in process.stdout:
                if "has already been downloaded" in line:
                    already_existed = True
                sys.stdout.write(line)
                sys.stdout.flush()
        
        process.wait()
        return process.returncode == 0, already_existed
    except Exception as e:
        print(f"\nError running yt-dlp: {e}")
        return False, False

def move_link_to_section(
    file_path: Union[str, Path], 
    target_link: str, 
    target_section_label: str, 
    target_section_header: str,
    source_section_label: str = 'Not downloaded yet'
) -> None:
    """Moves a link from the source section to the specified target section."""
    file_path = Path(file_path).expanduser()
    section_map = parse_markdown(file_path)
    if not section_map:
        return

    # Find the line again (content might have changed if someone edited the file)
    found_idx = -1
    for i, (section, line) in enumerate(section_map):
        if section == source_section_label and extract_link(line) == target_link:
            found_idx = i
            break

    if found_idx == -1:
        return

    moving_line = section_map.pop(found_idx)
    
    # Find position for the target section header
    target_header_idx = -1
    for i, (section, l) in enumerate(section_map):
        if section == target_section_label and RE_ANY_HEADER.match(l.strip()):
            target_header_idx = i
            break
    
    if target_header_idx != -1:
        # Find the last line that belongs to this section and has content
        last_content_idx = target_header_idx
        for i in range(target_header_idx + 1, len(section_map)):
            if section_map[i][0] == target_section_label:
                if section_map[i][1].strip():
                    last_content_idx = i
            else:
                break
        
        insert_pos = last_content_idx + 1
        section_map.insert(insert_pos, (target_section_label, moving_line[1]))
    else:
        # Create the section if missing
        # Check if there is a main header at all
        if section_map and section_map[0][1].startswith('# '):
             # Insert after the main title and potentially a blank line
             insert_at = 1
             if len(section_map) > 1 and section_map[1][1].strip() == '':
                 insert_at = 2
             
             section_map.insert(insert_at, (target_section_label, f'{target_section_header}\n'))
             section_map.insert(insert_at + 1, (target_section_label, moving_line[1]))
             section_map.insert(insert_at + 2, ('Other', '\n'))
        else:
             section_map.insert(0, (target_section_label, f'{target_section_header}\n'))
             section_map.insert(1, (target_section_label, moving_line[1]))
             section_map.insert(2, ('Other', '\n'))
    
    save_markdown(file_path, section_map)

def cleanup_markdown(file_path: Union[str, Path]) -> None:
    """Removes duplicate links from the Markdown file.
    - If a link exists in 'Downloaded', it is removed from 'Not downloaded yet' and 'Failed'.
    - If a link exists in 'Failed', it is removed from 'Not downloaded yet'.
    - Duplicates within the same section are removed (keeping the first occurrence).
    """
    file_path = Path(file_path).expanduser()
    section_map = parse_markdown(file_path)
    if not section_map:
        return

    print(f">>> Cleaning up Markdown: Removing duplicates and cross-section links...")
    # 1. Identify all links in each section to establish priorities
    downloaded_links = set()
    failed_links = set()
    
    for section, line in section_map:
        link = extract_link(line)
        if not link:
            continue
        if section == 'Downloaded':
            downloaded_links.add(link)
        elif section == 'Failed':
            failed_links.add(link)

    # 2. Rebuild the map, filtering out duplicates
    new_section_map = []
    seen_in_processed_sections = set()
    
    for section, line in section_map:
        link = extract_link(line)
        
        # Keep non-link lines and lines in 'Other' sections as-is
        if not link or section == 'Other':
            new_section_map.append((section, line))
            continue
            
        is_duplicate = False
        if section == 'Downloaded':
            if link in seen_in_processed_sections:
                is_duplicate = True
        elif section == 'Failed':
            if link in downloaded_links or link in seen_in_processed_sections:
                is_duplicate = True
        elif section == 'Not downloaded yet':
            if link in downloaded_links or link in failed_links or link in seen_in_processed_sections:
                is_duplicate = True
        
        if is_duplicate:
            continue
            
        seen_in_processed_sections.add(link)
        new_section_map.append((section, line))
        
    save_markdown(file_path, new_section_map)
    print(">>> Cleanup complete.")

def print_summary(downloaded: List[str], failed: List[str], already_existed: List[str] = None) -> None:
    """Prints a summary of the session's activity."""
    already_existed = already_existed or []
    print("\n" + "="*40)
    print("DOWNLOAD SUMMARY")
    print("="*40)
    print(f"Successfully downloaded: {len(downloaded)}")
    for link in downloaded:
        print(f"  [OK] {link}")
    
    if already_existed:
        print(f"Already existed: {len(already_existed)}")
        for link in already_existed:
            print(f"  [SKIP] {link}")

    if failed:
        print(f"Failed: {len(failed)}")
        for link in failed:
            print(f"  [FAIL] {link}")
    print("="*40)

def process_queue(input_file: str, output_dir: str, verify: bool = False, yt_dlp_path: str = DEFAULT_YT_DLP_PATH) -> Tuple[List[str], List[str], List[str]]:
    """Processes the Markdown file and downloads videos in the queue.
    If verify is True, processes the 'Downloaded' section instead.
    Returns (downloaded, failed, already_existed).
    """
    input_path = Path(input_file).expanduser()
    output_path = Path(output_dir).expanduser()
    yt_dlp_path = str(Path(yt_dlp_path).expanduser())
    
    downloaded_this_session: List[str] = []
    failed_this_session: List[str] = []
    already_existed_this_session: List[str] = []

    source_section = 'Downloaded' if verify else 'Not downloaded yet'
    print(f">>> Scanning section '{source_section}' for links...")

    try:
        # Main processing loop
        while True:
            section_map = parse_markdown(input_path)
            if not section_map:
                break
                
            target_link: Optional[str] = None
            
            # Find the first unprocessed link in source section
            for section, line in section_map:
                if section == source_section:
                    link = extract_link(line)
                    if link and link not in downloaded_this_session and \
                       link not in failed_this_session and \
                       link not in already_existed_this_session:
                        target_link = link
                        break
            
            if not target_link:
                # No more links to process
                break
                
            success, already_exists = download_video(target_link, output_path, yt_dlp_path=yt_dlp_path)
            
            if success:
                if already_exists:
                    print(f">>> File already exists. Skipping.")
                    already_existed_this_session.append(target_link)
                else:
                    print(f">>> Download successful!")
                    downloaded_this_session.append(target_link)
                
                if not verify:
                    print(f">>> Moving link to 'Downloaded' section.")
                    move_link_to_section(input_path, target_link, 'Downloaded', '## Downloaded')
            else:
                print(f">>> Download failed! Moving link to 'Failed' section.")
                failed_this_session.append(target_link)
                move_link_to_section(input_path, target_link, 'Failed', '## Failed', source_section_label=source_section)
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")

    return downloaded_this_session, failed_this_session, already_existed_this_session

def main() -> None:
    parser = argparse.ArgumentParser(description='yt-dlp wrapper to manage downloads via Markdown file sections.')
    parser.add_argument('input_file', help='Path to the Markdown file containing links.')
    parser.add_argument('output_dir', help='Directory where videos will be saved.')
    parser.add_argument('--verify', action='store_true', help='Verify and re-download missing videos from the Downloaded section.')
    parser.add_argument('--yt-dlp-path', default=DEFAULT_YT_DLP_PATH, help=f'Path to the yt-dlp executable (default: {DEFAULT_YT_DLP_PATH}).')
    args = parser.parse_args()

    input_path = Path(args.input_file).expanduser()
    output_path = Path(args.output_dir).expanduser()
    yt_dlp_path = str(Path(args.yt_dlp_path).expanduser())

    if not input_path.exists():
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)

    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)

    if args.verify:
        print(f"Mode: Verify (checking '{input_path}' against '{output_path}')")
        cleanup_markdown(args.input_file)
    else:
        print(f"Mode: Download (processing queue in '{input_path}')")

    downloaded, failed, skipped = process_queue(args.input_file, args.output_dir, verify=args.verify, yt_dlp_path=args.yt_dlp_path)
    print_summary(downloaded, failed, skipped)

if __name__ == "__main__":
    main()
