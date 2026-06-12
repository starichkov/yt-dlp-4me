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

def parse_markdown(file_path: Union[str, Path]) -> List[Tuple[str, str]]:
    """Parses the markdown file into a list of (section_name, line_text) tuples."""
    file_path = Path(file_path)
    if not file_path.is_file():
        return []

    try:
        lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    section_map = []
    current_section = 'Other'
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('## Downloaded'):
            current_section = 'Downloaded'
        elif stripped.startswith('## Failed'):
            current_section = 'Failed'
        elif stripped.startswith('## Not downloaded yet'):
            current_section = 'Not downloaded yet'
        elif (stripped.startswith('## ') or stripped == '##') and not (
            stripped.startswith('## Downloaded') or 
            stripped.startswith('## Failed') or 
            stripped.startswith('## Not downloaded yet')
        ):
            current_section = 'Other'
        elif stripped.startswith('# ') and i > 0:
            current_section = 'Other'
            
        section_map.append((current_section, line))

    return section_map

def extract_link(line: str) -> Optional[str]:
    """Extracts the first URL found in a line."""
    match = re.search(URL_PATTERN, line)
    return match.group(0) if match else None

def save_markdown(file_path: Union[str, Path], section_map: List[Tuple[str, str]]) -> None:
    """Saves the section map back to the markdown file."""
    file_path = Path(file_path)
    content = "".join(line for _, line in section_map)
    file_path.write_text(content, encoding='utf-8')

def download_video(link: str, output_dir: Union[str, Path]) -> bool:
    """Runs yt-dlp for a given link and streams output to console."""
    output_dir = Path(output_dir)
    print(f"\n>>> Starting download: {link}")
    # --color always helps keep the output pretty if the terminal supports it
    cmd = ['yt-dlp', '--color', 'always', '-o', str(output_dir / '%(title)s.%(ext)s'), link]
    
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
                sys.stdout.write(line)
                sys.stdout.flush()
        
        process.wait()
        return process.returncode == 0
    except Exception as e:
        print(f"\nError running yt-dlp: {e}")
        return False

def move_link_to_section(file_path: Union[str, Path], target_link: str, section_label: str, section_header: str) -> None:
    """Moves a link from 'Not downloaded yet' to the specified section."""
    file_path = Path(file_path)
    section_map = parse_markdown(file_path)
    if not section_map:
        return

    # Find the line again (content might have changed if someone edited the file)
    found_idx = -1
    for i, (section, line) in enumerate(section_map):
        if section == 'Not downloaded yet' and extract_link(line) == target_link:
            found_idx = i
            break

    if found_idx == -1:
        return

    moving_line = section_map.pop(found_idx)
    
    # Find position for the target section
    target_header_idx = -1
    for i, (_, l) in enumerate(section_map):
        if l.strip().startswith(section_header):
            target_header_idx = i
            break
    
    if target_header_idx != -1:
        # Find the last line that belongs to this section and has content
        last_content_idx = target_header_idx
        for i in range(target_header_idx + 1, len(section_map)):
            if section_map[i][0] == section_label:
                if section_map[i][1].strip():
                    last_content_idx = i
            else:
                break
        
        insert_pos = last_content_idx + 1
        section_map.insert(insert_pos, (section_label, moving_line[1]))
    else:
        # Create the section if missing
        # Check if there is a main header at all
        if section_map and section_map[0][1].startswith('# '):
             # Insert after the main title and potentially a blank line
             insert_at = 1
             if len(section_map) > 1 and section_map[1][1].strip() == '':
                 insert_at = 2
             
             section_map.insert(insert_at, (section_label, f'{section_header}\n'))
             section_map.insert(insert_at + 1, (section_label, moving_line[1]))
             section_map.insert(insert_at + 2, ('Other', '\n'))
        else:
             section_map.insert(0, (section_label, f'{section_header}\n'))
             section_map.insert(1, (section_label, moving_line[1]))
             section_map.insert(2, ('Other', '\n'))
    
    save_markdown(file_path, section_map)

def print_summary(downloaded: List[str], failed: List[str]) -> None:
    """Prints a summary of the session's activity."""
    print("\n" + "="*40)
    print("DOWNLOAD SUMMARY")
    print("="*40)
    print(f"Successfully downloaded: {len(downloaded)}")
    for link in downloaded:
        print(f"  [OK] {link}")
    if failed:
        print(f"Failed: {len(failed)}")
        for link in failed:
            print(f"  [FAIL] {link}")
    print("="*40)

def process_queue(input_file: str, output_dir: str) -> Tuple[List[str], List[str]]:
    """Processes the markdown file and downloads videos in the queue."""
    input_path = Path(input_file)
    output_path = Path(output_dir)
    
    downloaded_this_session: List[str] = []
    failed_this_session: List[str] = []

    try:
        # Main processing loop
        while True:
            section_map = parse_markdown(input_path)
            if not section_map:
                break
                
            target_link: Optional[str] = None
            
            # Find the first unprocessed link in "Not downloaded yet" section
            for section, line in section_map:
                if section == 'Not downloaded yet':
                    link = extract_link(line)
                    if link and link not in downloaded_this_session and link not in failed_this_session:
                        target_link = link
                        break
            
            if not target_link:
                # No more links to process
                break
                
            success = download_video(target_link, output_path)
            
            if success:
                downloaded_this_session.append(target_link)
                move_link_to_section(input_path, target_link, 'Downloaded', '## Downloaded')
            else:
                failed_this_session.append(target_link)
                move_link_to_section(input_path, target_link, 'Failed', '## Failed')
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")

    return downloaded_this_session, failed_this_session

def main() -> None:
    parser = argparse.ArgumentParser(description='yt-dlp wrapper to manage downloads via Markdown file sections.')
    parser.add_argument('input_file', help='Path to the Markdown file containing links.')
    parser.add_argument('output_dir', help='Directory where videos will be saved.')
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_dir)

    if not input_path.exists():
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)

    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)

    downloaded, failed = process_queue(args.input_file, args.output_dir)
    print_summary(downloaded, failed)

if __name__ == "__main__":
    main()
