[![Author](https://img.shields.io/badge/Author-Vadim%20Starichkov-blue?style=for-the-badge)](https://github.com/starichkov)
[![GitHub License](https://img.shields.io/github/license/starichkov/yt-dlp-4me?style=for-the-badge)](https://github.com/starichkov/yt-dlp-4me/blob/main/LICENSE.md)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/starichkov/yt-dlp-4me/python.yml?style=for-the-badge)](https://github.com/starichkov/yt-dlp-4me/actions/workflows/python.yml)
[![Codecov](https://img.shields.io/codecov/c/github/starichkov/yt-dlp-4me?style=for-the-badge)](https://codecov.io/gh/starichkov/yt-dlp-4me)

# yt-dlp Markdown Wrapper

A Python wrapper for `yt-dlp` that allows you to manage video download queues directly within Markdown files.

## Features

- **Markdown-based Queue**: Use a simple Markdown file to list videos you want to download.
- **Automatic Status Tracking**: Links are automatically moved between sections based on the download result:
    - From `## Not downloaded yet` to `## Downloaded` on success.
    - From `## Not downloaded yet` to `## Failed` on failure.
- **Real-time Progress**: Streams `yt-dlp` output directly to your console so you can see the download progress.
- **Flexible Parsing**: Supports various Markdown link formats (plain URLs, labeled links like `[Title](URL)`, or list items).
- **Session Summary**: Provides a clear report of successful and failed downloads at the end of each run.
- **Interrupt Handling**: Gracefully handles `Ctrl+C` to stop the process and save the current state.

## Prerequisites

- **Python 3.10+** (Recommended baseline as Python 3.9 has reached EOL).
- **yt-dlp**: Must be installed and available in your system's PATH. (Note: Latest `yt-dlp` versions require **Python 3.9+**).
  - [yt-dlp Installation Instructions](https://github.com/yt-dlp/yt-dlp#installation)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/starichkov/yt-dlp-4me.git
   cd yt-dlp-4me
   ```

2. (Optional) Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

## Usage

Run the wrapper by specifying your Markdown queue file and the desired output directory for the videos:

```bash
python3 yt_dlp_wrapper.py <queue_file.md> <output_directory>
```

### Example

```bash
python3 yt_dlp_wrapper.py example.md ./downloads
```

## Markdown File Format

The tool looks for specific second-level headers to manage the queue. You can see a full reference in [example.md](example.md).

### Required Sections

- `## Not downloaded yet`: Place the links you want to download here.
- `## Downloaded`: Successfully downloaded links will be moved here.
- `## Failed`: Links that failed to download will be moved here.

### Sample Structure

```markdown
# My Video Queue

## Not downloaded yet
- https://www.youtube.com/watch?v=dQw4w9WgXcQ
- [Big Buck Bunny](https://www.youtube.com/watch?v=aqz-KE-bpKQ)

## Downloaded

## Failed
```

## Running Tests

The project includes a comprehensive test suite to ensure robust parsing and processing.

```bash
python3 test_wrapper.py
```

## License & Attribution

This project is licensed under the **MIT License** - see the [LICENSE](https://github.com/starichkov/yt-dlp-4me/blob/main/LICENSE.md) file for details.

### Using This Project?

If you use this code in your own projects, attribution is required under the MIT License:

```
Based on yt-dlp-4me by Vadim Starichkov, TemplateTasks

https://github.com/starichkov/yt-dlp-4me
```

**Copyright © 2026 Vadim Starichkov, TemplateTasks**
