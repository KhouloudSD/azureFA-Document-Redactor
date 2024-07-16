Features

This repository contains the source code for an Intelligent Document Redaction project, designed to enhance employee efficiency by indexing emails and redacting sensitive data from attachments. The project leverages various technologies and tools to achieve this functionality.

Redaction Capabilities

* Sensitive Information Redaction: Identifies and obscures sensitive information in images, PDFs, text files, and MP4 videos.
    Image Redaction: Uses Optical Character Recognition (OCR) to detect and redact sensitive text in images.
    PDF Redaction: Extracts and redacts sensitive data from PDF documents.
    Text File Redaction: Detects and obscures sensitive information in text files using natural language processing (NLP).
    Video Redaction: Redacts sensitive audio information in MP4 videos.

HTTP Trigger Function
    A Python Azure Function to process HTTP requests for document indexing and redaction.
    Extracts documents from SharePoint, processes them, and uploads the modified files back to SharePoint.
  
Technologies Used
    Azure Functions: Serverless compute service.
    SharePoint API: For accessing and modifying SharePoint documents.
    Keras OCR: Optical Character Recognition (OCR) for image processing.
    SpaCy: Natural language processing (NLP) for text analysis.
    AssemblyAI: For audio transcription and redaction.
    MoviePy: For video processing.
    FitZ: For PDF manipulation.
    OpenCV: For image processing.
    Python Libraries: Including requests, numpy, PIL, and more.
  
This project uses Python 3.11.
