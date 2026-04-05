#!/usr/bin/env node

/**
 * Markdown to PPT/PDF Converter
 *
 * A tool to convert markdown files to PowerPoint or PDF presentations
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class MarkdownToPresentationConverter {
  constructor() {
    this.supportedFormats = ['pptx', 'pdf', 'html'];
  }

  /**
   * Check if required tools are installed
   */
  checkDependencies() {
    const dependencies = [
      { name: 'pandoc', checkCmd: 'pandoc --version' },
      { name: 'node', checkCmd: 'node --version' }
    ];

    // Check LaTeX for PDF support
    if (this.supportedFormats.includes('pdf')) {
      dependencies.push({ name: 'latex', checkCmd: 'pdflatex --version' });
    }

    const missing = [];
    for (const dep of dependencies) {
      try {
        execSync(dep.checkCmd, { stdio: 'pipe' });
      } catch (error) {
        missing.push(dep.name);
      }
    }

    if (missing.length > 0) {
      throw new Error(`Missing dependencies: ${missing.join(', ')}`);
    }

    return true;
  }

  /**
   * Convert markdown to specified format
   * @param {string} inputFile - Path to input markdown file
   * @param {string} outputFile - Path to output file
   * @param {string} format - Output format ('pptx', 'pdf', 'html')
   * @param {Object} options - Additional options
   */
  convert(inputFile, outputFile, format, options = {}) {
    if (!this.supportedFormats.includes(format)) {
      throw new Error(`Unsupported format: ${format}. Supported formats: ${this.supportedFormats.join(', ')}`);
    }

    if (!fs.existsSync(inputFile)) {
      throw new Error(`Input file does not exist: ${inputFile}`);
    }

    // Ensure output directory exists
    const outputDir = path.dirname(outputFile);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    let cmd;

    switch (format) {
      case 'pptx':
        cmd = `pandoc "${inputFile}" -o "${outputFile}"`;
        break;

      case 'pdf':
        // If latex is not available, convert to HTML first then to PDF using headless Chrome
        try {
          execSync('pdflatex --version', { stdio: 'pipe' });
          cmd = `pandoc "${inputFile}" -o "${outputFile}"`;
        } catch (e) {
          console.warn('LaTeX not found. Converting to HTML first, then to PDF requires additional processing.');
          const tempHtml = outputFile.replace('.pdf', '_temp.html');
          cmd = `pandoc "${inputFile}" -o "${tempHtml}"`;
          // Note: actual PDF conversion would require additional tools like puppeteer
        }
        break;

      case 'html':
        if (options.presentation) {
          // Create reveal.js presentation
          let themeOption = '-V theme=black'; // 默认主题

          // 如果指定了主题CSS文件，则应用自定义样式
          if (options.theme) {
            const themePath = path.resolve(__dirname, 'themes', `${options.theme}.css`);
            if (fs.existsSync(themePath)) {
              // 使用自定义CSS文件
              cmd = `pandoc "${inputFile}" -t revealjs -s -o "${outputFile}" -V revealjs-url=https://unpkg.com/reveal.js@4.3.1/ --css="${themePath}"`;
            } else {
              // 如果主题不存在，使用reveal.js内置主题
              themeOption = `-V theme=${options.theme}`;
              cmd = `pandoc "${inputFile}" -t revealjs -s -o "${outputFile}" -V revealjs-url=https://unpkg.com/reveal.js@4.3.1/ ${themeOption}`;
            }
          } else {
            cmd = `pandoc "${inputFile}" -t revealjs -s -o "${outputFile}" -V revealjs-url=https://unpkg.com/reveal.js@4.3.1/ ${themeOption}`;
          }
        } else {
          cmd = `pandoc "${inputFile}" -o "${outputFile}"`;
        }
        break;

      default:
        throw new Error(`Unsupported format: ${format}`);
    }

    // Add any additional options to the command
    if (options.template) {
      cmd += ` --reference-doc="${options.template}"`;
    }

    if (options.css && !options.presentation) { // 仅对非presentation HTML应用CSS
      cmd += ` --css="${options.css}"`;
    }

    console.log(`Executing: ${cmd}`);

    try {
      execSync(cmd, { stdio: 'inherit' });
      console.log(`Successfully converted ${inputFile} to ${outputFile}`);
      return true;
    } catch (error) {
      console.error(`Conversion failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Batch convert markdown files to multiple formats
   * @param {string} inputFile - Path to input markdown file
   * @param {Array} formats - Array of formats to convert to
   * @param {Object} options - Additional options
   */
  batchConvert(inputFile, formats, options = {}) {
    const results = {};

    for (const format of formats) {
      const ext = format === 'pptx' ? 'pptx' : format === 'pdf' ? 'pdf' : 'html';
      const outputFileName = path.basename(inputFile, path.extname(inputFile)) + '.' + ext;
      const outputFilePath = path.resolve(path.dirname(inputFile), outputFileName);

      results[format] = this.convert(inputFile, outputFilePath, format, options);
    }

    return results;
  }
}

// Command line interface
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length < 3) {
    console.log(`
Usage: node converter.js <input.md> <output> <format> [options]

Examples:
  node converter.js presentation.md output.pptx pptx
  node converter.js presentation.md output.pdf pdf
  node converter.js presentation.md slides.html html --presentation

Options:
  --presentation  Create HTML presentation using reveal.js
  --template FILE Use specified template file
    `);
    process.exit(1);
  }

  const inputFile = args[0];
  const outputFile = args[1];
  const format = args[2];
  const options = {};

  // Parse additional options
  for (let i = 3; i < args.length; i++) {
    if (args[i] === '--presentation') {
      options.presentation = true;
    } else if (args[i] === '--template' && i + 1 < args.length) {
      options.template = args[i + 1];
      i++; // Skip next argument as it's the template value
    }
  }

  try {
    const converter = new MarkdownToPresentationConverter();
    converter.checkDependencies();
    converter.convert(inputFile, outputFile, format, options);
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

module.exports = MarkdownToPresentationConverter;