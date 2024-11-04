import streamlit as st
import requests
import io
import fitz  # PyMuPDF
import os

# OCR.space API endpoint
OCR_SPACE_API_URL = 'https://api.ocr.space/parse/image'
# Get your API key from the environment variable
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
if not OCR_SPACE_API_KEY:
    st.error("OCR_SPACE_API_KEY environment variable not set.")
    st.stop()

# URL of the PDF document
pdf_url = "https://resource.cdn.icai.org/69249asb55316-as21.pdf"

def download_pdf(url):
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content)

def pdf_to_images(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        img_data = pix.tobytes("png")
        images.append(img_data)
    return images

def ocr_image_with_api(image_data):
    payload = {
        'isOverlayRequired': False,
        'apikey': OCR_SPACE_API_KEY,
        'language': 'eng',
    }
    files = {
        'filename': ('image.png', image_data),
    }
    response = requests.post(OCR_SPACE_API_URL, data=payload, files=files)
    result = response.json()
    if result.get('IsErroredOnProcessing'):
        st.error("Error during OCR processing.")
        return ''
    return result['ParsedResults'][0]['ParsedText']

def ocr_images(images):
    text = ""
    for idx, image_data in enumerate(images):
        st.write(f"Performing OCR on page {idx+1}...")
        page_text = ocr_image_with_api(image_data)
        text += page_text + "\n"
    return text

def main():
    st.title("Extract Text from PDF using OCR.space API")

    st.write("Downloading the PDF document...")
    try:
        pdf_file = download_pdf(pdf_url)
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading PDF: {e}")
        return

    st.write("Converting PDF pages to images...")
    images = pdf_to_images(pdf_file)

    if not images:
        st.error("Failed to convert PDF pages to images.")
        return

    st.write("Performing OCR on the images to extract text...")
    ocr_text = ocr_images(images)

    if not ocr_text.strip():
        st.error("OCR did not extract any text from the images.")
        return

    st.success("Text extraction completed.")

    # Output the extracted text
    st.write("---")
    st.write("## Extracted Text:")
    st.write(ocr_text)

    # Provide a download button to download the text as a file
    text_file = io.StringIO(ocr_text)
    st.download_button(
        label="Download Extracted Text",
        data=text_file,
        file_name="Extracted_Text.txt",
        mime="text/plain"
    )

if __name__ == "__main__":
    main()
