import streamlit as st
import pandas as pd
import numpy as np
from openai import OpenAI
import logging
from io import BytesIO
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AS21Processor:
    """Handles AS21 consolidation rules and processing with selective OpenAI support"""
    
    def __init__(self):
        self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        self.known_responses = {}  # Cache to store common clarifications from OpenAI
    
    def ask_openai(self, question: str) -> str:
        """Ask OpenAI a question if it hasn't been asked before, to minimize calls."""
        if question in self.known_responses:
            return self.known_responses[question]
        
        response = self.client.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": question}],
            max_tokens=300
        ).choices[0].message.content.strip()
        
        # Cache the response
        self.known_responses[question] = response
        return response

    def analyze_sheet(self, df: pd.DataFrame, sheet_name: str) -> Optional[str]:
        """Primary data inspection; uses OpenAI if data structure is unclear."""
        
        if df.empty:
            return f"Sheet '{sheet_name}' is empty or image-only, with no data to analyze."
        
        # Attempt to identify sheet type based on keywords in columns
        columns = df.columns.str.lower().tolist()
        if any(kw in columns for kw in ['assets', 'liabilities', 'equity']):
            sheet_type = "Balance Sheet"
        elif any(kw in columns for kw in ['revenue', 'expenses', 'profit']):
            sheet_type = "Income Statement"
        elif any(kw in columns for kw in ['cash', 'operating', 'financing']):
            sheet_type = "Cash Flow Statement"
        else:
            # Ask OpenAI if Python couldn't confidently identify the sheet type
            question = f"Can you help identify the type of financial statement from these column headers: {columns}"
            sheet_type = self.ask_openai(question)
        
        # Return consolidated analysis with identified type
        return f"Sheet '{sheet_name}' is identified as '{sheet_type}' based on AS 21 guidelines."

    def perform_consolidation(self, parent_df: pd.DataFrame, subsidiary_dfs: list[pd.DataFrame]) -> pd.DataFrame:
        """Consolidate data according to AS21 rules, using OpenAI only if a major ambiguity arises."""
        
        consolidated = parent_df.copy()
        
        for sub_df in subsidiary_dfs:
            # Check ownership and ensure required columns exist
            ownership_col = sub_df.get("ownership_percentage", pd.Series([100])).iloc[0]
            if ownership_col <= 50:
                continue  # Skip non-controlling interest

            # Basic consolidation addition, add values where applicable
            for col in consolidated.columns.intersection(sub_df.columns):
                try:
                    consolidated[col] += sub_df[col] * (ownership_col / 100)
                except Exception as e:
                    # If unexpected data, ask OpenAI for guidance
                    question = f"How should I handle an unexpected data type in column '{col}' during consolidation?"
                    advice = self.ask_openai(question)
                    logger.warning(f"{advice} - Error: {e}")
        
        return consolidated

def main():
    st.set_page_config(page_title="AS 21 Account Consolidator", layout="wide")
    st.title("Selective AI-Powered AS 21 Account Consolidation")
    st.markdown("Upload your Excel files containing financial statements to consolidate them according to AS 21 standards. Please mark one file as the Parent Company.")

    processor = AS21Processor()
    
    uploaded_files = st.file_uploader("Upload Financial Statements", type=['xlsx', 'xls'], accept_multiple_files=True)
    
    if uploaded_files:
        parent_file = None
        subsidiary_files = []

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

        if parent_file:
            try:
                parent_df = pd.ExcelFile(parent_file).parse()
                st.write("Analyzing Parent Company file...")
                
                analysis = processor.analyze_sheet(parent_df, "Parent Company")
                st.write(analysis)
                
                consolidated_df = processor.perform_consolidation(parent_df, [pd.ExcelFile(f).parse() for f in subsidiary_files])
                
                st.write("Consolidated Results:")
                st.dataframe(consolidated_df)
                
                # Option to download consolidated report
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    consolidated_df.to_excel(writer, sheet_name="Consolidated")
                output.seek(0)
                
                st.download_button(
                    label="Download Consolidated Report",
                    data=output,
                    file_name="consolidated_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                logger.error(f"Error: {str(e)}")
        else:
            st.warning("Please mark one file as the Parent Company to proceed with the analysis.")

if __name__ == "__main__":
    main()
