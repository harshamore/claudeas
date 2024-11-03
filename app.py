import streamlit as st
import pandas as pd
import numpy as np
from openai import OpenAI
import os
from typing import List, Dict
from dataclasses import dataclass
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dataclass definitions
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
        
    def analyze_statement(self, df: pd.DataFrame, sheet_name: str) -> Dict:
        """Analyze financial statement using GPT-4"""
        try:
            sample_data = df.head().to_string()
            
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
            
            return {
                "analysis": response.choices[0].message.content,
                "sheet_name": sheet_name,
                "data": df
            }
        except Exception as e:
            logger.error(f"Error analyzing sheet {sheet_name}: {str(e)}")
            raise

    def identify_statement_type(self, df: pd.DataFrame) -> str:
        """Identify the type of financial statement"""
        keywords = {
            'balance_sheet': ['assets', 'liabilities', 'equity', 'capital'],
            'income_statement': ['revenue', 'expenses', 'profit', 'loss'],
            'cash_flow': ['operating', 'investing', 'financing']
        }
        
        columns = [col.lower() for col in df.columns]
        
        for stmt_type, kwords in keywords.items():
            if any(kw in ' '.join(columns) for kw in kwords):
                return stmt_type
        
        return 'unknown'

    def process_consolidation(self, parent_df: pd.DataFrame, 
                            subsidiary_dfs: List[pd.DataFrame]) -> pd.DataFrame:
        """Process consolidation according to AS21 rules"""
        
        # Initialize consolidated dataframe with parent data
        consolidated = parent_df.copy()
        
        # Process each subsidiary
        for sub_df in subsidiary_dfs:
            # Check ownership percentage (assuming column exists)
            ownership = sub_df.get('ownership_percentage', 100)
            
            if ownership > 50:  # AS21 control criterion
                # Perform eliminations
                eliminations = self._calculate_eliminations(parent_df, sub_df)
                
                # Add subsidiary amounts
                consolidated = self._add_subsidiary_amounts(consolidated, sub_df, 
                                                         eliminations, ownership)
        
        return consolidated

    def _calculate_eliminations(self, parent_df: pd.DataFrame, 
                              subsidiary_df: pd.DataFrame) -> Dict:
        """Calculate necessary eliminations"""
        eliminations = {
            'investment': 0,
            'intercompany_transactions': 0,
            'unrealized_profit': 0
        }
        
        # Investment elimination
        if 'investment_in_subsidiary' in parent_df.columns:
            eliminations['investment'] = parent_df['investment_in_subsidiary'].sum()
        
        # Intercompany transactions
        if 'intercompany_receivables' in parent_df.columns:
            eliminations['intercompany_transactions'] = min(
                parent_df['intercompany_receivables'].sum(),
                subsidiary_df.get('intercompany_payables', 0).sum()
            )
        
        return eliminations

    def _add_subsidiary_amounts(self, consolidated: pd.DataFrame, 
                              subsidiary: pd.DataFrame, 
                              eliminations: Dict,
                              ownership: float) -> pd.DataFrame:
        """Add subsidiary amounts to consolidated statements"""
        
        # Calculate minority interest
        minority_interest = (1 - ownership / 100)
        
        # Add subsidiary amounts line by line
        for column in subsidiary.columns:
            if column in consolidated.columns:
                # Skip if it's an elimination account
                if 'intercompany' in column.lower():
                    continue
                
                # Only add numeric columns
                if pd.api.types.is_numeric_dtype(subsidiary[column]):
                    # Add subsidiary amount
                    consolidated[column] += subsidiary[column] * (ownership / 100)
                    
                    # Add minority interest column if needed
                    mi_column = f"minority_interest_{column}"
                    if mi_column not in consolidated.columns:
                        consolidated[mi_column] = 0  # Initialize minority interest column
                    consolidated[mi_column] += subsidiary[column] * minority_interest

        return consolidated

