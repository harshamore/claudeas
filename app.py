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
    st.markdown("Upload your Excel files containing financial statements to consolidate them according to AS 21 standards. Please mark one file as the Parent Company to proceed with the analysis.")
    
    processor = AS21Processor()
    
    uploaded_files = st.file_uploader("Upload Financial Statements", type=['xlsx', 'xls'], accept_multiple_files=True)
    
    if uploaded_files:
        parent_file = None
        subsidiary_files = []

        # Display each file with a checkbox to mark it as the parent company file
        for file in uploaded_files:
            st.write(f"Processing file: {file.name}")
            is_parent = st.checkbox(f"Mark {file.name} as Parent Company", key=file.name)

            if is_parent:
                if parent_file is None:
                    parent_file = file
                else:
                    st.warning("Only one file can be marked as the Parent Company. Uncheck the previous selection to change the parent file.")
            else:
                subsidiary_files.append(file)

        # Ensure a parent file is selected before proceeding
        if parent_file:
            try:
                st.write("Analyzing the Parent Company file...")
                parent_xls = pd.ExcelFile(parent_file)
                parent_analysis = processor.analyze_all_sheets(parent_xls)
                
                # Display analysis of the parent file
                for sheet_name, analysis in parent_analysis.items():
                    with st.expander(f"Parent Company - Analysis of Sheet: {sheet_name}"):
                        st.write(analysis)
                
                # Process each subsidiary file
                st.write("Analyzing Subsidiary Company files...")
                for file in subsidiary_files:
                    try:
                        xls = pd.ExcelFile(file)
                        file_analysis = processor.analyze_all_sheets(xls)
                        
                        for sheet_name, analysis in file_analysis.items():
                            with st.expander(f"Subsidiary Company - {file.name} - Analysis of Sheet: {sheet_name}"):
                                st.write(analysis)
                    
                    except Exception as e:
                        st.error(f"An error occurred while processing {file.name}: {str(e)}")
                        logger.error(f"Error processing file {file.name}: {str(e)}")

            except Exception as e:
                st.error(f"An error occurred while processing the Parent Company file: {str(e)}")
                logger.error(f"Error processing the Parent Company file: {str(e)}")
        else:
            st.warning("Please mark one file as the Parent Company to proceed with the analysis.")

if __name__ == "__main__":
    main()
