"""Command-line interface for the DAV video converter."""

import argparse
import logging
import multiprocessing
import platform
import sys
from pathlib import Path

from dav2mkv import __version__
from dav2mkv.batch import BatchConverter
from dav2mkv.converter import VideoConverter
from dav2mkv.exceptions import DAVConverterError, FFmpegNotFoundError
from dav2mkv.log_config import setup_logging
from dav2mkv.probe import check_ffmpeg_availability
from dav2mkv.types import (
    BatchResults,
    CliArgs,
    CliLoggingOptions,
    CliProcessingOptions,
)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert video files using direct stream copy for maximum quality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f input.dav -o output.mkv
  %(prog)s -d ./videos -o ./out --container mp4 --recursive
  %(prog)s input.dav output_folder --container mp4
  %(prog)s -f video.avi --log-level DEBUG --log-file conversion.log
        """,
    )

    parser.add_argument(
        "positional",
        nargs="*",
        metavar="PATH",
        help="Optional positional: input path [output folder] (alternative to -f/-d)",
    )

    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument("-f", "--file", help="Single video file to convert")
    input_group.add_argument(
        "-d", "--directory", help="Directory containing video files to convert"
    )

    parser.add_argument("-o", "--output", help="Output file or directory name")

    parser.add_argument(
        "--container",
        choices=("mkv", "mp4"),
        default="mkv",
        help="Output container format (default: mkv)",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=True,
        help="Overwrite existing output files (default: True)",
    )

    parser.add_argument(
        "--no-overwrite",
        action="store_false",
        dest="overwrite",
        help="Do not overwrite existing output files",
    )

    parser.add_argument(
        "-c",
        "--concurrent",
        type=int,
        help="Maximum number of concurrent conversions for directory processing",
    )

    parser.add_argument(
        "--recursive", action="store_true", help="Process directories recursively"
    )

    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    parser.add_argument("--log-file", help="Log file path (optional)")

    parser.add_argument(
        "--version",
        action="version",
        version=f"DAV Video Converter {__version__}",
    )

    return parser


def _namespace_members(namespace: argparse.Namespace) -> dict[str, object]:
    """Extract namespace members as a typed string-to-object mapping."""
    members: object = vars(namespace)
    if not isinstance(members, dict):
        raise TypeError("argparse namespace must provide a dict of attributes")
    typed_members: dict[str, object] = {}
    for key_obj, value_obj in members.items():
        if isinstance(key_obj, str):
            typed_members[key_obj] = value_obj
    return typed_members


def _namespace_to_cli_args(namespace: argparse.Namespace) -> CliArgs:
    """Convert argparse namespace to a typed CliArgs instance."""
    members = _namespace_members(namespace)

    file_value: object = members.get("file")
    directory_value: object = members.get("directory")
    output_value: object = members.get("output")
    concurrent_value: object = members.get("concurrent")
    log_file_value: object = members.get("log_file")
    container_value: object = members.get("container", "mkv")
    overwrite_value: object = members.get("overwrite", True)
    recursive_value: object = members.get("recursive", False)
    log_level_value: object = members.get("log_level", "INFO")

    return CliArgs(
        file=file_value if isinstance(file_value, str) else None,
        directory=directory_value if isinstance(directory_value, str) else None,
        output=output_value if isinstance(output_value, str) else None,
        container=container_value if isinstance(container_value, str) else "mkv",
        overwrite=bool(overwrite_value),
        processing=CliProcessingOptions(
            concurrent=concurrent_value if isinstance(concurrent_value, int) else None,
            recursive=bool(recursive_value),
        ),
        logging=CliLoggingOptions(
            log_level=log_level_value if isinstance(log_level_value, str) else "INFO",
            log_file=log_file_value if isinstance(log_file_value, str) else None,
        ),
    )


def resolve_input_arguments(
    parser: argparse.ArgumentParser, namespace: argparse.Namespace
) -> CliArgs:
    """Resolve positional input paths when -f/-d flags are not used."""
    args = _namespace_to_cli_args(namespace)
    members = _namespace_members(namespace)
    positional_value: object = members.get("positional")

    if args.file or args.directory:
        if isinstance(positional_value, list) and positional_value:
            parser.error(
                "Cannot combine positional paths with -f/--file or -d/--directory"
            )
        return args

    if not isinstance(positional_value, list) or not positional_value:
        parser.error(
            "An input path is required: use -f/--file, -d/--directory, "
            "or provide a positional path"
        )

    if len(positional_value) > 2:
        parser.error("Too many positional arguments (expected: input [output])")
    if len(positional_value) > 1 and args.output:
        parser.error("Cannot specify both positional output and -o/--output")

    input_path = Path(str(positional_value[0]))
    if len(positional_value) > 1:
        args.output = str(positional_value[1])

    if input_path.is_dir():
        args.directory = str(input_path)
    else:
        args.file = str(input_path)

    return args


def _log_system_info(logger: logging.Logger) -> None:
    """Log system and runtime information."""
    logger.info("=== DAV Video Converter Starting ===")
    logger.info("Python version: %s", sys.version)
    logger.info("Platform: %s %s", platform.system(), platform.release())
    logger.info("Architecture: %s", platform.machine())
    logger.info("CPU count: %s", multiprocessing.cpu_count())


def _run_single_file_mode(converter: VideoConverter, args: CliArgs) -> int:
    """Run single-file conversion mode."""
    if args.file is None:
        return 1

    logger = converter.logger
    logger.info("Converting single file: %s", args.file)
    success = converter.convert_video(
        input_file=args.file,
        output_file=args.output,
        container=args.container,
        overwrite=args.overwrite,
    )

    stats = converter.get_stats()
    logger.info("Conversion stats: %s", stats)
    return 0 if success else 1


def _compute_batch_exit_code(results: BatchResults, logger: logging.Logger) -> int:
    """Compute exit code from batch conversion results."""
    if results["failed"] == 0:
        logger.info("All conversions completed successfully")
        return 0
    if results["successful"] > 0:
        logger.warning(
            "Partial success: %s succeeded, %s failed",
            results["successful"],
            results["failed"],
        )
        return 2
    logger.error("All conversions failed")
    return 1


def _run_batch_mode(converter: VideoConverter, args: CliArgs) -> int:
    """Run directory batch conversion mode."""
    if args.directory is None:
        return 1

    logger = converter.logger
    max_workers = args.processing.concurrent
    if max_workers is not None and max_workers > 0:
        logger.info("Using %s worker threads", max_workers)

    batch_converter = BatchConverter(converter, max_workers)

    results = batch_converter.convert_directory(
        input_dir=args.directory,
        output_dir=args.output,
        container=args.container,
        recursive=args.processing.recursive,
        overwrite=args.overwrite,
    )

    converter_stats = converter.get_stats()
    logger.info("Final results: %s", results)
    logger.info("Converter stats: %s", converter_stats)

    return _compute_batch_exit_code(results, logger)


def main() -> int:
    """Main application entry point."""
    parser = create_argument_parser()
    args = resolve_input_arguments(parser, parser.parse_args())

    logger = setup_logging(args.logging.log_level, args.logging.log_file)
    exit_code = 1

    try:
        _log_system_info(logger)

        ffmpeg_available, ffmpeg_version = check_ffmpeg_availability()
        if not ffmpeg_available:
            logger.critical(
                "FFmpeg is not available. Please install FFmpeg and ensure "
                "it's in your PATH."
            )
            raise FFmpegNotFoundError("FFmpeg not found in system PATH")

        logger.info("Using %s", ffmpeg_version)

        converter = VideoConverter(logger)

        if args.file:
            exit_code = _run_single_file_mode(converter, args)
        else:
            exit_code = _run_batch_mode(converter, args)

    except KeyboardInterrupt:
        logger.warning("Conversion interrupted by user")
        exit_code = 130
    except FFmpegNotFoundError:
        exit_code = 127
    except (OSError, DAVConverterError) as exc:
        logger.critical("Unexpected error: %s", exc, exc_info=True)
        exit_code = 1
    finally:
        logger.info("=== DAV Video Converter Finished ===")

    return exit_code
