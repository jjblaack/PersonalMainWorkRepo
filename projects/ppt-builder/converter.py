#!/usr/bin/env python3
"""
Markdown to PPT/PDF Converter

A Python tool to convert markdown files to PowerPoint or PDF presentations
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


class MarkdownToPresentationConverter:
    def __init__(self):
        self.supported_formats = ['pptx', 'pdf', 'html']

    def check_dependencies(self):
        """Check if required tools are installed"""
        dependencies = [
            {'name': 'pandoc', 'cmd': ['pandoc', '--version']},
        ]

        # Check if LaTeX is available for PDF support
        if 'pdf' in self.supported_formats:
            dependencies.append({'name': 'latex', 'cmd': ['pdflatex', '--version']})

        missing = []
        for dep in dependencies:
            try:
                subprocess.run(dep['cmd'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing.append(dep['name'])

        if missing:
            raise Exception(f"Missing dependencies: {', '.join(missing)}")

        return True

    def convert(self, input_file, output_file, format, options=None):
        """Convert markdown to specified format"""
        if options is None:
            options = {}

        if format not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format}. Supported formats: {', '.join(self.supported_formats)}")

        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file does not exist: {input_file}")

        # Ensure output directory exists
        output_dir = Path(output_file).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = []

        if format == 'pptx':
            cmd = ['pandoc', input_file, '-o', output_file]
        elif format == 'pdf':
            # Check if LaTeX is available
            try:
                subprocess.run(['pdflatex', '--version'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cmd = ['pandoc', input_file, '-o', output_file]
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("Warning: LaTeX not found. Converting to HTML first, then to PDF requires additional processing.")
                temp_html = output_file.replace('.pdf', '_temp.html')
                cmd = ['pandoc', input_file, '-o', temp_html]
                # Note: actual PDF conversion would require additional tools like weasyprint
        elif format == 'html':
            if options.get('presentation'):
                # Create reveal.js presentation
                if options.get('theme'):
                    theme_path = Path(__file__).parent / 'themes' / f"{options['theme']}.css"
                    if theme_path.exists():
                        # Use custom CSS file
                        cmd = [
                            'pandoc', input_file,
                            '-t', 'revealjs',
                            '-s',
                            '-o', output_file,
                            '-V', 'revealjs-url=https://unpkg.com/reveal.js@4.3.1/',
                            '--css', str(theme_path)
                        ]
                    else:
                        # If theme doesn't exist as a CSS file, try it as a reveal.js theme
                        cmd = [
                            'pandoc', input_file,
                            '-t', 'revealjs',
                            '-s',
                            '-o', output_file,
                            '-V', 'revealjs-url=https://unpkg.com/reveal.js@4.3.1/',
                            f"-V", f"theme={options['theme']}"
                        ]
                else:
                    cmd = [
                        'pandoc', input_file,
                        '-t', 'revealjs',
                        '-s',
                        '-o', output_file,
                        '-V', 'revealjs-url=https://unpkg.com/reveal.js@4.3.1/',
                        '-V', 'theme=black'
                    ]
            else:
                cmd = ['pandoc', input_file, '-o', output_file]

        # Add template if specified
        if options.get('template'):
            cmd.extend(['--reference-doc', options['template']])

        # Add CSS if specified (only for non-presentation HTML)
        if options.get('css') and not options.get('presentation'):
            cmd.extend(['--css', options['css']])

        print(f"Executing: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, check=True)
            print(f"Successfully converted {input_file} to {output_file}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Conversion failed: {e}")
            return False

    def batch_convert(self, input_file, formats, options=None):
        """Batch convert markdown files to multiple formats"""
        if options is None:
            options = {}

        results = {}

        for format in formats:
            ext = format if format in ['pptx', 'pdf'] else 'html'
            output_filename = Path(input_file).stem + '.' + ext
            output_filepath = Path(input_file).parent / output_filename

            results[format] = self.convert(input_file, str(output_filepath), format, options)

        return results


def main():
    parser = argparse.ArgumentParser(description='Convert markdown files to PowerPoint or PDF presentations')
    parser.add_argument('input', help='Input markdown file')
    parser.add_argument('output', help='Output file path')
    parser.add_argument('format', choices=['pptx', 'pdf', 'html'], help='Output format')
    parser.add_argument('--presentation', action='store_true', help='Create HTML presentation using reveal.js')
    parser.add_argument('--template', help='Use specified template file')

    args = parser.parse_args()

    try:
        converter = MarkdownToPresentationConverter()
        converter.check_dependencies()

        options = {
            'presentation': args.presentation,
            'template': args.template
        }

        converter.convert(args.input, args.output, args.format, options)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()