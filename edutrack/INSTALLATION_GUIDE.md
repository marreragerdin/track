# Installation Guide

## Required Python Packages

To use all features of the EduTrack system, you need to install the following packages:

### 1. Core Django (Already Installed)
- Django
- Other core dependencies

### 2. PDF Generation (Optional but Recommended)
```bash
pip install reportlab
```
**Required for:** Generating PDF grade reports

### 3. Machine Learning Features (Optional but Recommended)
```bash
pip install numpy scikit-learn
```
**Required for:** 
- Grade prediction
- At-risk student flagging
- Performance category classification

### 4. Install All Optional Packages at Once
```bash
pip install reportlab numpy scikit-learn
```

Or use the requirements file:
```bash
pip install -r requirements_ml.txt
```

## What Happens If Packages Are Not Installed?

- **PDF Generation**: The system will show an error message when trying to generate PDFs, directing users to install reportlab.
- **ML Features**: The system will show an error message when trying to use ML predictions, directing users to install numpy and scikit-learn.
- **Core Features**: All other features (score entry, student records, etc.) work without these packages.

## Verification

After installation, you can verify by running:
```bash
python manage.py check
```

The system should start without errors. ML and PDF features will be available once the packages are installed.

