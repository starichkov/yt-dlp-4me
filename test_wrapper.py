import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from pathlib import Path

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
            downloaded, failed, skipped = wrapper.process_queue(self.md_file, "out")

            self.assertEqual(downloaded, [])
            self.assertEqual(failed, [])
            self.assertEqual(skipped, [])

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
            wrapper.print_summary(["link1"], ["link2"], ["link3"])
            # Just verify it doesn't crash and prints something
            self.assertTrue(mock_stdout.write.called)

    @patch('subprocess.Popen')
    def test_download_video_exception(self, mock_popen):
        mock_popen.side_effect = Exception("Failed to start")
        success, already_exists = wrapper.download_video("https://link.com", "out")
        self.assertFalse(success)
        self.assertFalse(already_exists)

    @patch('subprocess.Popen')
    def test_download_video_with_output(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ["line 1\n", "line 2\n"]
        mock_popen.return_value = mock_process

        success, already_exists = wrapper.download_video("https://link.com", "out")
        self.assertTrue(success)
        self.assertFalse(already_exists)

    def test_main_success(self):
        # Patch the wrapper object directly
        with patch.object(wrapper, 'process_queue', return_value=([], [], [])):
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
        with patch.object(wrapper, 'process_queue', return_value=([], [], [])):
            with patch.object(wrapper, 'print_summary'):
                with patch('sys.argv', ['yt_dlp_wrapper.py', str(self.md_file), str(new_dir)]):
                    wrapper.main()
        self.assertTrue(new_dir.exists())

    def test_main_verify(self):
        with open(self.md_file, 'w') as f:
            f.write("## Downloaded\n")
        with patch.object(wrapper, 'cleanup_markdown') as mock_cleanup:
            with patch.object(wrapper, 'process_queue', return_value=([], [], [])):
                with patch.object(wrapper, 'print_summary'):
                    with patch('sys.argv', ['yt_dlp_wrapper.py', str(self.md_file), str(self.test_dir), '--verify']):
                        wrapper.main()
                        self.assertTrue(mock_cleanup.called)

    def test_process_queue_missing_file(self):
        downloaded, failed, skipped = wrapper.process_queue("missing.md", "out")
        self.assertEqual(downloaded, [])
        self.assertEqual(failed, [])
        self.assertEqual(skipped, [])

    @patch('subprocess.Popen')
    def test_download_video_success(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = []
        mock_popen.return_value = mock_process

        success, already_exists = wrapper.download_video("https://link.com", "out")
        self.assertTrue(success)
        self.assertFalse(already_exists)
        mock_popen.assert_called()

    @patch('subprocess.Popen')
    def test_download_video_failure(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = []
        mock_popen.return_value = mock_process

        success, already_exists = wrapper.download_video("https://link.com", "out")
        self.assertFalse(success)
        self.assertFalse(already_exists)

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
            # Success for link1 (new), failure for link2
            mock_download.side_effect = [(True, False), (False, False)]

            downloaded, failed, skipped = wrapper.process_queue(self.md_file, "out")

            self.assertEqual(downloaded, ["https://link1.com"])
            self.assertEqual(failed, ["https://link2.com"])
            self.assertEqual(skipped, [])

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        self.assertIn('## Downloaded\n- https://link1.com\n', new_content)
        self.assertIn('## Failed\n- https://link2.com\n', new_content)


    def test_move_link_to_section_append_with_blank_lines(self):
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

        # Should be inserted right after existing items, before the blank line
        expected = "# Videos\n## Downloaded\n- https://link-existing.com\n- https://link1.com\n\n## Not downloaded yet\n"
        self.assertEqual(new_content, expected)

    def test_move_link_to_section_with_l3_header(self):
        content = """# Videos
## Downloaded
### Subheader
- https://link-old.com
## Not downloaded yet
- https://link-new.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        wrapper.move_link_to_section(self.md_file, "https://link-new.com", 'Downloaded', '## Downloaded')

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        # Should be inserted at the end of the Downloaded section (after link-old)
        self.assertIn("### Subheader\n- https://link-old.com\n- https://link-new.com\n", new_content)

    def test_parse_markdown_read_error(self):
        self.md_file.touch()
        with patch.object(Path, 'read_text', side_effect=Exception("Read error")):
            # Should return empty list and print error
            self.assertEqual(wrapper.parse_markdown(self.md_file), [])

    def test_move_link_to_section_no_file(self):
        # Line 93: if not section_map: return
        wrapper.move_link_to_section("non_existent.md", "https://link.com", "Downloaded", "## Downloaded")
        # Should just return without error

    def test_move_link_to_section_link_not_found(self):
        # Line 103: if found_idx == -1: return
        content = "## Not downloaded yet\n- https://other.com\n"
        with open(self.md_file, 'w') as f:
            f.write(content)
        wrapper.move_link_to_section(self.md_file, "https://missing.com", "Downloaded", "## Downloaded")
        # File should remain unchanged
        with open(self.md_file, 'r') as f:
            self.assertEqual(f.read(), content)

    def test_process_queue_verify(self):
        content = """# Queue
## Downloaded
- https://link1.com
- https://link2.com
- https://link3.com
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        with patch.object(wrapper, 'download_video') as mock_download:
            # 1: already exists, 2: re-downloaded, 3: failed
            mock_download.side_effect = [(True, True), (True, False), (False, False)]

            downloaded, failed, skipped = wrapper.process_queue(self.md_file, "out", verify=True)

            self.assertEqual(downloaded, ["https://link2.com"])
            self.assertEqual(failed, ["https://link3.com"])
            self.assertEqual(skipped, ["https://link1.com"])

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        # link3 should be in Failed section
        self.assertIn('## Failed\n- https://link3.com\n', new_content)
        # link1 and link2 should still be in Downloaded
        self.assertIn('## Downloaded\n- https://link1.com\n- https://link2.com\n', new_content)

    def test_move_link_to_section_from_downloaded(self):
        content = """## Downloaded
- https://link1.com
## Failed
"""
        with open(self.md_file, 'w') as f:
            f.write(content)

        wrapper.move_link_to_section(
            self.md_file, 
            "https://link1.com", 
            'Failed', 
            '## Failed', 
            source_section_label='Downloaded'
        )

        with open(self.md_file, 'r') as f:
            new_content = f.read()

        self.assertIn('## Failed\n- https://link1.com\n', new_content)
        self.assertNotIn('## Downloaded\n- https://link1.com\n', new_content)

    @patch('subprocess.Popen')
    def test_download_video_already_exists(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ["has already been downloaded\n"]
        mock_popen.return_value = mock_process

        success, already_exists = wrapper.download_video("https://link.com", "out")
        self.assertTrue(success)
        self.assertTrue(already_exists)

    def test_parse_markdown_h1_headers(self):
        content = """# Downloaded
- https://link1.com
# Not downloaded yet
- https://link2.com
"""
        self.md_file.write_text(content, encoding='utf-8')
        section_map = wrapper.parse_markdown(self.md_file)
        self.assertEqual(section_map[0][0], 'Downloaded')
        self.assertEqual(section_map[2][0], 'Not downloaded yet')

    def test_parse_markdown_case_insensitive(self):
        content = """## downloaded
- https://link1.com
## NOT DOWNLOADED YET
- https://link2.com
"""
        self.md_file.write_text(content, encoding='utf-8')
        section_map = wrapper.parse_markdown(self.md_file)
        self.assertEqual(section_map[0][0], 'Downloaded')
        self.assertEqual(section_map[2][0], 'Not downloaded yet')

    def test_parse_markdown_no_space_after_hash(self):
        content = """##Downloaded
- https://link1.com
"""
        self.md_file.write_text(content, encoding='utf-8')
        section_map = wrapper.parse_markdown(self.md_file)
        self.assertEqual(section_map[0][0], 'Downloaded')

    def test_move_link_to_h1_header(self):
        content = """# Downloaded
- https://link-existing.com
# Not downloaded yet
- https://link-new.com
"""
        self.md_file.write_text(content, encoding='utf-8')
        wrapper.move_link_to_section(self.md_file, "https://link-new.com", 'Downloaded', '## Downloaded')
        
        new_content = self.md_file.read_text()
        self.assertIn('# Downloaded\n- https://link-existing.com\n- https://link-new.com\n', new_content)
        self.assertNotIn('## Downloaded', new_content)

    @patch('subprocess.Popen')
    def test_download_video_command_args(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = []
        mock_popen.return_value = mock_process

        wrapper.download_video("https://link.com", "out")
        
        args, _ = mock_popen.call_args
        cmd = args[0]
        self.assertTrue(any("yt-dlp" in arg for arg in cmd))
        self.assertIn("-P", cmd)
        self.assertIn("out", cmd)
        self.assertNotIn("-o", cmd)

    @patch('subprocess.Popen')
    def test_download_video_custom_path(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = []
        mock_popen.return_value = mock_process

        custom_path = "/path/to/my-yt-dlp"
        wrapper.download_video("https://link.com", "out", yt_dlp_path=custom_path)
        
        args, _ = mock_popen.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], custom_path)

    def test_default_yt_dlp_path(self):
        self.assertIn('yt-dlp_linux', wrapper.DEFAULT_YT_DLP_PATH)
        self.assertIn('bin', wrapper.DEFAULT_YT_DLP_PATH)

    def test_path_expansion(self):
        # We can test if expanduser is called by mocking it
        with patch.object(Path, 'expanduser') as mock_expand:
            # When patched on the class, expanduser might be called without args if not bound
            mock_expand.side_effect = lambda: Path("expanded")
            
            wrapper.parse_markdown("~/test.md")
            self.assertTrue(mock_expand.called)
            
            mock_expand.reset_mock()
            wrapper.save_markdown("~/test.md", [])
            self.assertTrue(mock_expand.called)
            
            mock_expand.reset_mock()
            with patch('subprocess.Popen'):
                wrapper.download_video("http://link", "~/out", yt_dlp_path="~/yt")
                # Should be called for both output_dir and yt_dlp_path
                self.assertGreaterEqual(mock_expand.call_count, 2)
            
            mock_expand.reset_mock()
            wrapper.move_link_to_section("~/test.md", "link", "sec", "hdr")
            self.assertTrue(mock_expand.called)

    def test_cleanup_markdown(self):
        content = """# Title
## Downloaded
- https://link1.com
- https://link1.com
## Not downloaded yet
- https://link1.com
- https://link2.com
- https://link2.com
## Failed
- https://link2.com
- https://link3.com
"""
        self.md_file.write_text(content, encoding='utf-8')
        wrapper.cleanup_markdown(self.md_file)
        
        new_content = self.md_file.read_text(encoding='utf-8')
        
        # link1 should be ONLY in Downloaded (one occurrence)
        self.assertIn("## Downloaded\n- https://link1.com\n", new_content)
        self.assertEqual(new_content.count("https://link1.com"), 1)
        
        # link2 should be ONLY in Failed (one occurrence)
        self.assertIn("## Failed\n- https://link2.com\n", new_content)
        self.assertEqual(new_content.count("https://link2.com"), 1)
        
        # link3 should be in Failed
        self.assertIn("- https://link3.com\n", new_content)
        
        # Not downloaded yet should be empty of these links
        # (It might still have the header)
        self.assertIn("## Not downloaded yet\n##", new_content)

    def test_cleanup_markdown_edge_cases(self):
        # Empty file
        self.md_file.write_text("", encoding='utf-8')
        wrapper.cleanup_markdown(self.md_file)  # Should not crash

        # Duplicate in Failed, and link in Downloaded also in Failed
        content = """## Downloaded
- https://link1.com
## Failed
- https://link1.com
- https://link2.com
- https://link2.com
"""
        self.md_file.write_text(content, encoding='utf-8')
        wrapper.cleanup_markdown(self.md_file)
        new_content = self.md_file.read_text(encoding='utf-8')
        # link1 should be removed from Failed
        # link2 should have only one occurrence in Failed
        self.assertIn("## Downloaded\n- https://link1.com\n", new_content)
        self.assertIn("## Failed\n- https://link2.com\n", new_content)
        self.assertNotIn("## Failed\n- https://link1.com", new_content)
        self.assertEqual(new_content.count("https://link2.com"), 1)

if __name__ == '__main__':
    unittest.main()
