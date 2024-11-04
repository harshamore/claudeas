import streamlit as st
import requests
import io
import pdfplumber
import re

# URL of the PDF document
pdf_url = "https://resource.cdn.icai.org/69249asb55316-as21.pdf"

def download_pdf(url):
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content)

def read_pdf(pdf_file):
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def parse_steps(text):
    """
    Parses the extracted text to find steps and their content.
    Adjust the regex pattern based on the document's format.
    """
    # Regular expression to match steps starting with "Step X:"
    pattern = r"(?:^|\n)(Step\s+\d+[\.:]\s*)(.*?)\n(?=Step\s+\d+[\.:]|$)"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    steps = []
    for match in matches:
        step_title = match[0].strip()
        step_content = match[1].strip()
        steps.append((step_title, step_content))
    return steps

def create_step_function(step_title, step_content, step_number):
    def step_function():
        st.write(f"## {step_title}")
        st.write(step_content)
        # Add processing logic specific to the step here
    return step_function

def main():
    st.title("Process PDF Steps from URL")
    
    st.write("Downloading and processing the PDF document...")
    try:
        pdf_file = download_pdf(pdf_url)
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading PDF: {e}")
        return
    
    pdf_text = read_pdf(pdf_file)
    
    if not pdf_text:
        st.error("Failed to extract text from the PDF.")
        return
    
    st.write("Extracting steps from the document...")
    steps = parse_steps(pdf_text)
    
    if not steps:
        st.error("No steps found in the document.")
        return
    
    st.success(f"Found {len(steps)} steps in the document.")
    
    st.write("---")
    st.write("## Extracted Steps:")
    for i, (step_title, step_content) in enumerate(steps, 1):
        st.write(f"### {step_title}")
        st.write(step_content)
        st.write("---")
    
    st.write("## Execute Steps:")
    for i, (step_title, step_content) in enumerate(steps, 1):
        if st.button(f"Run {step_title}"):
            step_function = create_step_function(step_title, step_content, i)
            step_function()

if __name__ == "__main__":
    main()
