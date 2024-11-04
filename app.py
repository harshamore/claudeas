import streamlit as st
import requests
import io
from PyPDF2 import PdfReader

# URL of the PDF document
pdf_url = "https://resource.cdn.icai.org/69249asb55316-as21.pdf"

def download_pdf(url):
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content)

def read_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def parse_steps(text):
    # Implement the actual parsing logic based on the PDF's structure
    # For demonstration, we'll assume that steps are numbered like "Step 1", "Step 2", etc.
    import re
    pattern = r"Step\s*\d+[:.-]?(.*?)(?=Step\s*\d+[:.-]|$)"
    steps = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    return steps

def create_step_function(step_text, step_number):
    def step_function():
        st.write(f"### Step {step_number}")
        st.write(step_text.strip())
        # Add any processing logic needed for the step
    return step_function

def main():
    st.title("Process PDF Steps from URL")
    
    pdf_file = download_pdf(pdf_url)
    pdf_text = read_pdf(pdf_file)
    steps = parse_steps(pdf_text)
    
    if not steps:
        st.write("No steps found in the document.")
        return
    
    # **Print the steps**
    st.write("## Extracted Steps:")
    for i, step_text in enumerate(steps, 1):
        st.write(f"### Step {i}")
        st.write(step_text.strip())
        st.write("---")
    
    # **Create functions for each step**
    step_functions = []
    for i, step_text in enumerate(steps, 1):
        step_func = create_step_function(step_text, i)
        step_functions.append(step_func)
    
    # **Interactive buttons to execute each step**
    st.write("## Execute Steps:")
    for i, step_function in enumerate(step_functions, 1):
        if st.button(f"Run Step {i}"):
            step_function()

if __name__ == "__main__":
    main()
