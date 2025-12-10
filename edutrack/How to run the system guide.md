# Installation Guide

## Required Python Packages

To use all features of the EduTrack system, you need to install the following packages:

### 1. Core Django 
```bash
pip install django
```
### 2. PDF Generation 
```bash
pip install reportlab
```
**Required for:** Generating PDF grade reports

### 3. Machine Learning Features 
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

## Verification

After installation, you can verify by running:
```bash
python manage.py check
```
## To run the system
**Change directory to edutrack** 
```bash
cd edutrack
```
**Run the server** 
```bash
python manage.py runserver
```
The system should start without errors. ML and PDF features will be available once the packages are installed.

