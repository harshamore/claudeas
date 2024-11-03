import streamlit as st
import pandas as pd
from openai import OpenAI
import logging
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AS21Processor:
    """Handles AS21 consolidation rules and processing"""
    
    def __init__(self):
        self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    def analyze_statement(self, df: pd.DataFrame, sheet_name: str) -> str:
        """Analyze financial statement using GPT-4, presenting data in context for clarity."""
        if df.empty:
            return f"The sheet '{sheet_name}' is empty or image-only, with no data to analyze."
        
        sample_data_str = df.head().to_string(index=False)
        
        # Refined prompt for OpenAI
        prompt = f"""
        I am providing a financial statement sample from the '{sheet_name}' sheet below.
        Please analyze this financial statement in the context of AS21, identifying:
        
        1. The type of statement (e.g., Balance Sheet, Income Statement).
        2. Key AS21 considerations.
        3. Any potential consolidation issues.
        4. Required eliminations, if any.
        
        Here is the sample data:
        
        {sample_data_str}
        
        Please proceed with the analysis based on the above data.
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.choices[0].message.content

    def analyze_all_sheets(self, xls: pd.ExcelFile) -> dict[str, str]:
        """Iterate through all sheets and analyze each one, handling empty or image-only sheets gracefully."""
        analysis_results = {}
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            analysis_results[sheet_name] = self.analyze_statement(df, sheet_name)
        return analysis_results

def main():
    st.set_page_config(page_title="AS 21 Account Consolidator", layout="wide")
    st.title("AI-Powered AS 21 Account Consolidation")
    st.markdown("Upload your Excel files containing financial statements to consolidate them according to AS 21 standards. The AI will assist in analyzing and consolidating the accounts.")
    
    processor = AS21Processor()
    
    uploaded_files = st.file_uploader("Upload Financial Statements", type=['xlsx', 'xls'], accept_multiple_files=True)
    
    if uploaded_files:
        all_analysis_results = {}
        for file in uploaded_files:
            try:
                xls = pd.ExcelFile(file)
                st.write(f"Processing file: {file.name}")
                file_analysis = processor.analyze_all_sheets(xls)
                
                for sheet_name, analysis in file_analysis.items():
                    with st.expander(f"Analysis of {file.name} - Sheet: {sheet_name}"):
                        st.write(analysis)
                
                all_analysis_results[file.name] = file_analysis

            except Exception as e:
                st.error(f"An error occurred while processing {file.name}: {str(e)}")
                logger.error(f"Error processing file {file.name}: {str(e)}")

if __name__ == "__main__":
    main()
