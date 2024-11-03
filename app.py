import streamlit as st
import pandas as pd
import numpy as np
from openai import OpenAI
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
from pathlib import Path
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
                # Check if column contains numeric data (including strings that represent numbers)
                numeric_mask = pd.to_numeric(numeric_df[column], errors='coerce').notna()
                if numeric_mask.any():
                    numeric_df[column] = pd.to_numeric(numeric_df[column], errors='coerce').fillna(0)
            except Exception as e:
                logger.warning(f"Could not convert column {column} to numeric: {str(e)}")
        return numeric_df

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
        
        # Convert numeric columns in parent dataframe
        consolidated = self._safe_numeric_conversion(parent_df.copy())
        
        # Process each subsidiary
        for sub_df in subsidiary_dfs:
            # Convert numeric columns in subsidiary dataframe
            sub_df = self._safe_numeric_conversion(sub_df)
            
            # Check ownership percentage (assuming column exists)
            ownership = 100  # default to 100%
            if 'ownership_percentage' in sub_df.columns:
                ownership_col = pd.to_numeric(sub_df['ownership_percentage'], errors='coerce')
                ownership = ownership_col.iloc[0] if not ownership_col.empty else 100
            
            if ownership > 50:  # AS21 control criterion
                # Perform eliminations
                eliminations = self._calculate_eliminations(consolidated, sub_df)
                
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
            inv_values = pd.to_numeric(parent_df['investment_in_subsidiary'], errors='coerce')
            eliminations['investment'] = inv_values.sum()
        
        # Intercompany transactions
        if 'intercompany_receivables' in parent_df.columns and 'intercompany_payables' in subsidiary_df.columns:
            parent_recv = pd.to_numeric(parent_df['intercompany_receivables'], errors='coerce')
            sub_pay = pd.to_numeric(subsidiary_df['intercompany_payables'], errors='coerce')
            
            eliminations['intercompany_transactions'] = min(
                parent_recv.sum(),
                sub_pay.sum()
            )
        
        return eliminations

    def _add_subsidiary_amounts(self, consolidated: pd.DataFrame, 
                              subsidiary: pd.DataFrame, 
                              eliminations: Dict,
                              ownership: float) -> pd.DataFrame:
        """Add subsidiary amounts to consolidated statements"""
        
        # Calculate minority interest
        minority_interest = (1 - ownership/100)
        
        # Add subsidiary amounts line by line
        for column in subsidiary.columns:
            if column in consolidated.columns and self._is_numeric_column(subsidiary, column):
                # Skip if it's an elimination account
                if 'intercompany' in column.lower():
                    continue
                
                # Ensure we're working with numeric values
                sub_values = pd.to_numeric(subsidiary[column], errors='coerce').fillna(0)
                
                # Add subsidiary amount
                consolidated[column] += sub_values * (ownership/100)
                
                # Add minority interest column if needed
                mi_column = f"minority_interest_{column}"
                consolidated[mi_column] = sub_values * minority_interest
        
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
            # Write consolidated data
            consolidated_df = pd.DataFrame.from_dict(consolidated_data)
            consolidated_df.to_excel(writer, sheet_name='Consolidated', index=False)
            
            # Summary sheet
            self._write_summary_sheet(writer, consolidated_data, analysis_results)
            
            # Analysis sheet
            self._write_analysis_sheet(writer, analysis_results)
        
        output.seek(0)
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
        
        if summary_data:
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', 
                                              index=False)

    def _write_analysis_sheet(self, writer: pd.ExcelWriter, 
                            analysis_results: List[Dict]):
        """Write analysis sheet"""
        analysis_data = []
        
        for analysis in analysis_results:
            analysis_data.append({
                'Sheet Name': analysis['sheet_name'],
                'Analysis': analysis['analysis']
            })
        
        if analysis_data:
            pd.DataFrame(analysis_data).to_excel(writer, sheet_name='Analysis', 
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
            logger.error(f"Application error: {str(e)}")

if __name__ == "__main__":
    main()
