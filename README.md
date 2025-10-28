# Coursemology Submission Uploader

A Python tool to automatically download, extract, and upload student submissions to Coursemology. This tool streamlines the workflow of managing programming assignments by automating the process of collecting student work from various sources and submitting them to the Coursemology learning management system.

## Features

- **Batch Download**: Scrape and download submission files from protected directory indexes
- **Automatic Extraction**: Extract downloaded ZIP archives
- **CSV-based Mapping**: Map filenames to student identities (name and email) using CSV files
- **Flexible File Matching**: Map files to specific assessment questions by filename
- **Coursemology Integration**: Automatically submit programming answers to assessments
- **Progress Tracking**: Visual progress bars for batch operations
- **Error Handling**: Comprehensive error handling and logging

## Installation

### From Source

Download or clone from GitHub and install:

```bash
cd coursemology-submission-uploader
pip install -e .
```

### Dependencies

- Python >= 3.13
- requests >= 2.32.5
- beautifulsoup4 >= 4.14.2
- coursemology-py
- click >= 8.3.0
- pyyaml >= 6.0.3
- tqdm >= 4.67.1

## Usage

### Command Line

```bash
coursemology_uploader <config_file.yaml>
```

### Configuration File

Create a YAML configuration file with the following structure:

```yaml
# Base directory containing extracted student files
base_dir: pe

# Glob pattern to locate student submission files
file_pattern: "**/*.py"

# Path to save submission report
report_path: pe_submission_report.yaml

# CSV mapping configuration
fname_user_map:
  csv: plab-mapping.csv      # Path to CSV file
  key: plab ID               # Column name for lookup key
  name: Name                 # Column name for student name
  email: Email               # Column name for student email

# Map filenames to Coursemology question titles
file_question_map:
  "PE_1A.py": "Question 1A: Encoding"
  "PE_1B.py": "Question 1B: Decoding"
  "PE_2A.py": "Question 2A: eval_simple_bae"
  "PE_2B.py": "Question 2B: eval_bae"
  "PE_3.py": "Question 3: Hops"
  "PE_4.py": "Question 4: Deep Seek"

# Coursemology credentials and assessment info
coursemology:
  username: your-username
  password: your-password
  course_id: 1111
  assessment_category: PE
  assessment_title: Practical Exam

# Optional: Batch download configuration
batch_download:
  base_url: "https://data.example.com/submissions/"
  basic_auth:
    username: your-auth-username
    password: your-auth-password
  filter_pattern: PE  # Regex to filter files
  destination: downloads
```

### Example Configuration Files

Example configuration files are available in the `examples/` directory:
- `examples/config.yaml` - Template with placeholders

## Workflow

The tool follows this workflow:

1. **Download** (if `batch_download` configured):
   - Scrape directory index at `base_url`
   - Filter files matching `filter_pattern`
   - Download matched files to `destination`

2. **Extract**:
   - Automatically extract downloaded ZIP files
   - Organize extracted files in the specified `base_dir`

3. **Map**:
   - Load CSV mapping file to associate filenames with student identities
   - Match files using `file_pattern` glob
   - Map files to assessment questions using `file_question_map` by filename

4. **Upload**:
   - Authenticate with Coursemology
   - Find or create student submissions
   - Upload programming files to the correct assessment questions
   - Submit the assessments

## CSV Mapping File

The CSV file should contain at minimum the columns specified in `fname_user_map`:

```csv
plab ID,Name,Email
plab1001,John Doe,john.doe@example.com
plab1002,Jane Smith,jane.smith@example.com
```

## File Question Mapping

The `file_question_map` maps exact filenames to question titles as they appear in Coursemology:

```yaml
file_question_map:
  "PE_1A.py": "Question 1A: Encoding"
  "PE_1B.py": "Question 1B: Decoding"
  "PE_2A.py": "Question 2A: eval_simple_bae"
```

Note: The filenames should match exactly (case-sensitive), and the question titles must match those in the Coursemology assessment.

## Development

### Setting Up Development Environment

```bash
# Clone and install in editable mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

This installs type stubs for PyYAML for better type checking.

### Code Quality

```bash
# 1. Format code
ruff format .

# 2. Lint and fix issues
ruff check --fix .

# 3. Type check
mypy .

# 4. Test your changes
coursemology_uploader examples/config.yaml
```

## Architecture

- `core.py` - Main workflow orchestration and CLI entry point
- `configs.py` - Configuration data classes
- `downloader.py` - File download utilities with authentication
- `extractor.py` - ZIP extraction utilities
- `scraper.py` - Directory index scraping and URL filtering
- `csv_utils.py` - CSV parsing and mapping utilities

## Error Handling

The tool provides clear error messages for common issues:
- Missing or invalid configuration files
- Authentication failures
- File not found errors
- Network connectivity issues
- Invalid CSV mappings
- Coursemology API errors

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.