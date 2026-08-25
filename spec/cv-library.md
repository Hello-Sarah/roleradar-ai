# CV Library and Tailored CV

## User value

The user keeps existing CVs in one configured folder. RoleRadar indexes those files and,
after the user explicitly selects a saved job, creates a truthful, ATS-friendly Word CV
tailored to that job.

## Workflow

1. The user places `.docx`, `.pdf`, or `.txt` CVs in `CV_LIBRARY_PATH`.
2. The user clicks **Scan CV folder**. RoleRadar extracts text, fingerprints each file,
   updates changed files, and marks removed files inactive.
3. The user selects an existing job and clicks **Generate tailored CV**.
4. The LLM may prioritize and rewrite existing evidence but cannot invent facts.
5. RoleRadar validates every generated item against an exact quote from the source corpus.
6. A `.docx` is written to `GENERATED_CV_PATH` as `名字—岗位-chatgpt.docx`.

## Acceptance criteria

- Source files are never modified and both source/output defaults are excluded from Git.
- Repeated scans do not create duplicate library records.
- Missing, unreadable, or textless files produce actionable per-file errors.
- Generation fails clearly when the library is empty or no model API key is configured.
- Unsupported model claims stop the entire generation before a file is written.
- The generated response includes job ID, output filename, source CV IDs, and timestamp.
- Download rejects path traversal and only serves files from the configured output folder.

## Privacy and limitations

- The configured OpenAI-compatible provider receives the selected job description and
  extracted CV text during generation. Scanning alone does not call a model.
- Scanned PDFs must contain an extractable text layer; OCR is not part of this version.
- RoleRadar does not claim that a tailored CV guarantees ATS or hiring outcomes.
