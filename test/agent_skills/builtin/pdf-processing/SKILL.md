---
name: pdf-processing
description: Extract text and tables from PDF files, fill PDF forms, merge documents, and create PDFs. Use when working with PDF documents, extracting content from PDFs, or when the user mentions PDFs, forms, or document processing.
license: MIT
metadata:
  author: VTSBot
  version: "1.0"
allowed-tools: Bash(pdftotext:*) Bash(pdfinfo:*) Read Write
---

# PDF Processing Skill

This skill provides comprehensive PDF document handling capabilities.

## When to Use This Skill

- User mentions "PDF", "PDFs", or "document extraction"
- User wants to extract text or tables from documents
- User needs to fill PDF forms
- User wants to merge or split PDF documents
- User needs to create PDFs from other formats

## Capabilities

### Text Extraction

Extract text content from PDF files:

```bash
pdftotext input.pdf output.txt
pdftotext -layout input.pdf output.txt  # Preserve layout
```

### Table Extraction

Extract tables from PDFs:

```bash
# Using pdftotext with layout mode
pdftotext -layout input.pdf - | head -50
```

### PDF Information

Get metadata and page count:

```bash
pdfinfo document.pdf
```

### Merge PDFs

Combine multiple PDFs:

```bash
# Using ghostscript
gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=merged.pdf file1.pdf file2.pdf
```

## Step-by-Step Process

1. **Identify the PDF operation needed**
   - Text extraction?
   - Table extraction?
   - Merge/split?
   - Form filling?

2. **Check PDF existence**
   ```bash
   ls -la path/to/file.pdf
   pdfinfo path/to/file.pdf
   ```

3. **Execute the appropriate command**
   - Use the commands above based on operation type

4. **Verify results**
   - Check output file exists
   - Verify content is extracted correctly

## Common Edge Cases

- **Encrypted PDFs**: May require password or decryption
- **Scanned PDFs**: Need OCR (tesseract) for text extraction
- **Large PDFs**: Process in chunks or use streaming
- **Corrupted PDFs**: Try repair tools first

## Error Handling

```bash
# Check if PDF is valid before processing
pdfinfo input.pdf 2>&1 | grep -i error && echo "PDF may be corrupted"
```

## Dependencies

- `poppler-utils` (pdftotext, pdfinfo)
- `ghostscript` (gs) for merging
- Optional: `tesseract-ocr` for scanned PDFs
