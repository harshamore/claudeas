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

# Rest of the code remains the same (ReportGenerator class and main function)...
