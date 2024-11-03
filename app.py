import streamlit as st
import pandas as pd
import numpy as np
from openai import OpenAI
from typing import List, Dict
from dataclasses import dataclass
import logging
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ConsolidationItem:
    """Represents a consolidation line item"""
    account_name: str
    parent_value: float
    subsidiary_value: float
    elimination: float
    consolidated_value: float
    notes: List[str]

class AS21Processor:
    """Handles AS21 consolidation rules and processing"""
    
    def __init__(self):
        self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    def _is_numeric_column(self, df: pd.DataFrame, column: str) -> bool:
        """Check if a column contains numeric data"""
        return pd.api.types.is_numeric_dtype(df[column])

    def _safe_numeric_conversion(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert numeric columns to float, leaving non-numeric columns unchanged"""
        numeric_df = df.copy()
        for column in numeric_df.columns:
            try:
                # Convert only numeric columns
                if pd.api.types.is_numeric_dtype(numeric_df[column]):
                    numeric_df[column] = pd.to_numeric(numeric_df[column], errors='coerce').fillna(0)
            except Exception as e:
                logger.warning(f"Could not convert column {column} to numeric: {str(e)}")
        return numeric_df

    def analyze_statement(self, df: pd.DataFrame, sheet_name: str) -> Dict:
        """Analyze financial statement using GPT-4"""
        try:
            sample_data = df.head().applymap(str).to_string()
            prompt = f"""
            As an Indian Chartered Accountant, analyze this financial statement '{sheet_name}':
            {sample_data}
            
            Provide:
            1. Statement type identification
            2. Key AS21 considerations
            3. Potential consolidation issues
            4. Required eliminations
            """
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            return {"analysis": response.choices[0].message["content"], "sheet_name": sheet_name, "data": df}
        except Exception as e:
            logger.error(f"Error analyzing sheet {sheet_name}: {str(e)}")
            raise

    def process_consolidation(self, parent_df: pd.DataFrame, subsidiary_dfs: List[pd.DataFrame]) -> pd.DataFrame:
        """Process consolidation according to AS21 rules"""
        consolidated = self._safe_numeric_conversion(parent_df.copy())
        
        for sub_df in subsidiary_dfs:
            sub_df = self._safe_numeric_conversion(sub_df)
            ownership = sub_df.get('ownership_percentage', 100).iloc[0] if 'ownership_percentage' in sub_df else 100
            
            if ownership > 50:
                eliminations = self._calculate_eliminations(consolidated, sub_df)
                consolidated = self._add_subsidiary_amounts(consolidated, sub_df, eliminations, ownership)
        return consolidated

    def _calculate_eliminations(self, parent_df: pd.DataFrame, subsidiary_df: pd.DataFrame) -> Dict:
        """Calculate necessary eliminations"""
        eliminations = {'investment': 0, 'intercompany_transactions': 0, 'unrealized_profit': 0}
        if 'investment_in_subsidiary' in parent_df.columns:
            eliminations['investment'] = pd.to_numeric(parent_df['investment_in_subsidiary'], errors='coerce').sum()
        if 'intercompany_receivables' in parent_df.columns and 'intercompany_payables' in subsidiary_df.columns:
            parent_recv = pd.to_numeric(parent_df['intercompany_receivables'], errors='coerce').sum()
            sub_pay = pd.to_numeric(subsidiary_df['intercompany_payables'], errors='coerce').sum()
            eliminations['intercompany_transactions'] = min(parent_recv, sub_pay)
        return eliminations

    def _add_subsidiary_amounts(self, consolidated: pd.DataFrame, subsidiary: pd.DataFrame, eliminations: Dict, ownership: float) -> pd.DataFrame:
        """Add subsidiary amounts to consolidated statements"""
        minority_interest = (1 - ownership / 100)
        for column in subsidiary.columns:
            if column in consolidated.columns and self._is_numeric_column(subsidiary, column):
                sub_values = pd.to_numeric(subsidiary[column], errors='coerce').fillna(0)
                consolidated[column] = pd.to_numeric(consolidated[column], errors='coerce').fillna(0)
                consolidated[column] += sub_values * (ownership / 100)
                mi_column = f"minority_interest_{column}"
                consolidated[mi_column] = sub_values * minority_interest
        return consolidated

class ReportGenerator:
    """Generates consolidated financial reports"""
    
    def __init__(self):
        self.sections = {
            'balance_sheet': {'assets': ['current_assets', 'non_current_assets'], 'liabilities': ['current_liabilities', 'non_current_liabilities'], 'equity': ['share_capital', 'reserves', 'minority_interest']},
            'income_statement': {'revenue': ['operating_revenue', 'other_income'], 'expenses': ['operating_expenses', 'finance_costs'], 'profit': ['operating_profit', 'net_profit']}
        }

    def generate_excel_report(self, consolidated_data: pd.DataFrame, analysis_results: List[Dict]) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            consolidated_data.to_excel(writer, sheet_name='Consolidated', index=False)
            self._write_summary_sheet(writer, consolidated_data, analysis_results)
            self._write_analysis_sheet(writer, analysis_results)
        output.seek(0)
        return output.getvalue()

    def _write_summary_sheet(self, writer: pd.ExcelWriter, consolidated_data: pd.DataFrame, analysis_results: List[Dict]):
        summary_data = [{'Sheet Name': str(analysis['sheet_name']), 'Analysis': str(analysis['analysis'])} for analysis in analysis_results]
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

    def _write_analysis_sheet(self, writer: pd.ExcelWriter, analysis_results: List[Dict]):
        analysis_data = [{'Sheet Name': analysis['sheet_name'], 'Analysis': analysis['analysis']} for analysis in analysis_results]
        pd.DataFrame(analysis_data).to_excel(writer, sheet_name='Analysis', index=False)

def main():
    st.set_page_config(page_title="AS 21 Account Consolidator", layout="wide")
    st.title("AI-Powered AS 21 Account Consolidation")
    st.markdown("Upload your Excel files containing financial statements to consolidate them according to AS 21 standards. The AI will assist in analyzing and consolidating the accounts.")
    
    processor = AS21Processor()
    report_generator = ReportGenerator()
    
    parent_file = st.file_uploader("Upload Parent Company Excel File", type=['xlsx', 'xls'])
    subsidiary_files = st.file_uploader("Upload Subsidiary Company Excel Files", type=['xlsx', 'xls'], accept_multiple_files=True)
    
    if parent_file and subsidiary_files:
        try:
            with st.spinner('Processing files...'):
                parent_df = pd.read_excel(parent_file)
                parent_analysis = processor.analyze_statement(parent_df, "Parent Company")
                
                subsidiary_dfs = []
                subsidiary_analyses = []
                
                for file in subsidiary_files:
                    df = pd.read_excel(file)
                    analysis = processor.analyze_statement(df, file.name)
                    subsidiary_dfs.append(df)
                    subsidiary_analyses.append(analysis)
                
                consolidated_df = processor.process_consolidation(parent_df, subsidiary_dfs)
                
                st.subheader("AI Analysis Results")
                with st.expander("Parent Company Analysis"):
                    st.write(parent_analysis["analysis"])
                
                for analysis in subsidiary_analyses:
                    with st.expander(f"Analysis of {analysis['sheet_name']}"):
                        st.write(analysis["analysis"])
                
                st.subheader("Consolidated Results")
                st.dataframe(consolidated_df)
                
                if st.button("Generate Consolidated Report"):
                    with st.spinner('Generating report...'):
                        excel_report = report_generator.generate_excel_report(consolidated_df, [parent_analysis] + subsidiary_analyses)
                        st.download_button(label="Download Consolidated Report", data=excel_report, file_name="consolidated_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            logger.error(f"Application error: {str(e)}")

if __name__ == "__main__":
    main()
