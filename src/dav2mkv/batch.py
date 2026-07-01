"""Batch directory conversion with parallel processing."""

import multiprocessing
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from dav2mkv.converter import VideoConverter
from dav2mkv.types import BatchResults


class BatchConverter:
    """Batch video converter with parallel processing support."""

    def __init__(
        self, converter: VideoConverter, max_workers: int | None = None
    ) -> None:
        self.converter = converter
        self.logger = converter.logger
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() - 1)

        self.video_extensions = {
            ".dav",
            ".avi",
            ".mp4",
            ".mkv",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".m4v",
            ".3gp",
            ".3g2",
            ".asf",
            ".rm",
            ".rmvb",
            ".vob",
            ".ts",
        }

    def find_video_files(
        self, directory: str | Path, recursive: bool = False
    ) -> list[Path]:
        """
        Find all video files in a directory.

        Args:
            directory: Directory to search
            recursive: Whether to search recursively

        Returns:
            List of video file paths
        """
        directory_path = Path(directory)

        if not directory_path.exists():
            self.logger.error("Directory does not exist: %s", directory_path)
            return []

        if not directory_path.is_dir():
            self.logger.error("Path is not a directory: %s", directory_path)
            return []

        video_files: list[Path] = []

        try:
            if recursive:
                files = directory_path.rglob("*")
            else:
                files = directory_path.iterdir()

            for file_path in files:
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in self.video_extensions
                ):
                    video_files.append(file_path)
                    self.logger.debug("Found video file: %s", file_path)

            self.logger.info(
                "Found %s video files in %s", len(video_files), directory_path
            )
            return sorted(video_files)

        except OSError as exc:
            self.logger.error("Error scanning directory %s: %s", directory_path, exc)
            return []

    def _output_path_for_file(
        self,
        video_file: Path,
        input_dir: Path,
        output_dir: Path,
        container: str,
    ) -> Path:
        """Compute the output path for a video file in batch mode."""
        if output_dir != input_dir:
            relative_path = video_file.relative_to(input_dir)
            return output_dir / relative_path.with_suffix(f".{container}")
        return video_file.with_suffix(f".{container}")

    def _collect_batch_results(
        self,
        future_to_file: dict[Future[bool], Path],
        total_files: int,
    ) -> BatchResults:
        """Collect results from submitted batch conversion futures."""
        results: BatchResults = {
            "total": total_files,
            "successful": 0,
            "failed": 0,
        }
        completed = 0

        for future in as_completed(future_to_file):
            video_file = future_to_file[future]
            completed += 1

            try:
                success = future.result(timeout=3700)
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1

                self.logger.info(
                    "Progress: %s/%s files processed (%s successful, %s failed)",
                    completed,
                    total_files,
                    results["successful"],
                    results["failed"],
                )

            except OSError as exc:
                results["failed"] += 1
                self.logger.error("Conversion exception for %s: %s", video_file, exc)

        return results

    def convert_directory(
        self,
        input_dir: str | Path,
        output_dir: str | Path | None = None,
        container: str = "mkv",
        recursive: bool = False,
        overwrite: bool = True,
    ) -> BatchResults:
        """
        Convert all video files in a directory.

        Args:
            input_dir: Input directory path
            output_dir: Output directory path (optional)
            container: Output container format
            recursive: Whether to search recursively
            overwrite: Whether to overwrite existing files

        Returns:
            Dictionary with conversion statistics
        """
        input_path = Path(input_dir)

        if output_dir:
            resolved_output_dir = Path(output_dir)
            resolved_output_dir.mkdir(parents=True, exist_ok=True)
        else:
            resolved_output_dir = input_path

        self.logger.info(
            "Starting batch conversion: %s -> %s", input_path, resolved_output_dir
        )
        self.logger.info("Container: %s, Workers: %s", container, self.max_workers)

        video_files = self.find_video_files(input_path, recursive=recursive)

        if not video_files:
            self.logger.warning("No video files found to convert")
            return {"total": 0, "successful": 0, "failed": 0}

        self.logger.info(
            "Processing %s files with %s workers",
            len(video_files),
            self.max_workers,
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file: dict[Future[bool], Path] = {}

            for video_file in video_files:
                output_file = self._output_path_for_file(
                    video_file, input_path, resolved_output_dir, container
                )
                future = executor.submit(
                    self.converter.convert_video,
                    video_file,
                    output_file,
                    container,
                    overwrite,
                )
                future_to_file[future] = video_file

            results = self._collect_batch_results(future_to_file, len(video_files))

        self.logger.info("Batch conversion completed: %s", results)
        return results