class ReportGenerator:
    """Generates consolidated financial reports"""
    
    def __init__(self):
        self.sections = {
            'balance_sheet': {
                'assets': ['current_assets', 'non_current_assets'],
                'liabilities': ['current_liabilities', 'non_current_liabilities'],
                'equity': ['share_capital', 'reserves', 'minority_interest']
            },
            'income_statement': {
                'revenue': ['operating_revenue', 'other_income'],
                'expenses': ['operating_expenses', 'finance_costs'],
                'profit': ['operating_profit', 'net_profit']
            }
        }

    def generate_excel_report(self, consolidated_data: Dict, 
                            analysis_results: List[Dict]) -> bytes:
        """Generate formatted Excel report"""
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary sheet
            self._write_summary_sheet(writer, consolidated_data, analysis_results)
            
            # Detailed sheets
            self._write_detailed_sheets(writer, consolidated_data)
            
            # Analysis sheet
            self._write_analysis_sheet(writer, analysis_results)
        
        return output.getvalue()

    def _write_summary_sheet(self, writer: pd.ExcelWriter, 
                           consolidated_data: Dict,
                           analysis_results: List[Dict]):
        """Write summary sheet"""
        summary_data = []
        
        for section, categories in self.sections.items():
            for category, subcategories in categories.items():
                for subcategory in subcategories:
                    if subcategory in consolidated_data:
                        summary_data.append({
                            'Section': section,
                            'Category': category,
                            'Subcategory': subcategory,
                            'Consolidated Value': consolidated_data[subcategory]
                        })
        
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', 
                                          index=False)

def main():
    st.set_page_config(page_title="AS 21 Account Consolidator", layout="wide")
    
    st.title("AI-Powered AS 21 Account Consolidation")
    st.markdown("""
    Upload your Excel files containing financial statements to consolidate them 
    according to AS 21 standards. The AI will assist in analyzing and 
    consolidating the accounts.
    """)
    
    # Initialize processors
    processor = AS21Processor()
    report_generator = ReportGenerator()
    
    # File upload section
    st.subheader("Upload Financial Statements")
    
    parent_file = st.file_uploader("Upload Parent Company Excel File", 
                                 type=['xlsx', 'xls'])
    
    subsidiary_files = st.file_uploader("Upload Subsidiary Company Excel Files",
                                      type=['xlsx', 'xls'],
                                      accept_multiple_files=True)
    
    if parent_file and subsidiary_files:
        try:
            with st.spinner('Processing files...'):
                # Process parent file
                parent_df = pd.read_excel(parent_file)
                parent_analysis = processor.analyze_statement(parent_df, 
                                                           "Parent Company")
                
                # Process subsidiary files
                subsidiary_dfs = []
                subsidiary_analyses = []
                
                for file in subsidiary_files:
                    df = pd.read_excel(file)
                    analysis = processor.analyze_statement(df, file.name)
                    subsidiary_dfs.append(df)
                    subsidiary_analyses.append(analysis)
                
                # Perform consolidation
                consolidated_df = processor.process_consolidation(parent_df, 
                                                               subsidiary_dfs)
                
                # Display analyses
                st.subheader("AI Analysis Results")
                
                with st.expander("Parent Company Analysis"):
                    st.write(parent_analysis["analysis"])
                
                for analysis in subsidiary_analyses:
                    with st.expander(f"Analysis of {analysis['sheet_name']}"):
                        st.write(analysis["analysis"])
                
                # Display consolidated results
                st.subheader("Consolidated Results")
                st.dataframe(consolidated_df)
                
                # Generate downloadable report
                if st.button("Generate Consolidated Report"):
                    with st.spinner('Generating report...'):
                        excel_report = report_generator.generate_excel_report(
                            consolidated_df.to_dict(),
                            [parent_analysis] + subsidiary_analyses
                        )
                        
                        st.download_button(
                            label="Download Consolidated Report",
                            data=excel_report,
                            file_name="consolidated_report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            logger.error(f"Application error: {str(e)}
