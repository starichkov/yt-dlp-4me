import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

import yt_dlp_wrapper as wrapper


class TestYtDlpWrapper(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.md_file = self.test_dir / "test.md"

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_extract_link(self):
        self.assertEqual(wrapper.extract_link("- https://example.com/video"), "https://example.com/video")
        self.assertEqual(wrapper.extract_link("[Video](https://example.com/video)"), "https://example.com/video")
        self.assertEqual(wrapper.extract_link("No link here"), None)
        self.assertEqual(wrapper.extract_link("- https://example.com/v1 and https://example.com/v2"),
                         "https://example.com/v1")
        self.assertEqual(wrapper.extract_link("- https://example.com/video) trailing bracket"),
                         "https://example.com/video")

    def test_process_queue_keyboard_interrupt(self):
        content = """# Queue
## Not downloaded yet
- https://link1.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        with patch.object(wrapper, 'download_video') as mock_download:
            mock_download.side_effect = KeyboardInterrupt()

            # Should not raise exception, just return what was processed so far
            downloaded, failed = wrapper.process_queue(self.md_file, "out")

            self.assertEqual(downloaded, [])
            self.assertEqual(failed, [])

    def test_parse_markdown_missing_file(self):
        self.assertEqual(wrapper.parse_markdown("non_existent.md"), [])

    def test_parse_markdown_basic(self):
        content = """# My Videos
## Downloaded
- https://link1.com
## Not downloaded yet
- https://link2.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        section_map = wrapper.parse_markdown(self.md_file)
        expected = [
            ('Other', '# My Videos\n'),
            ('Downloaded', '## Downloaded\n'),
            ('Downloaded', '- https://link1.com\n'),
            ('Not downloaded yet', '## Not downloaded yet\n'),
            ('Not downloaded yet', '- https://link2.com\n')
        ]
        self.assertEqual(section_map, expected)

    def test_move_link_to_section_success(self):
        content = """# My Videos
## Downloaded
## Not downloaded yet
- https://link1.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        wrapper.move_link_to_section(self.md_file, "https://link1.com", 'Downloaded', '## Downloaded')

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        self.assertIn('## Downloaded\n- https://link1.com\n', new_content)
        self.assertNotIn('## Not downloaded yet\n- https://link1.com\n', new_content)

    def test_move_link_to_section_create_failed(self):
        content = """# My Videos
## Not downloaded yet
- https://link1.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        wrapper.move_link_to_section(self.md_file, "https://link1.com", 'Failed', '## Failed')

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        self.assertIn('## Failed\n- https://link1.com\n', new_content)

    def test_move_link_to_section_no_main_header(self):
        content = """## Not downloaded yet
- https://link1.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        wrapper.move_link_to_section(self.md_file, "https://link1.com", 'Downloaded', '## Downloaded')

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        self.assertTrue(new_content.startswith('## Downloaded\n- https://link1.com\n'))

    def test_move_link_to_section_multiple_items(self):
        content = """# Videos
## Downloaded
- https://link-existing.com
## Not downloaded yet
- https://link1.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        wrapper.move_link_to_section(self.md_file, "https://link1.com", 'Downloaded', '## Downloaded')

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        # Should be inserted after existing items in section
        expected = "# Videos\n## Downloaded\n- https://link-existing.com\n- https://link1.com\n## Not downloaded yet\n"
        self.assertEqual(new_content, expected)

    def test_move_link_to_section_with_blank_line(self):
        content = """# Videos

## Not downloaded yet
- https://link1.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        wrapper.move_link_to_section(self.md_file, "https://link1.com", 'Downloaded', '## Downloaded')

        with open(self.md_file, 'r') as f:
            lines = f.readlines()

        # Should insert after the blank line (line 2 index)
        self.assertEqual(lines[0], "# Videos\n")
        self.assertEqual(lines[1], "\n")
        self.assertEqual(lines[2], "## Downloaded\n")

    def test_parse_markdown_other_sections(self):
        content = """# Title
## Not downloaded yet
- https://link1.com
## Unknown Section
Some text
# Another Title
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        section_map = wrapper.parse_markdown(self.md_file)
        # ## Unknown Section should be 'Other'
        # # Another Title should be 'Other'
        self.assertEqual(section_map[3][0], 'Other')  # ## Unknown Section
        self.assertEqual(section_map[5][0], 'Other')  # # Another Title

    def test_print_summary(self):
        with patch('sys.stdout') as mock_stdout:
            wrapper.print_summary(["link1"], ["link2"])
            # Just verify it doesn't crash and prints something
            self.assertTrue(mock_stdout.write.called)

    @patch('subprocess.Popen')
    def test_download_video_exception(self, mock_popen):
        mock_popen.side_effect = Exception("Failed to start")
        result = wrapper.download_video("https://link.com", "out")
        self.assertFalse(result)

    @patch('subprocess.Popen')
    def test_download_video_with_output(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ["line 1\n", "line 2\n"]
        mock_popen.return_value = mock_process

        result = wrapper.download_video("https://link.com", "out")
        self.assertTrue(result)

    def test_main_success(self):
        # Patch the wrapper object directly
        with patch.object(wrapper, 'process_queue', return_value=([], [])):
            with patch.object(wrapper, 'print_summary'):
                # Ensure the file exists
                with open(self.md_file, 'w') as f:
                    f.write("## Not downloaded yet\n")
                with patch('sys.argv', ['yt_dlp_wrapper.py', str(self.md_file), str(self.test_dir)]):
                    wrapper.main()

    def test_main_file_not_found(self):
        with patch('sys.argv', ['yt_dlp_wrapper.py', "non_existent.md", str(self.test_dir)]):
            with self.assertRaises(SystemExit) as cm:
                wrapper.main()
            self.assertEqual(cm.exception.code, 1)

    def test_main_create_dir(self):
        new_dir = self.test_dir / "new_output"
        # Ensure the file exists
        with open(self.md_file, 'w') as f:
            f.write("## Not downloaded yet\n")
        with patch.object(wrapper, 'process_queue', return_value=([], [])):
            with patch.object(wrapper, 'print_summary'):
                with patch('sys.argv', ['yt_dlp_wrapper.py', str(self.md_file), str(new_dir)]):
                    wrapper.main()
        self.assertTrue(new_dir.exists())

    def test_process_queue_missing_file(self):
        downloaded, failed = wrapper.process_queue("missing.md", "out")
        self.assertEqual(downloaded, [])
        self.assertEqual(failed, [])

    @patch('subprocess.Popen')
    def test_download_video_success(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = []
        mock_popen.return_value = mock_process

        result = wrapper.download_video("https://link.com", "out")
        self.assertTrue(result)
        mock_popen.assert_called()

    @patch('subprocess.Popen')
    def test_download_video_failure(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = []
        mock_popen.return_value = mock_process

        result = wrapper.download_video("https://link.com", "out")
        self.assertFalse(result)

    def test_process_queue(self):
        content = """# Queue
## Not downloaded yet
- https://link1.com
- https://link2.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        # Mock download_video within the wrapper module
        with patch.object(wrapper, 'download_video') as mock_download:
            # Success for link1, failure for link2
            mock_download.side_effect = [True, False]

            downloaded, failed = wrapper.process_queue(self.md_file, "out")

            self.assertEqual(downloaded, ["https://link1.com"])
            self.assertEqual(failed, ["https://link2.com"])

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        self.assertIn('## Downloaded\n- https://link1.com\n', new_content)
        self.assertIn('## Failed\n- https://link2.com\n', new_content)


if __name__ == '__main__':
    unittest.main()
